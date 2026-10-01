import importlib.util
from pathlib import Path
import sys
import threading
import types
import unittest
from unittest.mock import Mock, patch

ROOT = Path(__file__).resolve().parents[1]


class ScannerValidationTests(unittest.TestCase):
    def scan(self, codes):
        config = types.ModuleType('config')
        config.SCANNER_DEVICE = '/dev/input/test'
        barcodes = types.ModuleType('barcodes')
        spec = importlib.util.spec_from_file_location('barcodes', ROOT / 'barcode_camera' / 'barcodes.py')
        spec.loader.exec_module(barcodes)
        evdev = types.ModuleType('evdev')
        device = Mock(fd=1)
        device.read.return_value = [types.SimpleNamespace(type=1, code=code) for code in codes]
        evdev.InputDevice = Mock(return_value=device)
        evdev.ecodes = types.SimpleNamespace(EV_KEY=1)
        evdev.categorize = lambda event: types.SimpleNamespace(
            keycode=event.code, keystate=1, key_down=1, key_up=0)
        with patch.dict(sys.modules, {'config': config, 'barcodes': barcodes, 'evdev': evdev}):
            spec = importlib.util.spec_from_file_location('tested_scanner', ROOT / 'barcode_camera' / 'scanner.py')
            scanner_module = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(scanner_module)
        stop = threading.Event()
        calls = 0
        def select(*args):
            nonlocal calls
            calls += 1
            if calls == 1:
                return [1], [], []
            stop.set()
            return [], [], []
        with patch.object(scanner_module.select, 'select', side_effect=select):
            return list(scanner_module.BarcodeScanner(stop))

    def test_oversized_scan_is_discarded_and_next_scan_works(self):
        codes = ['KEY_1'] * 129 + ['KEY_ENTER', 'KEY_2', 'KEY_ENTER']
        self.assertEqual(self.scan(codes), ['2'])

    def test_invalid_scan_is_discarded_and_next_scan_works(self):
        codes = ['KEY_DOT', 'KEY_DOT', 'KEY_SLASH', 'KEY_1', 'KEY_ENTER', 'KEY_2', 'KEY_ENTER']
        self.assertEqual(self.scan(codes), ['2'])

    def test_maximum_length_barcode_is_accepted(self):
        self.assertEqual(self.scan(['KEY_1'] * 128 + ['KEY_ENTER']), ['1' * 128])


if __name__ == '__main__':
    unittest.main()
