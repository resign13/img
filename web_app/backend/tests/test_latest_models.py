import base64
import io
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import Mock, patch

from PIL import Image

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from app import web_config
from app.services import image_client
from app.services.gpt_image import build_size


class LatestModelTests(unittest.TestCase):
    def setUp(self):
        buffer = io.BytesIO()
        Image.new('RGB', (16, 16), 'blue').save(buffer, format='PNG')
        self.image_bytes = buffer.getvalue()
        self.response = Mock(status_code=200)
        self.response.json.return_value = {'data': [{'b64_json': base64.b64encode(self.image_bytes).decode()}]}
        self.model = web_config.IMAGE_MODELS['gpt-image-2.5-sunburst']

    def test_gpt_text_generation_uses_json_and_dedicated_key(self):
        with tempfile.TemporaryDirectory() as output, patch.object(image_client.requests, 'post', return_value=self.response) as post:
            result = image_client.generate_image('kitten', 'gpt-key', '9:16', [], output,
                                                  image_size='1K', model_config=self.model)
            self.assertEqual(Path(result).read_bytes(), self.image_bytes)
        kwargs = post.call_args.kwargs
        self.assertTrue(post.call_args.args[0].endswith('/images/generations'))
        self.assertEqual(kwargs['headers']['Authorization'], 'Bearer gpt-key')
        self.assertEqual(kwargs['json']['model'], 'gpt-image-2.5-sunburst')
        self.assertEqual(kwargs['json']['size'], '720x1280')
        self.assertNotIn('files', kwargs)
        post.assert_called_once()

    def test_gpt_edit_uploads_all_references_and_closes_handles(self):
        with tempfile.TemporaryDirectory() as output:
            refs = [Path(output) / f'ref{i}.png' for i in range(2)]
            for path in refs:
                path.write_bytes(self.image_bytes)
            with patch.object(image_client.requests, 'post', return_value=self.response) as post:
                image_client.generate_image('edit', 'gpt-key', '3:4', list(map(str, refs)), output,
                                              image_size='2K', model_config=self.model)
            self.assertTrue(post.call_args.args[0].endswith('/images/edits'))
            self.assertEqual(post.call_args.kwargs['data']['size'], '1536x2048')
            files = post.call_args.kwargs['files']
            self.assertEqual(len(files), 2)
            self.assertTrue(all(name == 'image[]' and content[1].closed for name, content in files))

    def test_missing_gpt_key_blocks_network(self):
        with patch.object(image_client.requests, 'post') as post:
            with self.assertRaisesRegex(ValueError, 'WEB_GPT_IMAGE25_KEY'):
                image_client.generate_image('kitten', '', '1:1', [], 'unused', model_config=self.model)
            post.assert_not_called()

    def test_model_registry_and_all_gpt_sizes(self):
        self.assertEqual(web_config.provider_for_model(self.model), 'gpt_image_25')
        self.assertEqual(web_config.provider_for_model(web_config.IMAGE_MODELS['gemini-nano-banana-2.1']), 'meinianda')
        self.assertNotIn('gpt-image-2', web_config.IMAGE_MODELS)
        for ratio in self.model['allowed_ratios']:
            for resolution in self.model['allowed_resolutions']:
                with self.subTest(ratio=ratio, resolution=resolution):
                    width, height = map(int, build_size(ratio, resolution).split('x'))
                    rw, rh = map(int, ratio.split(':'))
                    self.assertEqual(width * rh, height * rw)
                    self.assertEqual(width % 16, 0)
                    self.assertEqual(height % 16, 0)
                    self.assertLessEqual(max(width, height), 3840)
                    self.assertTrue(655360 <= width * height <= 8294400)

    def test_banana21_uses_native_endpoint_and_model_timeout(self):
        self.response.json.return_value = {'candidates': [{'content': {'parts': [{'inlineData': {
            'mimeType': 'image/png', 'data': base64.b64encode(self.image_bytes).decode()}}]}}]}
        model = web_config.IMAGE_MODELS['gemini-nano-banana-2.1']
        with tempfile.TemporaryDirectory() as output, patch.object(image_client.requests, 'post', return_value=self.response) as post:
            image_client.generate_image('kitten', 'mei-key', '16:9', [], output, image_size='4K', model_config=model)
        self.assertIn('/gemini-nano-banana-2.1:generateContent', post.call_args.args[0])
        self.assertEqual(post.call_args.kwargs['headers']['x-goog-api-key'], 'mei-key')
        self.assertEqual(post.call_args.kwargs['json']['generationConfig']['imageConfig'], {'imageSize': '4K', 'aspectRatio': '16:9'})
        self.assertEqual(post.call_args.kwargs['timeout'], 600)
