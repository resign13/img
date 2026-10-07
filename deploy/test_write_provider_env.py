import json
import tempfile
import unittest
from pathlib import Path

from write_provider_env import write_provider_env


class WriteProviderEnvTests(unittest.TestCase):
    def test_replaces_platform_keys_and_removes_legacy_values(self):
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / ".env"
            config_file = Path(folder) / "desktop_app" / "data" / "config.json"
            config_file.parent.mkdir(parents=True)
            config_file.write_text('{"img_key":"old","llm_key":"old","image_model":"gemini2"}', encoding="utf-8")
            path.write_text(
                "OTHER_KEY=keep\nLLM_KEY=old\nIMG_KEY=old\nWEB_APIYI_KEY=old\n",
                encoding="utf-8",
            )
            environment = {
                "SECRET_WEB_APIYI_KEY": "new-a",
                "SECRET_WEB_MEINIANDA_KEY": "new-m",
                "SECRET_WEB_G_AISC_KEY": "new-g",
                "SECRET_WEB_GPT_IMAGE25_KEY": "new-gpt",
            }
            write_provider_env(path, environment)
            result = path.read_text(encoding="utf-8")
            self.assertIn("OTHER_KEY=keep", result)
            self.assertIn("WEB_APIYI_KEY=new-a", result)
            self.assertIn("WEB_MEINIANDA_KEY=new-m", result)
            self.assertIn("WEB_G_AISC_KEY=new-g", result)
            self.assertIn("WEB_GPT_IMAGE25_KEY=new-gpt", result)
            self.assertNotIn("LLM_KEY=", result)
            self.assertNotIn("IMG_KEY=", result)
            self.assertNotIn("=old", result)
            self.assertEqual(
                json.loads(config_file.read_text(encoding="utf-8")),
                {"image_model": "gemini2"},
            )

    def test_missing_secret_keeps_existing_file(self):
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / ".env"
            path.write_text("OTHER_KEY=keep\n", encoding="utf-8")
            with self.assertRaises(ValueError):
                write_provider_env(path, {"SECRET_WEB_APIYI_KEY": "only-one"})
            self.assertEqual(path.read_text(encoding="utf-8"), "OTHER_KEY=keep\n")


if __name__ == "__main__":
    unittest.main()
