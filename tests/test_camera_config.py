import importlib.util
from pathlib import Path
import unittest

spec = importlib.util.spec_from_file_location('camera_config', Path(__file__).resolve().parents[1] / 'barcode_camera' / 'camera_config.py')
camera_config = importlib.util.module_from_spec(spec)
spec.loader.exec_module(camera_config)


class CameraConfigTests(unittest.TestCase):
    def test_legacy_configuration_works_and_stable_path_takes_precedence(self):
        self.assertEqual(camera_config.parse_cameras({'camera': {'index': 0}}), [{'name': 'camera1', 'source': 0}])
        self.assertEqual(camera_config.parse_cameras({'camera': {'index': 0, 'device': '/dev/v4l/by-id/test'}})[0]['source'], '/dev/v4l/by-id/test')

    def test_multiple_named_cameras_keep_configuration_order(self):
        result = camera_config.parse_cameras({'cameras': [{'name': 'front', 'device': '/dev/front'}, {'name': 'side', 'index': 2}]})
        self.assertEqual(result, [{'name': 'front', 'source': '/dev/front'}, {'name': 'side', 'source': 2}])

    def test_invalid_ambiguous_and_duplicate_configurations_fail_early(self):
        for config in [None, {'cameras': []}, {'cameras': {}}, {'camera': {}, 'cameras': [{}]},
                       {'cameras': [None]}, {'cameras': [{'name': '../escape', 'index': 0}]},
                       {'cameras': [{'name': 'front', 'index': 0}, {'name': 'FRONT', 'index': 1}]},
                       {'cameras': [{'name': 'front', 'index': 0}, {'name': 'side', 'index': 0}]},
                       {'cameras': [{'index': 0}, {'device': '/dev/video0'}]},
                       {'camera': {'index': -1}}, {'camera': {'index': True}}, {'camera': {'index': '0'}},
                       {'camera': {'device': False}}, {'camera': {'device': ' /dev/video0 '}}]:
            with self.subTest(config=config), self.assertRaises((ValueError, KeyError)):
                camera_config.parse_cameras(config)


if __name__ == '__main__':
    unittest.main()
