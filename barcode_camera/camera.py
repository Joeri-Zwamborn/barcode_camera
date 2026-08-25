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
    QUIT_BUTTON_WIDTH = 20
    QUIT_BUTTON_HEIGHT = 20
    QUIT_BUTTON_MARGIN = 20

    def __init__(self, index, stop_event):

        self.cap = cv2.VideoCapture(index, cv2.CAP_V4L2)

        if not self.cap.isOpened():
            logger.error("Failed to open camera")
            raise RuntimeError("Cannot open camera")

        self.frame = None
        self.frame_width = 0
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
                cv2.setMouseCallback(self.WINDOW_NAME, self._handle_mouse_event)
                cv2.waitKey(1)
                self.preview_available = True

            except cv2.error:
                logger.warning("Display not available for preview. Continuing without preview.")
                self.preview_available = False

            return self.preview_available

    def _handle_mouse_event(self, event, x, y, flags, parameters):
        if event != cv2.EVENT_LBUTTONDOWN:
            return

        if not self.frame_width:
            return

        x_start = self.frame_width - self.QUIT_BUTTON_WIDTH - self.QUIT_BUTTON_MARGIN
        y_start = self.QUIT_BUTTON_MARGIN

        if x_start <= x <= x_start + self.QUIT_BUTTON_WIDTH and y_start <= y <= y_start + self.QUIT_BUTTON_HEIGHT:
            logger.info("Quit button clicked.")
            self.stop_event.set()
            self.running = False

    def _draw_quit_button(self, frame):
        self.frame_width = frame.shape[1]
        x_start = self.frame_width - self.QUIT_BUTTON_WIDTH - self.QUIT_BUTTON_MARGIN
        y_start = self.QUIT_BUTTON_MARGIN
        x_end = x_start + self.QUIT_BUTTON_WIDTH
        y_end = y_start + self.QUIT_BUTTON_HEIGHT

        cv2.rectangle(frame, (x_start, y_start), (x_end, y_end), (240, 240, 255), -1)
        cv2.putText(
            frame,
            "",
            (x_start + 10, y_start + 30),
            cv2.FONT_HERSHEY_SIMPLEX,
            0.5,
            (255, 255, 255),
            2,
            cv2.LINE_AA,
        )
        
    def _loop(self):

        while self.running:
            ok, frame = self.cap.read()

            if not ok:
                read_logger.warning("Could not read frame from camera")
                continue

            if self._display_is_available():
                preview_frame = frame.copy()
                self._draw_quit_button(preview_frame)
                cv2.imshow(self.WINDOW_NAME, preview_frame)
                if cv2.waitKey(1) & 0xFF == ord('q'):
                    logger.info("Exiting camera loop due to 'q' key press.")
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
