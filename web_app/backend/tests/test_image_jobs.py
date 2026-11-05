import threading
import time
import unittest
import uuid
import sys
import json
import gzip
import os
from urllib3.exceptions import ReadTimeoutError
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock, patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from app import create_app
from app.services import image_jobs, image_client


class ImageJobsTests(unittest.TestCase):
    def setUp(self):
        with image_jobs._LOCK:
            image_jobs._JOBS.clear()
        self.settings = SimpleNamespace(session_id="test", image_model="nano banana2", provider_keys={"apiyi": "secret-key"})

    def test_queue_bounded_and_duplicate_submission_does_not_repeat(self):
        entered = 0
        lock = threading.Lock()
        running = threading.Event()
        release = threading.Event()
        def work(*args):
            nonlocal entered
            with lock:
                entered += 1
                if entered == 2: running.set()
            release.wait(5)
            return {"url": "/generated/result.png"}
        ids = [str(uuid.uuid4()) for _ in range(7)]
        with patch.object(image_jobs, "run_multi_reference_generation_web", side_effect=work):
            try:
                for task_id in ids[:6]: image_jobs.submit(task_id, self.settings, [], "cat")
                self.assertTrue(running.wait(2))
                image_jobs.submit(ids[0], self.settings, [], "cat")
                self.assertEqual(entered, 2)
                with self.assertRaisesRegex(RuntimeError, "队列已满"):
                    image_jobs.submit(ids[6], self.settings, [], "cat")
                self.assertIsNone(image_jobs.status(ids[0], "other"))
                self.assertEqual(image_jobs.status(ids[2], "test")["status"], "queued")
                self.assertEqual(image_jobs.status(ids[0], "test")["status"], "running")
            finally:
                release.set()
                for task_id in ids[:2]: image_jobs._JOBS[task_id]["future"].result(timeout=3)
                deadline = time.monotonic() + 5
                while time.monotonic() < deadline and any(image_jobs.status(t, "test")["status"] in ("queued", "running") for t in ids[:6]): time.sleep(.02)
            self.assertEqual(entered, 6)
            self.assertTrue(all(image_jobs.status(t, "test")["status"] == "success" for t in ids[:6]))

    def test_failed_request_records_redacted_error(self):
        task_id = str(uuid.uuid4())
        with patch.object(image_jobs, "run_multi_reference_generation_web", side_effect=RuntimeError("bad secret-key")), patch.object(image_jobs.config, "log_to_file") as log:
            image_jobs.submit(task_id, self.settings, [], "cat")
            deadline = time.monotonic() + 3
            while time.monotonic() < deadline:
                status = image_jobs.status(task_id, "test")
                if status["status"] == "error": break
                time.sleep(.01)
            self.assertEqual(status["error"], "bad [REDACTED]")
            self.assertNotIn("secret-key", str(log.call_args_list))

    def test_queue_timeout_prevents_submission(self):
        entered = threading.Event(); release = threading.Event()
        def work(*args): entered.set(); release.wait(3); return {"url": "ok"}
        with patch.object(image_jobs, "run_multi_reference_generation_web", side_effect=work):
            ids = [str(uuid.uuid4()) for _ in range(3)]
            try:
                for task_id in ids: image_jobs.submit(task_id, self.settings, [], "cat")
                self.assertTrue(entered.wait(1))
                with image_jobs._LOCK: image_jobs._JOBS[ids[2]]["created"] -= 181
                status=image_jobs.status(ids[2], "test")
                self.assertEqual(status["status"], "error")
                self.assertIn("未提交", status["error"])
            finally:
                release.set()

    def test_http_submit_and_poll(self):
        task_id = str(uuid.uuid4())
        with patch("app.start_history_cleanup_thread"), patch.object(image_jobs, "run_multi_reference_generation_web", return_value={"url": "/generated/result.png"}):
            client = create_app().test_client()
            r = client.post("/api/multi-reference/tasks", data={"task_id": task_id, "session_id": "test", "image_model": "nano banana2", "prompt": "cat"})
            self.assertEqual(r.status_code, 202)
            deadline = time.monotonic() + 3
            while time.monotonic() < deadline:
                result=client.get("/api/multi-reference/tasks/"+task_id+"?session_id=test").get_json()["data"]
                if result["status"] == "success": break
                time.sleep(.01)
            self.assertEqual(result["result"]["url"], "/generated/result.png")
            self.assertEqual(client.get("/api/multi-reference/tasks/"+task_id+"?session_id=wrong").status_code,404)

    def test_upstream_timeout_and_key_redaction_are_logged(self):
        response = Mock(status_code=200)
        response.raw._connection = None
        response.raw._fp = None
        response.raw.read1.side_effect = [b"response", b""]
        token = image_client._REQUEST_CONTEXT.set(("nano", "secret-key"))
        try:
            with patch.object(image_client.requests, "post", return_value=response), patch.object(image_client.config, "log_to_file") as log, patch.object(image_client.time, "monotonic", side_effect=[0, 601, 602]):
                with self.assertRaises(TimeoutError): image_client._post("https://api.apiyi.com/test", timeout=360)
                self.assertIn("elapsed=602.00s", str(log.call_args_list))
                response.close.assert_called_once()
        finally:
            image_client._REQUEST_CONTEXT.reset(token)

    def test_queued_job_waits_for_shared_provider_slot(self):
        image_client._IMAGE_SLOTS.acquire()
        image_client._IMAGE_SLOTS.acquire()
        waiting = threading.Event()
        stages = []
        result = []
        def execute():
            token = image_client._IMAGE_JOB_STAGE.set(lambda stage: (stages.append(stage), waiting.set()))
            try:
                result.append(image_client.generate_image('cat', 'key', '1:1', [], 'unused', model_config={'model':'test'}))
            finally:
                image_client._IMAGE_JOB_STAGE.reset(token)
        with patch.object(image_client, '_generate_image', return_value='result.png'):
            thread = threading.Thread(target=execute)
            try:
                thread.start()
                self.assertTrue(waiting.wait(1))
                self.assertEqual(stages, ['queued'])
                image_client._IMAGE_SLOTS.release()
                thread.join(2)
                self.assertEqual(result, ['result.png'])
                self.assertEqual(stages, ['queued', 'running'])
            finally:
                image_client._IMAGE_SLOTS.release()
                thread.join(2)

    def test_real_http_stream_and_slow_stream_deadline(self):
        class Handler(BaseHTTPRequestHandler):
            def do_POST(self):
                if self.path == '/slow':
                    self.send_response(200)
                    self.send_header('Content-Length', '100000')
                    self.end_headers()
                    try:
                        for _ in range(30):
                            self.wfile.write(b'x' * 1024)
                            self.wfile.flush()
                            time.sleep(.05)
                    except (BrokenPipeError, ConnectionResetError, ConnectionAbortedError):
                        pass
                else:
                    body = gzip.compress(json.dumps({'ok': True}).encode())
                    self.send_response(200)
                    self.send_header('Content-Encoding', 'gzip')
                    self.send_header('Content-Length', str(len(body)))
                    self.end_headers()
                    self.wfile.write(body)
            def log_message(self, *_): pass
        server = ThreadingHTTPServer(('127.0.0.1', 0), Handler)
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()
        url = f'http://127.0.0.1:{server.server_port}'
        try:
            with patch.dict(os.environ, {'NO_PROXY': '127.0.0.1,localhost', 'no_proxy': '127.0.0.1,localhost'}):
                response = image_client._post(url + '/ok', json={}, timeout=3)
                self.assertEqual(response.json(), {'ok': True})
                with patch.object(image_client, '_UPSTREAM_TOTAL_SECONDS', .15):
                    with self.assertRaises((TimeoutError, ReadTimeoutError)): image_client._post(url + '/slow', json={}, timeout=3)
        finally:
            server.shutdown()
            server.server_close()
            thread.join(2)

if __name__ == "__main__": unittest.main()
