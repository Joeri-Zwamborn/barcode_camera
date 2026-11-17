import importlib.util
import signal
import sys
import threading
import types
import unittest
from pathlib import Path
from unittest.mock import Mock, patch

ROOT = Path(__file__).resolve().parents[1]


class ServiceRecoveryTests(unittest.TestCase):
    def setUp(self):
        modules = {name: types.ModuleType(name) for name in ('camera_rig', 'scanner', 'storage', 'config', 'notifications')}
        modules['notifications'].PhotoNotifications = Mock()
        modules['camera_rig'].CameraRig = Mock()
        modules['scanner'].BarcodeScanner = Mock()
        modules['storage'].save_image = Mock(return_value=True)
        modules['storage'].start_upload_worker = Mock(return_value=None)
        modules['config'].CAMERAS = [{'name': 'camera1', 'source': 0}]
        with patch.dict(sys.modules, modules):
            spec = importlib.util.spec_from_file_location('tested_main', ROOT / 'barcode_camera' / 'main.py')
            self.main = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(self.main)
        self.logging_patch = patch.object(self.main, 'configure_logging')
        self.logging_patch.start()
        self.addCleanup(self.logging_patch.stop)

    def test_scanner_exception_signals_failure(self):
        def broken_scanner():
            raise OSError('Scanner unplugged')
            yield
        stop, failed = threading.Event(), threading.Event()
        self.main.scan_loop(Mock(), broken_scanner(), stop, failed)
        self.assertTrue(stop.is_set())
        self.assertTrue(failed.is_set())

    def test_popup_only_follows_a_successful_local_save(self):
        for saved in (True, False):
            with self.subTest(saved=saved):
                stop, failed = threading.Event(), threading.Event()
                notifications = Mock()
                camera = Mock()
                camera.get_frames.return_value = [('camera1', object())]
                self.main.save_image.return_value = saved
                def scans():
                    yield '00123'
                    stop.set()
                self.main.scan_loop(camera, scans(), stop, failed, notifications)
                if saved:
                    notifications.photo_saved.assert_called_once_with('00123')
                else:
                    notifications.photo_saved.assert_not_called()
                self.assertFalse(failed.is_set())

    def test_rejected_scan_does_not_show_a_success_popup(self):
        stop, failed = threading.Event(), threading.Event()
        camera, notifications = Mock(), Mock()
        camera.get_frames.return_value = [('camera1', None)]
        def scans():
            yield '00123'
            stop.set()
        self.main.scan_loop(camera, scans(), stop, failed, notifications)
        notifications.photo_saved.assert_not_called()
        self.main.save_image.assert_not_called()

    def test_unexpected_scanner_end_signals_failure(self):
        stop, failed = threading.Event(), threading.Event()
        self.main.scan_loop(Mock(), iter([]), stop, failed)
        self.assertTrue(failed.is_set())

    def scan_once(self, frames, results):
        camera, notifications = Mock(), Mock()
        camera.get_frames.return_value = frames
        self.main.save_image.side_effect = results
        stop, failed = threading.Event(), threading.Event()
        def scans():
            yield '00123'
            stop.set()
        self.main.scan_loop(camera, scans(), stop, failed, notifications)
        self.assertFalse(failed.is_set())
        return notifications

    def test_one_scan_saves_all_cameras_with_shared_identifier_and_timestamp(self):
        front, side = object(), object()
        notifications = self.scan_once([('front', front), ('side', side)], [True, True])
        calls = self.main.save_image.call_args_list
        self.assertEqual([call.args for call in calls], [('00123', front), ('00123', side)])
        self.assertEqual([call.kwargs['camera_name'] for call in calls], ['front', 'side'])
        self.assertEqual(calls[0].kwargs['capture_id'], calls[1].kwargs['capture_id'])
        self.assertEqual(calls[0].kwargs['captured_at'], calls[1].kwargs['captured_at'])
        notifications.photo_saved.assert_called_once_with('00123')
        notifications.capture_failed.assert_not_called()

    def test_missing_camera_prevents_partial_capture_and_reports_failure(self):
        notifications = self.scan_once([('front', object()), ('side', None)], [])
        self.main.save_image.assert_not_called()
        notifications.photo_saved.assert_not_called()
        notifications.capture_failed.assert_called_once()

    def test_partial_disk_failure_attempts_other_cameras_but_never_claims_success(self):
        notifications = self.scan_once([('front', object()), ('side', object()), ('top', object())], [True, False, True])
        self.assertEqual(self.main.save_image.call_count, 3)
        notifications.photo_saved.assert_not_called()
        notifications.capture_failed.assert_called_once_with('00123', 'Saved 2/3 photos - rescan required')

    def test_each_scan_gets_a_new_capture_identifier(self):
        self.scan_once([('front', object()), ('side', object())], [True, True])
        first_id = self.main.save_image.call_args_list[0].kwargs['capture_id']
        self.main.save_image.reset_mock()
        self.scan_once([('front', object()), ('side', object())], [True, True])
        self.assertNotEqual(first_id, self.main.save_image.call_args_list[0].kwargs['capture_id'])

    def test_rescan_after_camera_recovery_captures_only_the_new_item(self):
        camera, notifications = Mock(), Mock()
        camera.get_frames.side_effect = [
            [('front', object()), ('side', None)],
            [('front', object()), ('side', object())],
        ]
        stop, failed = threading.Event(), threading.Event()
        def scans():
            yield 'missing-camera-item'
            yield 'rescanned-item'
            stop.set()
        self.main.scan_loop(camera, scans(), stop, failed, notifications)
        self.assertFalse(failed.is_set())
        self.assertEqual(self.main.save_image.call_count, 2)
        self.assertTrue(all(call.args[0] == 'rescanned-item' for call in self.main.save_image.call_args_list))
        notifications.capture_failed.assert_called_once()
        notifications.photo_saved.assert_called_once_with('rescanned-item')

    def test_scanner_startup_failure_exits_nonzero_and_closes_camera(self):
        camera = self.main.CameraRig.return_value
        camera.failure_event = threading.Event()
        self.main.BarcodeScanner.side_effect = OSError('Missing scanner')
        self.assertEqual(self.main.main(), 1)
        camera.close.assert_called_once()

    def test_camera_startup_failure_exits_nonzero(self):
        self.main.CameraRig.side_effect = RuntimeError('Camera initialization failed')
        self.assertEqual(self.main.main(), 1)

    def test_sigterm_exits_cleanly_and_restores_handler(self):
        original = signal.getsignal(signal.SIGTERM)
        camera = self.main.CameraRig.return_value
        camera.failure_event = threading.Event()
        camera.run_preview.side_effect = lambda: signal.getsignal(signal.SIGTERM)(signal.SIGTERM, None)
        with patch.object(self.main.threading, 'Thread'):
            self.assertEqual(self.main.main(), 0)
        self.assertEqual(signal.getsignal(signal.SIGTERM), original)
        camera.close.assert_called_once()

    def test_camera_worker_failure_exits_nonzero(self):
        camera = self.main.CameraRig.return_value
        camera.failure_event = threading.Event()
        camera.failure_event.set()
        with patch.object(self.main.threading, 'Thread'):
            self.assertEqual(self.main.main(), 1)

    def test_runtime_scanner_failure_exits_nonzero(self):
        camera = self.main.CameraRig.return_value
        camera.failure_event = threading.Event()
        self.main.BarcodeScanner.return_value = iter([])
        def thread(target, args, daemon):
            return types.SimpleNamespace(start=lambda: target(*args), join=Mock())
        with patch.object(self.main.threading, 'Thread', side_effect=thread):
            self.assertEqual(self.main.main(), 1)

    def test_service_template_uses_checkout_and_account(self):
        spec = importlib.util.spec_from_file_location('renderer', ROOT / 'scripts' / 'render_service.py')
        renderer = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(renderer)
        unit = renderer.render_service(ROOT, 'admin')
        self.assertIn('User=admin', unit)
        self.assertIn('Restart=on-failure', unit)
        self.assertIn('RestartSec=5', unit)
        self.assertNotIn('@APP_DIRECTORY@', unit)
        self.assertIn(renderer.quote_path(ROOT / 'venv' / 'bin' / 'python'), unit)
        working_directory = next(line for line in unit.splitlines() if line.startswith('WorkingDirectory='))
        self.assertEqual(working_directory, 'WorkingDirectory=' + str(ROOT).replace('%', '%%'))
        with self.assertRaises(ValueError):
            renderer.render_service(ROOT, 'root')


if __name__ == '__main__':
    unittest.main()
