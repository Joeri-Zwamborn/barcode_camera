import importlib.util
from pathlib import Path
import sys
import threading
import types
import unittest
from unittest.mock import Mock, patch

import numpy as np


class CameraRigTests(unittest.TestCase):
    def setUp(self):
        cv2 = types.ModuleType('cv2')
        cv2.INTER_LINEAR, cv2.FONT_HERSHEY_SIMPLEX, cv2.LINE_AA = 1, 0, 16
        cv2.resize = Mock(side_effect=lambda image, size, interpolation: np.full((size[1], size[0], 3), image[0, 0], dtype=np.uint8))
        cv2.rectangle, cv2.putText = Mock(), Mock()
        cv2.hconcat = lambda tiles: np.concatenate(tiles, axis=1)
        cv2.vconcat = lambda tiles: np.concatenate(tiles, axis=0)
        camera_module = types.ModuleType('camera')
        self.factory = camera_module.Camera = Mock()
        with patch.dict(sys.modules, {'cv2': cv2, 'camera': camera_module}):
            spec = importlib.util.spec_from_file_location('tested_camera_rig',
                Path(__file__).resolve().parents[1] / 'barcode_camera' / 'camera_rig.py')
            self.module = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(self.module)
        self.front, self.side = Mock(), Mock()
        self.front.failure_event = threading.Event()
        self.side.failure_event = threading.Event()
        self.factory.side_effect = [self.front, self.side]
        self.stop = threading.Event()
        self.configuration = [{'name': 'front', 'source': '/dev/front'}, {'name': 'side', 'source': '/dev/side'}]

    def test_every_camera_gets_its_own_capture_and_shared_stop_signal(self):
        rig = self.module.CameraRig(self.configuration, self.stop)
        self.assertEqual([call.args for call in self.factory.call_args_list], [('/dev/front', self.stop), ('/dev/side', self.stop)])
        self.assertEqual(rig.get_frames(), [('front', self.front.get_frame.return_value), ('side', self.side.get_frame.return_value)])
        rig.close()
        self.front.close.assert_called_once()
        self.side.close.assert_called_once()

    def test_startup_failure_closes_already_started_cameras(self):
        self.factory.side_effect = [self.front, RuntimeError('second camera failed')]
        with self.assertRaises(RuntimeError):
            self.module.CameraRig(self.configuration, self.stop)
        self.front.close.assert_called_once()

    def test_failure_in_any_capture_thread_is_reported(self):
        rig = self.module.CameraRig(self.configuration, self.stop)
        self.assertFalse(rig.failure_event.is_set())
        self.side.failure_event.set()
        self.assertTrue(rig.failure_event.is_set())

    def test_cleanup_continues_even_if_one_camera_cannot_close(self):
        rig = self.module.CameraRig(self.configuration, self.stop)
        self.front.close.side_effect = RuntimeError('blocked driver')
        rig.close()
        self.side.close.assert_called_once()
        self.assertTrue(rig.failure_event.is_set())

    def test_single_camera_keeps_existing_preview_and_multicamera_uses_one_mosaic(self):
        rig = self.module.CameraRig(self.configuration, self.stop)
        rig.run_preview()
        self.front.run_preview.assert_called_once_with(frame_provider=rig.preview_frame)
        self.side.run_preview.assert_not_called()
        self.factory.side_effect = [self.front]
        self.front.run_preview.reset_mock()
        single = self.module.CameraRig(self.configuration[:1], self.stop)
        single.run_preview()
        self.front.run_preview.assert_called_once_with()

    def test_preview_labels_missing_camera_without_modifying_original_frame(self):
        rig = self.module.CameraRig(self.configuration, self.stop)
        original = np.full((480, 640, 3), 100, dtype=np.uint8)
        self.front.get_frame.return_value = original
        self.side.get_frame.return_value = None
        mosaic = rig.preview_frame()
        self.assertEqual(mosaic.shape, (480, 1280, 3))
        self.assertTrue(np.all(mosaic[:, :640] == 100))
        self.assertTrue(np.all(mosaic[:, 640:] == 0))
        self.assertTrue(np.all(original == 100))
        self.assertIn('side: unavailable', self.module.cv2.putText.call_args_list[1].args[1])

    def test_odd_camera_count_pads_the_grid_and_all_missing_still_renders(self):
        third = Mock()
        third.get_frame.return_value = None
        self.front.get_frame.return_value = self.side.get_frame.return_value = None
        self.factory.side_effect = [self.front, self.side, third]
        rig = self.module.CameraRig(self.configuration + [{'name': 'top', 'source': 2}], self.stop)
        self.assertEqual(rig.preview_frame().shape, (960, 1280, 3))


if __name__ == '__main__':
    unittest.main()
