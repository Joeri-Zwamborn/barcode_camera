import logging
import threading
import time

class PerSecondRateLimit(logging.Filter):
        def __init__(self, max_messages: int, period_seconds: float = 1.0):
            super().__init__()
            self.max_messages = max_messages
            self.period_seconds = period_seconds
            self.message_count = 0
            self.window_started = time.monotonic()
            self.lock = threading.Lock()

        def filter(self, record: logging.LogRecord) -> bool:
            now = time.monotonic()
            with self.lock:
                if now - self.window_started >= self.period_seconds:
                    self.window_started = now
                    self.message_count = 0

                if self.message_count < self.max_messages:
                    self.message_count += 1
                    return True
                else:
                    return False
