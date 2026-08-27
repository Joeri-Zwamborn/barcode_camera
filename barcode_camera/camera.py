import cv2
import threading
import logging
import os
import time
from rate_limit import PerSecondRateLimit

logger = logging.getLogger(__name__)
read_logger = logging.getLogger(f"{__name__}.frame_read")
read_logger.addFilter(PerSecondRateLimit(max_messages=1))

class Camera:
    WINDOW_NAME = "Barcode Camera"

    def __init__(self, index, stop_event):

        self.cap = cv2.VideoCapture(index, cv2.CAP_V4L2)

        if not self.cap.isOpened():
            logger.error("Failed to open camera")
            raise RuntimeError("Cannot open camera")

        self.frame = None
        self.preview_available = False
        self.next_preview_check = 0.0
        self.lock = threading.Lock()
        self.stop_event = stop_event
        self.running = True

        threading.Thread(target=self._loop, daemon=True).start()

    def _display_is_available(self):
        if not os.path.exists("/tmp/.X11-unix/X0"):
            return False
        os.environ["DISPLAY"] = ":0"
        os.environ["XAUTHORITY"] = "/home/admin/.Xauthority"

        if self.preview_available:
            return True
        
        if time.monotonic() - self.next_preview_check < 5.0:
            return self.preview_available
        
        self.next_preview_check = time.monotonic()

        if not self.preview_available:
            try:
                cv2.namedWindow(self.WINDOW_NAME, cv2.WINDOW_NORMAL)
                cv2.setWindowProperty(
                    self.WINDOW_NAME,
                    cv2.WND_PROP_FULLSCREEN,
                    cv2.WINDOW_FULLSCREEN,
                )
                cv2.waitKey(1)
                self.preview_available = True

            except cv2.error:
                logger.warning("Display not available for preview. Continuing without preview.")
                self.preview_available = False

            return self.preview_available

    def _loop(self):

        while self.running:
            ok, frame = self.cap.read()

            if not ok:
                read_logger.warning("Could not read frame from camera")
                continue

            if self._display_is_available():
                cv2.imshow(self.WINDOW_NAME, frame)
                if cv2.waitKey(1) & 0xFF == ord("`"):
                    logger.info("Exiting camera loop due to backtick key press.")
                    self.stop_event.set()
                    self.running = False
                    break
            with self.lock:
                self.frame = frame.copy()

    def get_frame(self):

        with self.lock:

            if self.frame is None:
                return None

            return self.frame.copy()

    def close(self):

        self.running = False
        self.cap.release()
        if self.preview_available:
            cv2.destroyAllWindows()
