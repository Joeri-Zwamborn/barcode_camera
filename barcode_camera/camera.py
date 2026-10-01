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
    MAX_FRAME_AGE_SECONDS = 1.0
    MAX_READ_FAILURES = 5
    RECONNECT_SECONDS = 2.0

    def __init__(self, index, stop_event):

        self.index = index
        self.cap = None
        self.frame = None
        self.frame_received_at = None
        self.preview_available = False
        self.next_preview_check = 0.0
        self.lock = threading.Lock()
        self.stop_event = stop_event
        self.failure_event = threading.Event()
        self.running = True

        self.capture_thread = threading.Thread(target=self._loop, daemon=True)
        self.capture_thread.start()

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
        failures = 0
        try:
            while self.running and not self.stop_event.is_set():
                if self.cap is None:
                    try:
                        self.cap = cv2.VideoCapture(self.index, cv2.CAP_V4L2)
                        if not self.cap.isOpened():
                            raise RuntimeError("Cannot open camera")
                        logger.info("Camera connected")
                        failures = 0
                    except Exception:
                        read_logger.warning("Camera unavailable; will reconnect", exc_info=True)
                        self._invalidate_frame()
                        self._release_capture()
                        self.stop_event.wait(self.RECONNECT_SECONDS)
                        continue

                try:
                    ok, frame = self.cap.read()
                except Exception:
                    read_logger.warning("Error reading camera frame", exc_info=True)
                    ok, frame = False, None

                if not ok or frame is None:
                    self._invalidate_frame()
                    failures += 1
                    read_logger.warning("Could not read frame from camera")
                    if failures >= self.MAX_READ_FAILURES:
                        logger.warning("Repeated camera failures; reconnecting")
                        self._release_capture()
                        self.stop_event.wait(self.RECONNECT_SECONDS)
                    else:
                        self.stop_event.wait(0.1)
                    continue

                with self.lock:
                    self.frame = frame.copy()
                    self.frame_received_at = time.monotonic()
                failures = 0
        except Exception:
            logger.exception("Camera capture thread failed")
            self.failure_event.set()
            self.stop_event.set()
        finally:
            self._invalidate_frame()
            self._release_capture()

    def _invalidate_frame(self):
        with self.lock:
            self.frame = None
            self.frame_received_at = None

    def _release_capture(self):
        if self.cap is not None:
            self.cap.release()
            self.cap = None

    def run_preview(self):
        while not self.stop_event.is_set():
            if self._display_is_available():
                frame = self.get_frame()
                with self.lock:
                    if frame is not None:
                        cv2.imshow(self.WINDOW_NAME, frame)
                        if cv2.waitKey(1) & 0xFF == ord('`'):
                            logger.info("Stop event set. Exiting preview loop.")
                            self.stop_event.set()
                if frame is None:
                    cv2.waitKey(1)
                    self.stop_event.wait(0.05)
            else:
                time.sleep(0.01)

    def get_frame(self):

        with self.lock:

            if (self.frame is None or self.frame_received_at is None
                    or self.stop_event.is_set()
                    or time.monotonic() - self.frame_received_at > self.MAX_FRAME_AGE_SECONDS):
                return None

            return self.frame.copy()

    def close(self):

        self.running = False
        self.stop_event.set()
        self._invalidate_frame()
        self.capture_thread.join(timeout=2)
        if self.capture_thread.is_alive():
            logger.warning("Camera read is still blocked during shutdown")
        if self.preview_available:
            cv2.destroyAllWindows()
