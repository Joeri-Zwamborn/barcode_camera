import logging
from logging.handlers import RotatingFileHandler
from pathlib import Path
import signal
import sys
import threading
import datetime
import uuid

from camera_rig import CameraRig
from scanner import BarcodeScanner
from storage import save_image, start_upload_worker
from config import CAMERAS
from notifications import PhotoNotifications

LOG_FILE_PATH = Path(__file__).resolve().parent.parent / "main.log"
logger = logging.getLogger(__name__)


def configure_logging():
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] pid=%(process)d %(name)s: %(message)s",
        handlers=[
            RotatingFileHandler(LOG_FILE_PATH, maxBytes=1024 * 1024, backupCount=5),
            logging.StreamHandler(),
        ],
    )


def scan_loop(camera, scanner, stop_event, failure_event, notifications=None):
    try:
        for barcode in scanner:
            if stop_event.is_set():
                break
            frames = camera.get_frames()
            missing = [name for name, frame in frames if frame is None]
            if not frames or missing:
                logger.warning("Scan rejected: no fresh frame from %s; rescan when cameras recover", ", ".join(missing) or "any camera")
                if notifications is not None:
                    notifications.capture_failed(barcode, "Camera unavailable - rescan when ready")
                continue
            capture_id = uuid.uuid4().hex
            captured_at = datetime.datetime.now()
            saved = 0
            for name, frame in frames:
                if save_image(barcode, frame, camera_name=name, capture_id=capture_id, captured_at=captured_at):
                    saved += 1
                else:
                    logger.error("Photo could not be saved for camera %s, capture %s", name, capture_id)
            if saved == len(frames):
                if notifications is not None:
                    notifications.photo_saved(barcode)
            else:
                logger.error("Incomplete capture %s: saved %s/%s photos; rescan required", capture_id, saved, len(frames))
                if notifications is not None:
                    notifications.capture_failed(barcode, f"Saved {saved}/{len(frames)} photos - rescan required")
        if not stop_event.is_set():
            raise RuntimeError("Scanner stopped unexpectedly")
    except Exception:
        logger.exception("Scanner loop failed")
        failure_event.set()
        stop_event.set()


def main():
    camera = None
    upload_worker = None
    scanner_thread = None
    notifications = None
    stop_event = threading.Event()
    failure_event = threading.Event()
    previous_handlers = {}
    exit_code = 0
    configure_logging()
    logger.info("Starting barcode scanning.")

    def request_shutdown(signum, frame):
        logger.info("Shutdown requested by signal %s", signum)
        stop_event.set()

    try:
        for signum in (signal.SIGTERM, signal.SIGINT):
            previous_handlers[signum] = signal.signal(signum, request_shutdown)
        camera = CameraRig(CAMERAS, stop_event)
        scanner = BarcodeScanner(stop_event)
        upload_worker = start_upload_worker(stop_event)
        notifications = PhotoNotifications(stop_event)
        scanner_thread = threading.Thread(
            target=scan_loop,
            args=(camera, scanner, stop_event, failure_event, notifications),
            daemon=True,
        )
        scanner_thread.start()
        camera.run_preview()
        if failure_event.is_set() or camera.failure_event.is_set():
            exit_code = 1
    except Exception:
        logger.exception("An error occurred while scanning barcodes.")
        exit_code = 1
    finally:
        stop_event.set()
        if scanner_thread is not None:
            scanner_thread.join(timeout=2)
        if upload_worker is not None:
            upload_worker.join(timeout=5)
        if notifications is not None:
            notifications.close()
        if camera is not None:
            camera.close()
        if failure_event.is_set() or (camera is not None and camera.failure_event.is_set()):
            exit_code = 1
        logger.info("Camera closed. Exiting program.")
        for signum, handler in previous_handlers.items():
            signal.signal(signum, handler)
    return exit_code


if __name__ == "__main__":
    sys.exit(main())
