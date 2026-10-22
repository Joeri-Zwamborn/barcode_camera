import importlib.util
from pathlib import Path
import sys
import threading
import types
import unittest
from unittest.mock import Mock, patch


class NotificationTests(unittest.TestCase):
    def setUp(self):
        spec = importlib.util.spec_from_file_location('tested_notifications',
            Path(__file__).resolve().parents[1] / 'barcode_camera' / 'notifications.py')
        self.module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(self.module)
        self.stop = threading.Event()
        with patch.object(self.module.threading, 'Thread'):
            self.notifications = self.module.PhotoNotifications(self.stop)

    def test_rapid_scans_keep_the_latest_pending_confirmation(self):
        self.notifications.photo_saved('first')
        self.notifications.photo_saved('second')
        self.assertEqual(self.notifications.pending.qsize(), 1)
        self.assertEqual(self.notifications.pending.get_nowait(), 'second')

    def test_gui_process_failure_does_not_escape_the_worker(self):
        self.notifications.photo_saved('00123')
        def failed_popup(*args, **kwargs):
            self.stop.set()
            return types.SimpleNamespace(returncode=-6)
        with patch.object(self.module.subprocess, 'run', side_effect=failed_popup):
            self.notifications._run()
        self.assertTrue(self.notifications.warned)

    def test_popup_is_bottom_right_and_closes_automatically(self):
        root = Mock()
        root.winfo_screenwidth.return_value = 1920
        root.winfo_screenheight.return_value = 1080
        tk = types.ModuleType('tkinter')
        tk.Tk = Mock(return_value=root)
        tk.Label = Mock()
        with patch.dict(sys.modules, {'tkinter': tk}):
            self.module.show_popup('00123')
        root.geometry.assert_called_once_with('360x110+1536+946')
        root.after.assert_called_once_with(2200, root.destroy)
        root.focus_force.assert_not_called()


if __name__ == '__main__':
    unittest.main()
