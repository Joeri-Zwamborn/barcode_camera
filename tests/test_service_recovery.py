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
        modules = {name: types.ModuleType(name) for name in ('camera', 'scanner', 'storage', 'config')}
        modules['camera'].Camera = Mock()
        modules['scanner'].BarcodeScanner = Mock()
        modules['storage'].save_image = Mock(return_value=True)
        modules['storage'].start_upload_worker = Mock(return_value=None)
        modules['config'].CAMERA_INDEX = 0
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

    def test_unexpected_scanner_end_signals_failure(self):
        stop, failed = threading.Event(), threading.Event()
        self.main.scan_loop(Mock(), iter([]), stop, failed)
        self.assertTrue(failed.is_set())

    def test_scanner_startup_failure_exits_nonzero_and_closes_camera(self):
        camera = self.main.Camera.return_value
        camera.failure_event = threading.Event()
        self.main.BarcodeScanner.side_effect = OSError('Missing scanner')
        self.assertEqual(self.main.main(), 1)
        camera.close.assert_called_once()

    def test_camera_startup_failure_exits_nonzero(self):
        self.main.Camera.side_effect = RuntimeError('Camera initialization failed')
        self.assertEqual(self.main.main(), 1)

    def test_sigterm_exits_cleanly_and_restores_handler(self):
        original = signal.getsignal(signal.SIGTERM)
        camera = self.main.Camera.return_value
        camera.failure_event = threading.Event()
        camera.run_preview.side_effect = lambda: signal.getsignal(signal.SIGTERM)(signal.SIGTERM, None)
        with patch.object(self.main.threading, 'Thread'):
            self.assertEqual(self.main.main(), 0)
        self.assertEqual(signal.getsignal(signal.SIGTERM), original)
        camera.close.assert_called_once()

    def test_camera_worker_failure_exits_nonzero(self):
        camera = self.main.Camera.return_value
        camera.failure_event = threading.Event()
        camera.failure_event.set()
        with patch.object(self.main.threading, 'Thread'):
            self.assertEqual(self.main.main(), 1)

    def test_runtime_scanner_failure_exits_nonzero(self):
        camera = self.main.Camera.return_value
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
        with self.assertRaises(ValueError):
            renderer.render_service(ROOT, 'root')


if __name__ == '__main__':
    unittest.main()
