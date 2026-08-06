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
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    handlers=[
        RotatingFileHandler(LOG_FILE_PATH, maxBytes=1024*1024, backupCount=5),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

print("Ready to scan barcodes. Please scan a barcode to capture an image.")
logger.info("Starting barcode scanning.")

def main():
    camera = Camera(CAMERA_INDEX)
    scanner = BarcodeScanner()
    try:
        for barcode in scanner:
            frame = camera.get_frame()
            if frame is None:
                continue
            save_image(barcode, frame)
    except Exception:
        logger.exception("An error occurred while scanning barcodes.")

    finally:
        camera.close()
        logging.info("Camera closed. Exiting program.")

if __name__ == "__main__":
    main()
