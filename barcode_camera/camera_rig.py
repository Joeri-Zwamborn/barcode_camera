"""Independent camera capture threads with one combined preview."""
import logging
import math
import threading

import cv2
import numpy as np
from camera import Camera

logger = logging.getLogger(__name__)


class CameraRig:
    def __init__(self, configurations, stop_event):
        self.cameras = []
        self._failure_event = threading.Event()
        try:
            for entry in configurations:
                logger.info("Starting camera %s: %r", entry["name"], entry["source"])
                self.cameras.append((entry["name"], Camera(entry["source"], stop_event)))
        except Exception:
            self.close()
            raise

    @property
    def failure_event(self):
        if any(camera.failure_event.is_set() for _, camera in self.cameras):
            self._failure_event.set()
        return self._failure_event

    def get_frames(self):
        # Snapshot every camera before saving/encoding any photo.
        return [(name, camera.get_frame()) for name, camera in self.cameras]

    def preview_frame(self):
        frames = self.get_frames()
        columns = math.ceil(math.sqrt(len(frames)))
        rows = math.ceil(len(frames) / columns)
        tiles = []
        for name, frame in frames:
            tile = np.zeros((480, 640, 3), dtype=np.uint8)
            if frame is not None:
                height, width = frame.shape[:2]
                scale = min(640 / width, 480 / height)
                width, height = max(1, round(width * scale)), max(1, round(height * scale))
                resized = cv2.resize(frame, (width, height), interpolation=cv2.INTER_LINEAR)
                x, y = (640 - width) // 2, (480 - height) // 2
                tile[y:y + height, x:x + width] = resized
            label = name if frame is not None else f"{name}: unavailable - rescan when ready"
            cv2.rectangle(tile, (0, 0), (640, 36), (0, 0, 0), -1)
            cv2.putText(tile, label, (10, 25), cv2.FONT_HERSHEY_SIMPLEX, 0.55,
                        (255, 255, 255) if frame is not None else (80, 80, 255), 1, cv2.LINE_AA)
            tiles.append(tile)
        while len(tiles) < rows * columns:
            tiles.append(np.zeros((480, 640, 3), dtype=np.uint8))
        return cv2.vconcat([cv2.hconcat(tiles[row * columns:(row + 1) * columns]) for row in range(rows)])

    def run_preview(self):
        primary = self.cameras[0][1]
        if len(self.cameras) == 1:
            primary.run_preview()
        else:
            primary.run_preview(frame_provider=self.preview_frame)

    def close(self):
        for name, camera in self.cameras:
            try:
                camera.close()
            except Exception:
                logger.exception("Could not close camera %s", name)
                self._failure_event.set()
