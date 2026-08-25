from camera import Camera
from scanner import BarcodeScanner
from storage import save_image
from config import CAMERA_INDEX
import logging
import threading
from logging.handlers import RotatingFileHandler
from pathlib import Path

LOG_FILE_PATH = Path(__file__).resolve().parent.parent / "main.log"

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    handlers=[
        RotatingFileHandler(LOG_FILE_PATH, maxBytes=1024*1024, backupCount=5),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)


def close_scanner_when_stopped(stop_event, scanner):
    stop_event.wait()
    scanner.close()


logger.info("Starting barcode scanning.")

def main():
    camera = None
    stop_event = threading.Event()
    try:
        camera = Camera(CAMERA_INDEX, stop_event)
        scanner = BarcodeScanner(stop_event)
        threading.Thread(
            target=close_scanner_when_stopped,
            args=(stop_event, scanner),
            daemon=True,
        ).start()
        for barcode in scanner:
            if stop_event.is_set():
                break
            frame = camera.get_frame()
            if frame is None:
                continue
            save_image(barcode, frame)
    except Exception:
        logger.exception("An error occurred while scanning barcodes.")

    finally:
        if camera is not None:
            camera.close()
        logging.info("Camera closed. Exiting program.")

if __name__ == "__main__":
    main()
