import json
from pathlib import Path
import sys
import unittest
from unittest.mock import Mock, patch

import requests

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from app import web_config
from app.services import image_client


class UpstreamErrorTests(unittest.TestCase):
    key = "sk-current-test-secret"

    def response(self, payload, headers=None):
        response = requests.Response()
        response.status_code = 477
        response.headers.update(headers or {})
        response.encoding = "utf-8"
        body = json.dumps(payload).encode() if isinstance(payload, dict) else payload.encode()
        response.raw = Mock()
        response.raw._connection = None
        response.raw._fp = None
        response.raw.read1.side_effect = [body, b""]
        return response

    def generate_failure(self, response):
        model = web_config.IMAGE_MODELS["API易 gpt-image-2.6-all"]
        with patch.object(image_client.requests, "post", return_value=response) as post, patch.object(image_client, "_log") as log:
            with self.assertRaises(RuntimeError) as raised:
                image_client.generate_image("cat", self.key, "1:1", [], "unused", model_config=model)
            post.assert_called_once()
        return str(raised.exception), "\n".join(call.args[0] for call in log.call_args_list)

    def test_failure_logs_only_allowed_metadata_and_redacts_current_key(self):
        response = self.response({
            "error": {
                "message": f"upstream rejected {self.key}",
                "type": f"image_failure_{self.key}",
                "code": 477,
                "param": f"reference_{self.key}",
                "other": "ignored-error-field",
            },
            "data": [{"b64_json": "ignored-base64-body"}],
        }, {
            "X-Request-ID": f"request-{self.key}",
            "Request-ID": "gateway-request-2",
            "X-OneAPI-Request-ID": "oneapi-request-3",
            "Authorization": "ignored-authorization-header",
            "X-Other": "ignored-other-header",
        })
        error, logs = self.generate_failure(response)
        self.assertIn("[request_id: request-[REDACTED]]", error)
        self.assertIn("upstream rejected [REDACTED]", error)
        for expected in (
            '"x-request-id": "request-[REDACTED]"',
            '"request-id": "gateway-request-2"',
            '"x-oneapi-request-id": "oneapi-request-3"',
            '"error.type": "image_failure_[REDACTED]"',
            '"error.code": "477"',
            '"error.param": "reference_[REDACTED]"',
        ):
            self.assertIn(expected, logs)
        for forbidden in (self.key, "ignored-error-field", "ignored-base64-body",
                          "ignored-authorization-header", "Authorization", "ignored-other-header"):
            self.assertNotIn(forbidden, logs + error)

    def test_request_id_aliases_are_returned_when_other_metadata_is_absent(self):
        for header in ("x-request-id", "request-id", "x-oneapi-request-id"):
            with self.subTest(header=header):
                response = self.response({"error": {"message": "upstream failed"}}, {header: "correlation-123"})
                error, logs = self.generate_failure(response)
                self.assertIn("[request_id: correlation-123]", error)
                self.assertIn(f'"{header}": "correlation-123"', logs)

    def test_failure_without_error_message_does_not_dump_response_body(self):
        for payload in (
            f"raw-response-body {self.key}",
            {"data": [{"b64_json": "raw-response-body"}],
             "error": {"param": {"Authorization": self.key}}},
        ):
            with self.subTest(payload_type=type(payload).__name__):
                response = self.response(payload, {"X-Request-ID": "request-456"})
                error, logs = self.generate_failure(response)
                self.assertIn("Upstream returned no error message.", error)
                self.assertIn("[request_id: request-456]", error)
                for forbidden in (self.key, "raw-response-body", "b64_json", "Authorization"):
                    self.assertNotIn(forbidden, logs + error)


if __name__ == "__main__":
    unittest.main()
