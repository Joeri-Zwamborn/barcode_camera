import threading
from camera import Camera
from scanner import BarcodeScanner
from storage import save_image
from config import CAMERA_INDEX
import logging
from logging.handlers import RotatingFileHandler
from pathlib import Path

LOG_FILE_PATH = Path(__file__).resolve().parent.parent / "main.log"

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] pid=%(process)d %(name)s: %(message)s",
    handlers=[
        RotatingFileHandler(LOG_FILE_PATH, maxBytes=1024*1024, backupCount=5),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)


logger.info("Starting barcode scanning.")

def scan_loop(camera, scanner, stop_event):
        try:
            for barcode in scanner:
                if stop_event.is_set():
                    break
                frame = camera.get_frame()
                if frame is not None:
                    save_image(barcode, frame)
                    continue
                    
        except Exception:
            logger.exception("Scanner loop failed")
            stop_event.set()

def main():
    camera = None
    stop_event = threading.Event()
    try:
        camera = Camera(CAMERA_INDEX, stop_event)
        scanner = BarcodeScanner(stop_event)

        scanner_thread = threading.Thread(target=scan_loop, args=(camera, scanner, stop_event), daemon=True)
        scanner_thread.start()

        camera.run_preview()
        scanner_thread.join()

    except Exception:
        logger.exception("An error occurred while scanning barcodes.")

    finally:
        if camera is not None:
            camera.close()
        logging.info("Camera closed. Exiting program.")

if __name__ == "__main__":
    main()
