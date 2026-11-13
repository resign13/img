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
    def test_apiyi_banana21_edit_uses_shared_protocol(self):
        from core import apiyi_banana21
        model = web_config.IMAGE_MODELS[apiyi_banana21.LABEL]
        self.response.json.return_value = {'candidates': [{'content': {'parts': [
            {'text': 'done'}, {'inlineData': {'mimeType': 'image/png', 'data': base64.b64encode(self.image_bytes).decode()}}]}}]}
        with tempfile.TemporaryDirectory() as folder:
            reference = Path(folder) / 'ref.png'
            reference.write_bytes(self.image_bytes)
            with patch.dict('os.environ', {'APIYI_API_KEY': ''}), patch.object(image_client.requests, 'post', return_value=self.response) as post:
                output = image_client.generate_image('edit', 'web-key', '1:8', [str(reference)], folder, image_size='2K', model_config=model)
            self.assertEqual(Path(output).read_bytes(), self.image_bytes)
        kwargs = post.call_args.kwargs
        self.assertEqual(kwargs['timeout'], 360)
        self.assertEqual(kwargs['headers']['Authorization'], 'Bearer web-key')
        parts = kwargs['json']['contents'][0]['parts']
        self.assertEqual([list(p) for p in parts], [['text'], ['inlineData']])
        self.assertEqual(len(model['allowed_ratios']), 14)
        self.assertNotIn('512', model['allowed_resolutions'])

    def setUp(self):
        buffer = io.BytesIO()
        Image.new('RGB', (16, 16), 'blue').save(buffer, format='PNG')
        self.image_bytes = buffer.getvalue()
        self.response = Mock(status_code=200)
        self.response.raw._connection = None
        self.response.raw._fp = None
        self.response.raw.read1.return_value = b""
        self.response.json.return_value = {'data': [{'b64_json': base64.b64encode(self.image_bytes).decode()}]}
        self.model = web_config.IMAGE_MODELS['meinianda gpt-image-2.6-flare']
        self.apiyi_model = web_config.IMAGE_MODELS['API易 gpt-image-2.6-all']

    def test_gpt_text_generation_uses_json_and_dedicated_key(self):
        with tempfile.TemporaryDirectory() as output, patch.object(image_client.requests, 'post', return_value=self.response) as post:
            result = image_client.generate_image('kitten', 'gpt-key', '9:16', [], output,
                                                  image_size='1K', model_config=self.model)
            self.assertEqual(Path(result).read_bytes(), self.image_bytes)
        kwargs = post.call_args.kwargs
        self.assertTrue(post.call_args.args[0].endswith('/images/generations'))
        self.assertEqual(kwargs['headers']['Authorization'], 'Bearer gpt-key')
        self.assertEqual(kwargs['json']['model'], 'gpt-image-2.6-flare')
        self.assertEqual(kwargs['json']['size'], '720x1280')
        self.assertEqual(kwargs['json']['response_format'], 'b64_json')
        self.assertEqual(kwargs['timeout'], 600)
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
        for model, env_name in ((self.model, 'WEB_GPT_IMAGE25_KEY'), (self.apiyi_model, 'WEB_APIYI_KEY')):
            with self.subTest(model=model['model']), patch.object(image_client.requests, 'post') as post:
                with self.assertRaisesRegex(ValueError, env_name):
                    image_client.generate_image('kitten', '', '1:1', [], 'unused', model_config=model)
                post.assert_not_called()

    def _set_apiyi_response_size(self, size, reported_size=None):
        buffer = io.BytesIO()
        Image.new('RGB', size, 'blue').save(buffer, format='PNG')
        self.response.json.return_value = {'data': [{
            'b64_json': base64.b64encode(buffer.getvalue()).decode(),
            'size': reported_size or f'{size[0]}x{size[1]}',
        }]}

    def test_apiyi_text_generation_sends_native_size_and_explicit_parameters(self):
        self._set_apiyi_response_size((1024, 576))
        with tempfile.TemporaryDirectory() as output, patch.object(image_client.requests, 'post', return_value=self.response) as post:
            result = image_client.generate_image('kitten', 'apiyi-key', '16:9', [], output,
                                                  image_size='1K', model_config=self.apiyi_model)
            with Image.open(result) as image:
                self.assertEqual(image.size, (1024, 576))
        self.assertEqual(post.call_args.args[0], 'https://api.apiyi.com/v1/images/generations')
        kwargs = post.call_args.kwargs
        self.assertEqual(kwargs['headers']['Authorization'], 'Bearer apiyi-key')
        self.assertEqual(kwargs['json'], {
            'model': 'gpt-image-2.6-all', 'prompt': 'kitten', 'size': '1024x576',
            'quality': 'high', 'output_format': 'png', 'response_format': 'b64_json',
        })
        self.assertEqual(kwargs['timeout'], 600)
        post.assert_called_once()

    def test_apiyi_edit_uses_multipart_with_all_references(self):
        self._set_apiyi_response_size((2048, 1536))
        with tempfile.TemporaryDirectory() as output:
            refs = [Path(output) / f'ref{i}.png' for i in range(2)]
            for path in refs:
                path.write_bytes(self.image_bytes)
            with patch.object(image_client.requests, 'post', return_value=self.response) as post:
                image_client.generate_image('edit', 'apiyi-key', '4:3', list(map(str, refs)), output,
                                              image_size='2K', model_config=self.apiyi_model)
        self.assertEqual(post.call_args.args[0], 'https://api.apiyi.com/v1/images/edits')
        kwargs = post.call_args.kwargs
        self.assertEqual(kwargs['data']['size'], '2048x1536')
        self.assertEqual(kwargs['data']['response_format'], 'b64_json')
        self.assertEqual(len(kwargs['files']), 2)
        self.assertTrue(all(name == 'image[]' and content[1].closed for name, content in kwargs['files']))

    def test_apiyi_4k_square_blocks_network(self):
        with patch.object(image_client.requests, 'post') as post:
            with self.assertRaisesRegex(ValueError, '2K'):
                image_client.generate_image('kitten', 'apiyi-key', '1:1', [], 'unused',
                                              image_size='4K', model_config=self.apiyi_model)
            post.assert_not_called()

    def test_apiyi_wrong_actual_or_reported_size_is_rejected_before_compression(self):
        for actual_size, reported_size in (((16, 16), '1024x1024'), ((1024, 1024), '2048x2048')):
            with self.subTest(actual_size=actual_size, reported_size=reported_size), tempfile.TemporaryDirectory() as output:
                self._set_apiyi_response_size(actual_size, reported_size)
                with patch.object(image_client.requests, 'post', return_value=self.response), patch.object(image_client.utils, 'compress_image_smart') as compress:
                    with self.assertRaisesRegex(RuntimeError, '返回尺寸不符'):
                        image_client.generate_image('kitten', 'apiyi-key', '1:1', [], output,
                                                      compress_enabled=True, model_config=self.apiyi_model)
                    compress.assert_not_called()
                self.assertEqual(list(Path(output).iterdir()), [])

    def test_apiyi_sizes_preserve_requested_resolution(self):
        self.assertEqual(build_size('3:2', '1K', 'apiyi_26'), '1024x683')
        self.assertEqual(build_size('21:9', '1K', 'apiyi_26'), '1024x439')
        self.assertEqual(build_size('16:9', '2K', 'apiyi_26'), '2048x1152')
        self.assertEqual(build_size('16:9', '4K', 'apiyi_26'), '3840x2160')
        self.assertEqual(build_size('1:1', '2K', 'apiyi_26'), '2048x2048')

    def test_model_registry_and_all_gpt_sizes(self):
        self.assertEqual(web_config.provider_for_model(self.model), 'gpt_image_25')
        self.assertEqual(web_config.provider_for_model(self.apiyi_model), 'apiyi')
        self.assertEqual(web_config.provider_for_model(web_config.IMAGE_MODELS['gemini-nano-banana-2.1']), 'meinianda')
        self.assertNotIn('gpt-image-2', web_config.IMAGE_MODELS)
        for label in ('API易 gpt-image-2.5-all', 'API易 gpt-image-2.5-vip', 'gpt-image-2.5-sunburst',
                      'kuai便宜banana2', 'kuai便宜banana pro'):
            self.assertNotIn(label, web_config.IMAGE_MODELS)
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
