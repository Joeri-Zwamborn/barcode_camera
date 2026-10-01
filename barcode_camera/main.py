import logging
from logging.handlers import RotatingFileHandler
from pathlib import Path
import signal
import sys
import threading

from camera import Camera
from scanner import BarcodeScanner
from storage import save_image, start_upload_worker
from config import CAMERA_INDEX

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


def scan_loop(camera, scanner, stop_event, failure_event):
    try:
        for barcode in scanner:
            if stop_event.is_set():
                break
            frame = camera.get_frame()
            if frame is not None:
                if not save_image(barcode, frame):
                    logger.error("Photo could not be saved for scanned barcode")
                continue
            logger.warning("Scan rejected: no fresh camera frame; rescan when camera recovers")
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
        camera = Camera(CAMERA_INDEX, stop_event)
        scanner = BarcodeScanner(stop_event)
        upload_worker = start_upload_worker(stop_event)
        scanner_thread = threading.Thread(
            target=scan_loop,
            args=(camera, scanner, stop_event, failure_event),
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
