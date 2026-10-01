import importlib.util
import sys
import threading
import types
import unittest
from pathlib import Path
from unittest.mock import Mock, patch


class CameraRecoveryTests(unittest.TestCase):
    def setUp(self):
        cv2 = types.ModuleType('cv2')
        cv2.CAP_V4L2 = 200
        cv2.VideoCapture = Mock()
        rate_limit = types.ModuleType('rate_limit')
        spec = importlib.util.spec_from_file_location('rate_limit',
            Path(__file__).resolve().parents[1] / 'barcode_camera' / 'rate_limit.py')
        spec.loader.exec_module(rate_limit)
        with patch.dict(sys.modules, {'cv2': cv2, 'rate_limit': rate_limit}):
            spec = importlib.util.spec_from_file_location('tested_camera',
                Path(__file__).resolve().parents[1] / 'barcode_camera' / 'camera.py')
            self.module = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(self.module)
        self.stop = threading.Event()
        with patch.object(self.module.threading, 'Thread'):
            self.camera = self.module.Camera(0, self.stop)

    def test_fresh_frames_are_copied_and_stale_frames_rejected(self):
        frame = Mock()
        self.camera.frame = frame
        self.camera.frame_received_at = 100
        with patch.object(self.module.time, 'monotonic', return_value=100.5):
            self.assertIs(self.camera.get_frame(), frame.copy.return_value)
        with patch.object(self.module.time, 'monotonic', return_value=101.1):
            self.assertIsNone(self.camera.get_frame())
        self.stop.set()
        self.assertIsNone(self.camera.get_frame())

    def test_failures_clear_frame_and_reconnect_then_resume(self):
        first, second = Mock(), Mock()
        first.isOpened.return_value = second.isOpened.return_value = True
        self.module.cv2.VideoCapture.side_effect = [first, second]
        self.camera.frame = Mock()
        self.camera.frame_received_at = 100
        first.read.side_effect = [(False, None)] * 5
        recovered = Mock()
        reads = 0
        def next_frame():
            nonlocal reads
            reads += 1
            if reads == 1:
                self.assertIsNone(self.camera.get_frame())
                return True, recovered
            self.assertIsNotNone(self.camera.get_frame())
            self.stop.set()
            return False, None
        second.read.side_effect = next_frame
        with patch.object(self.stop, 'wait', return_value=False):
            self.camera._loop()
        self.assertEqual(self.module.cv2.VideoCapture.call_count, 2)
        first.release.assert_called_once()
        second.release.assert_called_once()
        self.assertIsNone(self.camera.frame)

    def test_missing_camera_at_startup_can_recover(self):
        missing, available = Mock(), Mock()
        missing.isOpened.return_value = False
        available.isOpened.return_value = True
        self.module.cv2.VideoCapture.side_effect = [missing, available]
        def read():
            self.stop.set()
            return False, None
        available.read.side_effect = read
        with patch.object(self.stop, 'wait', return_value=False):
            self.camera._loop()
        missing.release.assert_called_once()
        available.release.assert_called_once()
        self.assertEqual(self.module.cv2.VideoCapture.call_count, 2)

    def test_stable_device_path_is_used_when_opening_camera(self):
        device = '/dev/v4l/by-id/usb-C270-video-index0'
        self.camera.index = device
        capture = Mock()
        capture.isOpened.return_value = True
        self.module.cv2.VideoCapture.return_value = capture
        def read():
            self.stop.set()
            return False, None
        capture.read.side_effect = read
        self.camera._loop()
        self.module.cv2.VideoCapture.assert_called_once_with(device, 200)

    def test_read_exception_invalidates_frame(self):
        capture = Mock()
        capture.isOpened.return_value = True
        self.module.cv2.VideoCapture.return_value = capture
        self.camera.frame = Mock()
        self.camera.frame_received_at = 100
        capture.read.side_effect = OSError('disconnected')
        def stop_after_failure(timeout):
            self.assertIsNone(self.camera.frame)
            self.stop.set()
        with patch.object(self.stop, 'wait', side_effect=stop_after_failure):
            self.camera._loop()
        capture.release.assert_called_once()

    def test_unexpected_capture_thread_error_signals_application_failure(self):
        capture = Mock()
        capture.isOpened.return_value = True
        frame = Mock()
        frame.copy.side_effect = RuntimeError('Unexpected frame failure')
        capture.read.return_value = (True, frame)
        self.module.cv2.VideoCapture.return_value = capture
        self.camera._loop()
        self.assertTrue(self.camera.failure_event.is_set())
        self.assertTrue(self.stop.is_set())
        capture.release.assert_called_once()


if __name__ == '__main__':
    unittest.main()
