"""Bounded in-process queue for web multi-reference tasks (one Gunicorn worker)."""
from concurrent.futures import ThreadPoolExecutor
import threading
import time
import requests
from urllib3.exceptions import HTTPError as Urllib3Error

import config
from .workflows import run_multi_reference_generation_web
from .image_client import _log, _IMAGE_JOB_ID, _IMAGE_JOB_STAGE

_LOCK = threading.Lock()
_JOBS = {}
_EXECUTOR = ThreadPoolExecutor(max_workers=2, thread_name_prefix="web-image")
_MAX_ACTIVE = 6
_MAX_QUEUE_SECONDS = 180
_RETENTION_SECONDS = 3600


def _prune(now):
    for key, job in list(_JOBS.items()):
        if job.get("finished") and now - job["finished"] > _RETENTION_SECONDS:
            del _JOBS[key]


def submit(task_id, settings, reference_paths, prompt):
    now = time.monotonic()
    with _LOCK:
        _prune(now)
        existing = _JOBS.get(task_id)
        if existing:
            if existing["session"] != settings.session_id:
                raise ValueError("任务编号不可用")
            return
        if sum(j["status"] in ("queued", "running") for j in _JOBS.values()) >= _MAX_ACTIVE:
            raise RuntimeError("生图队列已满，请等待现有任务结束后再提交。")
        _JOBS[task_id] = {"session": settings.session_id, "status": "queued", "created": now, "model": settings.image_model}
        try:
            _JOBS[task_id]["future"] = _EXECUTOR.submit(_execute, task_id, settings, reference_paths, prompt)
        except Exception:
            del _JOBS[task_id]
            raise


def _execute(task_id, settings, reference_paths, prompt):
    with _LOCK:
        job = _JOBS[task_id]
        waited = time.monotonic() - job["created"]
        if waited > _MAX_QUEUE_SECONDS:
            job.update(status="error", error="排队时间过长，任务未提交到上游，请稍后重试。", finished=time.monotonic())
            _log(f"Web image queue expired: task={task_id}, model={settings.image_model}, queue={waited:.2f}s", "ERROR")
            return
        job.update(status="running", started=time.monotonic())
    _log(f"Web image started: task={task_id}, model={settings.image_model}, queue={waited:.2f}s")
    token = _IMAGE_JOB_ID.set(task_id)
    def report_stage(stage):
        with _LOCK:
            job["status"] = stage
    stage_token = _IMAGE_JOB_STAGE.set(report_stage)
    try:
        result = run_multi_reference_generation_web(settings, reference_paths, prompt)
    except Exception as exc:
        message = str(exc)
        for key in settings.provider_keys.values():
            if key:
                message = message.replace(key, "[REDACTED]")
        if isinstance(exc, (requests.exceptions.RequestException, TimeoutError, ConnectionError, Urllib3Error)):
            message = f"上游连接中断或超时，任务可能已计费；请先检查平台账单和历史记录再重试。详情：{message}"
        with _LOCK:
            job.update(status="error", error=message[:500], finished=time.monotonic())
        _log(f"Web image task failed: task={task_id}, model={settings.image_model}, elapsed={time.monotonic()-job['started']:.2f}s, error={type(exc).__name__}: {message[:500]}", "ERROR")
    else:
        with _LOCK:
            job.update(status="success", result=result, finished=time.monotonic())
        _log(f"Web image task finished: task={task_id}, model={settings.image_model}, elapsed={time.monotonic()-job['started']:.2f}s")
    finally:
        _IMAGE_JOB_STAGE.reset(stage_token)
        _IMAGE_JOB_ID.reset(token)


def status(task_id, session_id):
    with _LOCK:
        _prune(time.monotonic())
        job = _JOBS.get(task_id)
        if not job or job["session"] != session_id:
            return None
        if job["status"] == "queued" and time.monotonic() - job["created"] > _MAX_QUEUE_SECONDS:
            if job["future"].cancel():
                job.update(status="error", error="排队时间过长，任务未提交到上游，请稍后重试。", finished=time.monotonic())
                _log(f"Web image queue expired: task={task_id}, model={job['model']}", "ERROR")
        result = {"status": job["status"], "elapsed_seconds": int(time.monotonic() - job["created"])}
        if "result" in job:
            result["result"] = job["result"]
        if "error" in job:
            result["error"] = job["error"]
        return result
