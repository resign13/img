import base64
import io
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import Mock, patch

from flask import Flask, request
from PIL import Image

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from app import web_config
from app.services import image_client
from app.services.config_service import get_public_config
from app.services.gpt_image import build_size
from app.services.request_parsers import parse_generation_settings


class ImageRatioTests(unittest.TestCase):
    def test_registry_has_channel_specific_capabilities(self):
        models = web_config.IMAGE_MODELS
        for label in ('nano banana2', 'API易 Nano Banana 2.1', 'kuai稳定banana2'):
            self.assertEqual(len(models[label]['allowed_ratios']), 14)
            self.assertIn('1:8', models[label]['allowed_ratios'])
        for label in ('gemini2', 'gemini pro', '企业t3nano banana2', '企业t3nano banana pro', 'nano banana pro', 'kuai稳定banana pro'):
            self.assertEqual(len(models[label]['allowed_ratios']), 10)
            self.assertIn('4:5', models[label]['allowed_ratios'])
        self.assertEqual(len(models['gemini-nano-banana-2.1']['allowed_ratios']), 11)
        self.assertNotIn('1:8', models['gemini-nano-banana-2.1']['allowed_ratios'])
        for label in ('API易 gpt-image-2.6-all', 'meinianda gpt-image-2.6-flare'):
            self.assertEqual(len(models[label]['allowed_ratios']), 15)
            self.assertEqual(models[label]['custom_ratio_max'], 3)

    def test_public_config_exposes_custom_limits_and_new_presets(self):
        with patch('core.data_manager.load_json_data', return_value={
                'image_model': 'meinianda gpt-image-2.6-flare', 'ratio': '7:5'}):
            config = get_public_config()
        self.assertEqual(config['defaults']['ratio'], '7:5')
        self.assertTrue({'1:2', '2:1', '1:3', '3:1', '9:21'} <= {option['value'] for option in config['ratio_options']})
        flare = next(model for model in config['models'] if model['label'] == 'meinianda gpt-image-2.6-flare')
        self.assertEqual(flare['custom_ratio_max'], 3)

    def test_parser_preserves_valid_custom_ratio_and_rejects_unsupported_ratio(self):
        app = Flask(__name__)
        with patch('core.data_manager.load_json_data', return_value={}):
            for label, raw, expected in (
                ('meinianda gpt-image-2.6-flare', '7：5', '7:5'),
                ('API易 gpt-image-2.6-all', '3:1', '3:1'),
                ('gemini2', '4:5', '4:5'),
            ):
                with app.test_request_context(method='POST', data={'image_model': label, 'ratio_label': raw}):
                    settings = parse_generation_settings(request)
                    self.assertEqual(settings.ratio_value, expected)
            for label, ratio in (
                ('gemini2', '1:8'), ('gemini-nano-banana-2.1', '8:1'),
                ('meinianda gpt-image-2.6-flare', '4:1'),
                ('meinianda gpt-image-2.6-flare', '0:1'),
                ('meinianda gpt-image-2.6-flare', 'invalid'),
            ):
                with app.test_request_context(method='POST', data={'image_model': label, 'ratio_label': ratio}):
                    with self.assertRaisesRegex(ValueError, '比例'):
                        parse_generation_settings(request)

    def test_custom_flare_ratio_reaches_upstream_payload(self):
        buffer = io.BytesIO()
        Image.new('RGB', (16, 16), 'blue').save(buffer, format='PNG')
        response = Mock(status_code=200)
        response.raw._connection = None
        response.raw._fp = None
        response.raw.read1.return_value = b''
        response.json.return_value = {'data': [{'b64_json': base64.b64encode(buffer.getvalue()).decode()}]}
        with tempfile.TemporaryDirectory() as folder, patch.object(image_client.requests, 'post', return_value=response) as post:
            image_client.generate_image('circle', 'fake-key', '7:5', [], folder,
                                        model_config=web_config.IMAGE_MODELS['meinianda gpt-image-2.6-flare'])
        self.assertEqual(post.call_args.kwargs['json']['size'], '1008x720')

    def test_apiyi_boundary_sizes_stay_inside_three_to_one(self):
        for ratio in ('1:3', '3:1'):
            for resolution in ('1K', '2K', '4K'):
                width, height = map(int, build_size(ratio, resolution, 'apiyi_26').split('x'))
                self.assertEqual(max(width, height), 3 * min(width, height))


if __name__ == '__main__':
    unittest.main()
