import cv2
import threading

class Camera:

    def __init__(self, index):

        self.cap = cv2.VideoCapture(index, cv2.CAP_V4L2)

        if not self.cap.isOpened():
            raise RuntimeError("Cannot open camera")

        self.frame = None
        self.lock = threading.Lock()
        self.running = True

        threading.Thread(target=self._loop, daemon=True).start()

    def _loop(self):

        while self.running:

            ok, frame = self.cap.read()

            if ok:
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
