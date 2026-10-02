"""Capture de la fenetre du jeu via Windows Graphics Capture (marche meme si la fenetre est masquee)."""
import threading
import numpy as np
import cv2


def grab_window(title_part="PartyMu.NET", timeout=5.0):
    from windows_capture import WindowsCapture, Frame, InternalCaptureControl

    cap = WindowsCapture(cursor_capture=False, draw_border=False, window_name=title_part)
    out, done = {}, threading.Event()

    @cap.event
    def on_frame_arrived(frame: Frame, ctl: InternalCaptureControl):
        out["img"] = frame.frame_buffer[:, :, :3].copy()
        ctl.stop()
        done.set()

    @cap.event
    def on_closed():
        done.set()

    cap.start_free_threaded()
    if not done.wait(timeout) or "img" not in out:
        raise RuntimeError("Capture impossible (fenetre '%s' introuvable ?)" % title_part)
    return out["img"]


def load_image(path):
    img = cv2.imread(path, cv2.IMREAD_COLOR)
    if img is None:
        raise FileNotFoundError(path)
    return img

class FrameStream:
    """Capture continue: garde la derniere image (copiee au plus toutes les `every` secondes)."""

    def __init__(self, title_part="PartyMu.NET", every=0.15):
        import time
        from windows_capture import WindowsCapture, Frame, InternalCaptureControl

        self._lock = threading.Lock()
        self._frame, self._ts, self._last = None, 0.0, 0.0
        self.closed = False
        self.every = every
        cap = WindowsCapture(cursor_capture=False, draw_border=False, window_name=title_part)

        @cap.event
        def on_frame_arrived(frame: Frame, ctl: InternalCaptureControl):
            now = time.time()
            if now - self._last < every:
                return
            img = frame.frame_buffer[:, :, :3].copy()
            with self._lock:
                self._frame, self._ts, self._last = img, now, now

        @cap.event
        def on_closed():
            self.closed = True

        self._control = cap.start_free_threaded()

    def get(self):
        """(image, timestamp) ou (None, 0)."""
        with self._lock:
            return self._frame, self._ts

    def next_in(self):
        """Secondes avant la prochaine image disponible."""
        import time
        return max(0.0, self._last + self.every - time.time())

    def stop(self):
        try:
            self._control.stop()
        except Exception:
            pass
