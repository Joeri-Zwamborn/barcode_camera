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
        cv2.error = RuntimeError
        cv2.INTER_LINEAR = 1
        cv2.BORDER_CONSTANT = 0
        cv2.getWindowImageRect = Mock()
        cv2.resize = Mock()
        cv2.copyMakeBorder = Mock()
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

    def test_disabled_preview_does_not_open_a_window(self):
        self.module.cv2.namedWindow = Mock()
        with patch.dict(self.module.os.environ, {'BARCODE_CAMERA_PREVIEW': 'off'}):
            self.assertFalse(self.camera._display_is_available())
        self.module.cv2.namedWindow.assert_not_called()

    def test_preview_scales_to_monitor_without_distorting_capture(self):
        frame = types.SimpleNamespace(shape=(480, 640, 3))
        self.module.cv2.getWindowImageRect.return_value = (0, 0, 1920, 1080)
        result = self.camera._fit_preview_frame(frame)
        self.module.cv2.resize.assert_called_once_with(frame, (1440, 1080), interpolation=1)
        self.module.cv2.copyMakeBorder.assert_called_once_with(
            self.module.cv2.resize.return_value, 0, 0, 240, 240, 0, value=(0, 0, 0))
        self.assertIs(result, self.module.cv2.copyMakeBorder.return_value)
        self.assertEqual(frame.shape, (480, 640, 3))

    def test_preview_uses_original_if_window_size_is_not_available(self):
        frame = types.SimpleNamespace(shape=(480, 640, 3))
        self.module.cv2.getWindowImageRect.return_value = (0, 0, 0, 0)
        self.assertIs(self.camera._fit_preview_frame(frame), frame)
        self.module.cv2.getWindowImageRect.side_effect = RuntimeError('unsupported')
        self.assertIs(self.camera._fit_preview_frame(frame), frame)
        self.module.cv2.resize.assert_not_called()

    def test_missing_desktop_credentials_does_not_open_a_window(self):
        self.module.cv2.namedWindow = Mock()
        with patch.dict(self.module.os.environ, {}, clear=True), patch.object(self.module.Path, 'home', return_value=Path('/home/plisse')), patch.object(self.module.os.path, 'exists', return_value=True), patch.object(self.module.os.path, 'isfile', return_value=False):
            self.assertFalse(self.camera._display_is_available())
        self.module.cv2.namedWindow.assert_not_called()

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
        with patch.object(self.module.Path, 'resolve', return_value='/dev/video3'):
            self.camera._loop()
        self.module.cv2.VideoCapture.assert_called_once_with(3, 200)

    def test_device_path_is_resolved_again_after_reconnect(self):
        self.camera.index = '/dev/v4l/by-id/usb-C270-video-index0'
        missing, available = Mock(), Mock()
        missing.isOpened.return_value = False
        available.isOpened.return_value = True
        self.module.cv2.VideoCapture.side_effect = [missing, available]
        def read():
            self.stop.set()
            return False, None
        available.read.side_effect = read
        with patch.object(self.module.Path, 'resolve', side_effect=['/dev/video0', '/dev/video2']), patch.object(self.stop, 'wait', return_value=False):
            self.camera._loop()
        self.assertEqual(self.module.cv2.VideoCapture.call_args_list, [((0, 200),), ((2, 200),)])

    def test_missing_device_path_does_not_fall_back_to_another_camera(self):
        self.camera.index = '/dev/v4l/by-id/usb-missing-video-index0'
        with patch.object(self.module.Path, 'resolve', side_effect=FileNotFoundError('disconnected')), patch.object(self.stop, 'wait', side_effect=lambda timeout: self.stop.set()):
            self.camera._loop()
        self.module.cv2.VideoCapture.assert_not_called()

    def test_non_video_device_path_is_rejected(self):
        self.camera.index = '/dev/v4l/by-id/usb-invalid-video-index0'
        with patch.object(self.module.Path, 'resolve', return_value='/dev/null'), patch.object(self.stop, 'wait', side_effect=lambda timeout: self.stop.set()):
            self.camera._loop()
        self.module.cv2.VideoCapture.assert_not_called()

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
