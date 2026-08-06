from camera import Camera
from scanner import BarcodeScanner
from storage import save_image
import logging
from config import CAMERA_INDEX

logging.basicConfig(level=logging.INFO)
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
