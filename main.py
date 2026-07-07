from camera import Camera
from scanner import BarcodeScanner
from storage import save_image

from config import CAMERA_INDEX

camera = Camera(CAMERA_INDEX)

scanner = BarcodeScanner()

print("Ready.")

for barcode in scanner:

    frame = camera.get_frame()

    if frame is None:
        continue

    save_image(barcode, frame)
