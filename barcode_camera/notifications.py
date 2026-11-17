"""Best-effort desktop confirmations, isolated from the camera process."""
import logging
import os
from pathlib import Path
import queue
import subprocess
import sys
import threading

logger = logging.getLogger(__name__)


class PhotoNotifications:
    def __init__(self, stop_event):
        self.stop_event = stop_event
        self.pending = queue.Queue(maxsize=1)
        self.warned = False
        self.thread = threading.Thread(target=self._run, daemon=True)
        self.thread.start()

    def photo_saved(self, barcode):
        self._enqueue((barcode, "saved", ""))

    def capture_failed(self, barcode, detail):
        self._enqueue((barcode, "failed", detail))

    def _enqueue(self, notification):
        # Keep the latest confirmation rather than delaying scanning or building
        # up a backlog of old popups when operators scan quickly.
        try:
            self.pending.put_nowait(notification)
        except queue.Full:
            try:
                self.pending.get_nowait()
            except queue.Empty:
                pass
            try:
                self.pending.put_nowait(notification)
            except queue.Full:
                pass

    def _run(self):
        while not self.stop_event.is_set():
            try:
                barcode, status, detail = self.pending.get(timeout=0.2)
            except queue.Empty:
                continue
            if self.stop_event.is_set():
                break
            try:
                environment = os.environ.copy()
                environment.setdefault("DISPLAY", ":0")
                authority = Path.home() / ".Xauthority"
                if authority.is_file():
                    environment.setdefault("XAUTHORITY", str(authority))
                result = subprocess.run(
                    [sys.executable, str(Path(__file__).resolve()), "--popup", barcode, status, detail],
                    env=environment, stdout=subprocess.DEVNULL,
                    stderr=subprocess.DEVNULL, timeout=5, check=False,
                )
                if result.returncode:
                    raise RuntimeError("Desktop popup could not be displayed")
                self.warned = False
            except Exception:
                if not self.warned:
                    logger.warning("Desktop capture notification unavailable; check desktop access and python3-tk")
                    self.warned = True

    def close(self):
        self.thread.join(timeout=5.5)


def show_popup(barcode, status="saved", detail=""):
    # Tk owns its event loop in a child process. Even a native GUI failure cannot
    # terminate the scanner/camera service.
    import tkinter as tk

    root = tk.Tk()
    root.withdraw()
    root.overrideredirect(True)
    root.attributes("-topmost", True)
    width, height, margin = 360, 150 if detail else 110, 24
    x = max(0, root.winfo_screenwidth() - width - margin)
    y = max(0, root.winfo_screenheight() - height - margin)
    root.geometry(f"{width}x{height}+{x}+{y}")
    background = "#17633b" if status == "saved" else "#a32626"
    root.configure(background=background)
    tk.Label(root, text="Photos saved" if status == "saved" else "Capture incomplete", foreground="white", background=background,
             font=("sans-serif", 17, "bold")).pack(pady=(12, 3))
    tk.Label(root, text=barcode, foreground="white", background=background,
             font=("sans-serif", 11), wraplength=330).pack()
    if detail:
        tk.Label(root, text=detail, foreground="white", background=background,
                 font=("sans-serif", 11), wraplength=330).pack(pady=(4, 0))
    root.deiconify()
    # Do not call focus_force: the popup must not take keyboard focus.
    root.after(2200 if status == "saved" else 3500, root.destroy)
    root.mainloop()


if __name__ == "__main__":
    if len(sys.argv) in (3, 5) and sys.argv[1] == "--popup":
        try:
            show_popup(sys.argv[2], *(sys.argv[3:] if len(sys.argv) == 5 else []))
        except Exception:
            sys.exit(1)
