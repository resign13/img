import os
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from flask import Flask, request

BACKEND_DIR = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(BACKEND_DIR))

from app import web_config  # noqa: E402
from app.services.config_service import get_public_config  # noqa: E402
from app.services.request_parsers import parse_generation_settings  # noqa: E402


class ProviderKeyTests(unittest.TestCase):
    def setUp(self):
        self.app = Flask(__name__)

    def test_each_model_uses_its_own_server_key(self):
        values = {
            "WEB_APIYI_KEY": "apiyi-test",
            "WEB_MEINIANDA_KEY": "meinianda-test",
            "WEB_G_AISC_KEY": "g-aisc-test",
            "WEB_GPT_IMAGE25_KEY": "gpt-image25-test",
            "LLM_KEY": "legacy-llm",
            "IMG_KEY": "legacy-image",
        }
        with patch.dict(os.environ, values), patch(
            "core.data_manager.load_json_data", return_value={"img_key": "old-default", "llm_key": "old-default"}
        ):
            for label, model in web_config.IMAGE_MODELS.items():
                provider = web_config.provider_for_model(model)
                if not provider:
                    continue
                with self.subTest(label=label), self.app.test_request_context(
                    "/api/test", method="POST", data={"image_model": label}
                ):
                    settings = parse_generation_settings(request)
                    self.assertEqual(settings.effective_image_key, {
                        "apiyi": "apiyi-test",
                        "meinianda": "meinianda-test",
                        "g_aisc": "g-aisc-test",
                        "gpt_image_25": "gpt-image25-test",
                    }[provider])
                    self.assertEqual(settings.llm_key, "apiyi-test")
                    self.assertNotIn("key_override", settings.model_config)

    def test_public_status_does_not_expose_key_values(self):
        values = {
            "WEB_APIYI_KEY": "apiyi-test",
            "WEB_MEINIANDA_KEY": "",
            "WEB_G_AISC_KEY": "g-aisc-test",
            "WEB_GPT_IMAGE25_KEY": "gpt-image25-test",
        }
        with patch.dict(os.environ, values), patch(
            "core.data_manager.load_json_data", return_value={}
        ):
            result = get_public_config()
        self.assertEqual(result["key_status"], {
            "apiyi_key_configured": True,
            "meinianda_key_configured": False,
            "g_aisc_key_configured": True,
            "gpt_image_25_key_configured": True,
        })
        self.assertNotIn("apiyi-test", str(result))
        self.assertNotIn("g-aisc-test", str(result))
        self.assertNotIn("gpt-image25-test", str(result))

    def test_flare_does_not_fall_back_to_general_meinianda_key(self):
        values = {"WEB_MEINIANDA_KEY": "meinianda-test", "WEB_GPT_IMAGE25_KEY": ""}
        with patch.dict(os.environ, values), patch("core.data_manager.load_json_data", return_value={}):
            with self.app.test_request_context("/api/test", method="POST", data={
                "image_model": "meinianda gpt-image-2.6-flare",
            }):
                settings = parse_generation_settings(request)
        self.assertEqual(settings.effective_image_key, "")

    def test_public_models_exclude_removed_models_and_replace_old_default(self):
        with patch("core.data_manager.load_json_data", return_value={"image_model": "gpt-image-2.5-sunburst"}):
            result = get_public_config()
        labels = {model["label"] for model in result["models"]}
        self.assertIn("API易 gpt-image-2.6-all", labels)
        self.assertIn("meinianda gpt-image-2.6-flare", labels)
        self.assertTrue(labels.isdisjoint({"API易 gpt-image-2.5-all", "API易 gpt-image-2.5-vip",
                                          "gpt-image-2.5-sunburst", "kuai便宜banana2", "kuai便宜banana pro"}))
        self.assertIn(result["defaults"]["image_model"], labels)


if __name__ == "__main__":
    unittest.main()
