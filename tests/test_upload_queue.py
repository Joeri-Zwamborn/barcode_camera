import importlib.util
import sys
import uuid
import threading
import types
import unittest
from pathlib import Path
from unittest.mock import Mock, patch


class ResourceExistsError(Exception):
    pass


class UploadQueueTests(unittest.TestCase):
    def setUp(self):
        directory = Path(__file__).resolve().parent / f"queue-test-{uuid.uuid4().hex}"
        directory.mkdir()
        self.directory = types.SimpleNamespace(name=str(directory))
        def cleanup():
            for file in directory.iterdir():
                file.unlink()
            directory.rmdir()
        self.addCleanup(cleanup)
        modules = {}
        for name in ('cv2', 'config', 'barcodes', 'azure', 'azure.core', 'azure.core.exceptions',
                     'azure.identity', 'azure.storage', 'azure.storage.blob'):
            modules[name] = types.ModuleType(name)
        barcode_spec = importlib.util.spec_from_file_location('barcodes',
            Path(__file__).resolve().parents[1] / 'barcode_camera' / 'barcodes.py')
        barcode_spec.loader.exec_module(modules['barcodes'])
        modules['config'].LOCAL_SAVE_DIR = self.directory.name
        modules['config'].AZURE_ENABLED = True
        modules['config'].AZURE = {'container': 'photos'}
        modules['cv2'].imencode = Mock(return_value=(True, Mock(tobytes=lambda: b'photo')))
        modules['azure.core.exceptions'].ResourceExistsError = ResourceExistsError
        modules['azure.identity'].ClientSecretCredential = Mock()
        modules['azure.storage.blob'].BlobServiceClient = Mock()
        with patch.dict(sys.modules, modules):
            spec = importlib.util.spec_from_file_location('queue_storage',
                Path(__file__).resolve().parents[1] / 'barcode_camera' / 'storage.py')
            self.storage = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(self.storage)
        self.service = Mock()
        self.stop = threading.Event()

    def test_capture_does_not_upload_and_names_are_unique(self):
        with patch.object(self.storage, 'upload_to_azure') as upload:
            self.assertTrue(self.storage.save_image('123', object()))
            self.assertTrue(self.storage.save_image('123', object()))
            upload.assert_not_called()
        self.assertEqual(len(list(Path(self.directory.name).glob('*.png'))), 2)
        self.assertEqual(list(Path(self.directory.name).glob('*.pending')), [])

    def test_failed_upload_survives_and_later_retry_removes_file(self):
        photo = Path(self.directory.name) / 'old.png'
        photo.write_bytes(b'photo')
        blob = self.service.get_blob_client.return_value
        blob.upload_blob.side_effect = OSError('offline')
        self.storage.upload_pending_once(self.stop, self.service)
        self.assertTrue(photo.exists())
        blob.upload_blob.side_effect = None
        self.storage.upload_pending_once(self.stop, self.service)
        self.assertFalse(photo.exists())

    def test_existing_blob_is_verified_before_local_deletion(self):
        photo = Path(self.directory.name) / 'old.png'
        photo.write_bytes(b'photo')
        blob = self.service.get_blob_client.return_value
        blob.upload_blob.side_effect = ResourceExistsError()
        blob.download_blob.return_value.chunks.return_value = [b'other photo']
        self.storage.upload_pending_once(self.stop, self.service)
        self.assertTrue(photo.exists())
        blob.download_blob.return_value.chunks.return_value = [b'photo']
        self.storage.upload_pending_once(self.stop, self.service)
        self.assertFalse(photo.exists())

    def test_partial_file_is_ignored_and_stop_prevents_upload(self):
        (Path(self.directory.name) / 'partial.pending').write_bytes(b'incomplete')
        self.storage.upload_pending_once(self.stop, self.service)
        self.service.get_blob_client.assert_not_called()
        (Path(self.directory.name) / 'complete.png').write_bytes(b'photo')
        self.stop.set()
        self.storage.upload_pending_once(self.stop, self.service)
        self.service.get_blob_client.assert_not_called()

    def test_failed_save_does_not_publish_png(self):
        self.storage.cv2.imencode.return_value = (False, None)
        self.assertFalse(self.storage.save_image('123', object()))
        self.assertEqual(list(Path(self.directory.name).iterdir()), [])

    def test_local_only_mode_does_not_start_worker(self):
        self.storage.AZURE_ENABLED = False
        self.assertIsNone(self.storage.start_upload_worker(self.stop))
        self.assertTrue(self.storage.save_image('123', object()))

    def test_invalid_barcodes_never_write_or_encode_a_photo(self):
        for barcode in ('', '../escape', '/absolute', 'a/b', 'a\\b', '..',
                        'abc\x00', 'abc\n', 'a b', 'a:b', 'a*', 'é123',
                        'a' * 129, None, 123):
            with self.subTest(barcode=barcode):
                self.assertFalse(self.storage.save_image(barcode, object()))
        self.storage.cv2.imencode.assert_not_called()
        self.assertEqual(list(Path(self.directory.name).iterdir()), [])

    def test_valid_barcodes_preserve_searchable_text(self):
        for barcode in ('0123456789', 'AbC-123_4.5', 'a' * 128):
            self.assertTrue(self.storage.save_image(barcode, object()))
            self.assertEqual(len(list(Path(self.directory.name).glob(barcode + '_*.png'))), 1)

    def test_resolved_path_outside_directory_is_rejected(self):
        directory = Path(self.directory.name)
        original = Path.resolve
        def resolve(path, *args, **kwargs):
            if path.suffix == '.png':
                return directory.parent / 'outside.png'
            return original(path, *args, **kwargs)
        with patch.object(Path, 'resolve', resolve):
            self.assertFalse(self.storage.save_image('123', object()))
        self.storage.cv2.imencode.assert_not_called()
        self.assertEqual(list(directory.iterdir()), [])


if __name__ == '__main__':
    unittest.main()
