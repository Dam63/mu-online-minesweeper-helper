"""Surimpression transparente et click-through sur le plateau du jeu."""
import ctypes, sys, time
from ctypes import wintypes

ctypes.windll.shcore.SetProcessDpiAwareness(2)  # coordonnees en pixels physiques

import tkinter as tk
import win32gui
import reader
from capture import grab_window

GWL_EXSTYLE = -20
WS_EX_LAYERED, WS_EX_TRANSPARENT, WS_EX_TOOLWINDOW, WS_EX_NOACTIVATE = 0x80000, 0x20, 0x80, 0x08000000
KEY = "#010203"


def visible_bounds(hwnd):
    """Rectangle visible de la fenetre en pixels ecran (= origine de l'image capturee)."""
    r = wintypes.RECT()
    ctypes.windll.dwmapi.DwmGetWindowAttribute(hwnd, 9, ctypes.byref(r), ctypes.sizeof(r))
    return r.left, r.top, r.right, r.bottom


def find_hwnd(title_part):
    found = []
    win32gui.EnumWindows(lambda h, _: found.append(h) if title_part in win32gui.GetWindowText(h) and win32gui.IsWindowVisible(h) else None, None)
    return found[0] if found else None


def board_rect_screen(title, force=False):
    hwnd = find_hwnd(title)
    if not hwnd:
        raise RuntimeError("Fenetre '%s' introuvable" % title)
    frame = grab_window(title)
    left, top, right, bottom = visible_bounds(hwnd)
    fx = (right - left) / frame.shape[1]  # frame -> ecran (normalement 1.0)
    fy = (bottom - top) / frame.shape[0]
    geo = reader.locate(frame)
    if geo is None:
        if not force:
            raise RuntimeError("Mini-jeu 'Find Bombs' non detecte (--force pour tester au centre de la fenetre)")
        w, h = 270, 220
        return (left + (right - left - w) // 2, top + (bottom - top - h) // 2, w, h)
    s, ox, oy, _ = geo
    x0, y0, _, _ = reader.cell_rect(0, 0)
    _, _, x1, y1 = reader.cell_rect(reader.ROWS - 1, reader.COLS - 1)
    X0, Y0, X1, Y1 = (ox + s * x0, oy + s * y0, ox + s * x1, oy + s * y1)
    return int(left + X0 * fx), int(top + Y0 * fy), int((X1 - X0) * fx), int((Y1 - Y0) * fy)


def make_overlay(rect, text="Hello world", seconds=15):
    x, y, w, h = rect
    root = tk.Tk()
    root.overrideredirect(True)
    root.attributes("-topmost", True)
    root.attributes("-transparentcolor", KEY)
    root.geometry("%dx%d+%d+%d" % (w, h, x, y))
    cv = tk.Canvas(root, width=w, height=h, bg=KEY, highlightthickness=0)
    cv.pack()
    cv.create_rectangle(2, 2, w - 3, h - 3, outline="#00ff00", width=3)
    cv.create_text(w // 2, h // 2, text=text, fill="#00ff00", font=("Segoe UI", max(12, w // 12), "bold"))
    root.update_idletasks()
    hwnd = ctypes.windll.user32.GetParent(root.winfo_id()) or root.winfo_id()
    st = ctypes.windll.user32.GetWindowLongW(hwnd, GWL_EXSTYLE)
    ctypes.windll.user32.SetWindowLongW(hwnd, GWL_EXSTYLE, st | WS_EX_LAYERED | WS_EX_TRANSPARENT | WS_EX_TOOLWINDOW | WS_EX_NOACTIVATE)
    root.after(int(seconds * 1000), root.destroy)
    root.mainloop()


if __name__ == "__main__":
    force = "--force" in sys.argv
    rect = board_rect_screen("PartyMu.NET", force)
    print("overlay rect:", rect)
    make_overlay(rect)
