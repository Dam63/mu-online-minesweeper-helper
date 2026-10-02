"""Utilitaire minimal: fenetre Start/Stop + icone dans la zone de notification."""
import os, sys, queue, threading, time

HERE = os.path.dirname(os.path.abspath(__file__))
os.chdir(HERE)
sys.path.insert(0, HERE)
if sys.stdout is None or sys.stderr is None:  # pythonw: pas de console
    os.makedirs("debug", exist_ok=True)
    sys.stdout = sys.stderr = open(os.path.join("debug", "app.log"), "a", buffering=1, encoding="utf8")

import win32api, win32event, winerror

_mutex = win32event.CreateMutex(None, False, "Local\\MuBombesHelper")
_show_evt = win32event.CreateEvent(None, False, False, "Local\\MuBombesHelperShow")
if win32api.GetLastError() == winerror.ERROR_ALREADY_EXISTS:
    win32event.SetEvent(_show_evt)  # demande a l'instance existante de se montrer
    sys.exit(0)

import live  # definit aussi le DPI awareness avant tkinter
import tkinter as tk
import psutil
import pystray
from PIL import Image, ImageDraw


def make_icon(active):
    im = Image.new("RGBA", (64, 64), (0, 0, 0, 0))
    d = ImageDraw.Draw(im)
    d.ellipse((6, 14, 58, 62), fill=(30, 30, 30, 255), outline=(0, 220, 0, 255) if active else (150, 150, 150, 255), width=4)
    d.line((40, 14, 50, 4), fill=(200, 160, 60, 255), width=4)
    d.ellipse((46, 0, 56, 10), fill=(255, 120, 0, 255))
    d.ellipse((18, 28, 28, 38), fill=(255, 255, 255, 120))
    return im


class App:
    def __init__(self):
        self.session = live.Session()
        self.q = queue.Queue()
        self.root = tk.Tk()
        r = self.root
        r.title("MU Online Minesweeper Helper")
        r.geometry("560x330")
        r.resizable(False, False)
        r.attributes("-topmost", True)
        try:
            from PIL import ImageTk
            self.icon_tk = ImageTk.PhotoImage(make_icon(False))
            r.iconphoto(True, self.icon_tk)
        except Exception:
            pass
        self.status = tk.Label(r, text="Arrete", font=("Segoe UI", 10))
        self.status.pack(pady=(10, 6))
        row = tk.Frame(r)
        row.pack()
        self.perf = tk.Label(r, text="", font=("Consolas", 9), justify="left", anchor="nw")
        self.perf.pack(fill="x", padx=10, pady=(8, 0))
        self.b_start = tk.Button(row, text="Start", width=9, command=self.start)
        self.b_stop = tk.Button(row, text="Stop", width=9, command=self.stop, state="disabled")
        self.b_start.pack(side="left", padx=4)
        self.b_stop.pack(side="left", padx=4)
        r.protocol("WM_DELETE_WINDOW", r.withdraw)  # la croix reduit dans la zone de notification
        self.proc = psutil.Process()
        self.proc.cpu_percent(None)
        self.res_text, self.res_at = "", 0.0
        self.overlay = live.Overlay(r)
        self.tray = pystray.Icon("mu-online-minesweeper-helper", make_icon(False), "MU Online Minesweeper Helper", menu=pystray.Menu(
            pystray.MenuItem("Afficher", lambda: self.q.put("show"), default=True),
            pystray.MenuItem("Start", lambda: self.q.put("start")),
            pystray.MenuItem("Stop", lambda: self.q.put("stop")),
            pystray.MenuItem("Quitter", lambda: self.q.put("quit")),
        ))
        self.tray.run_detached()
        self.overlay.tick()
        self.poll()

    def start(self):
        self.session.start()
        self.refresh()

    def stop(self):
        self.session.stop()
        self.refresh()

    def refresh(self):
        run = self.session.running
        self.b_start.config(state="disabled" if run else "normal")
        self.b_stop.config(state="normal" if run else "disabled")
        self.tray.icon = make_icon(run)

    def perf_text(self):
        P = live.PERF
        nxt = self.session.stream.next_in() * 1000 if self.session.stream else 0
        if P["change_at"]:
            ago = "il y a %.0f s (%.0f ms)" % (time.time() - P["change_at"], P["change_ms"])
        else:
            ago = "-"
        return ("Cycle : %5.0f ms (loc %.0f | lect %.0f)\n"
                "Solveur: %5.0f ms\n"
                "Idle   : %5.0f %%\n"
                "Refresh: %5.0f ms (prochain %.0f ms)\n"
                "Derniere modif: %s\n"
                "%s") % (P["cycle"], P["locate"], P["read"], P["solve"], 100 * P["idle"],
                                         1000 * P["interval"], nxt, ago, self.resources())

    def resources(self):
        """CPU (en % d'un coeur et du CPU total) et RAM du processus, echantillonnes chaque seconde."""
        if time.time() - self.res_at >= 1.0:
            cpu = self.proc.cpu_percent(None)
            ram = self.proc.memory_info().rss / 1048576
            self.res_text = "CPU    : %5.1f %% coeur (%.1f %% total) | RAM %.0f Mo" % (cpu, cpu / psutil.cpu_count(), ram)
            self.res_at = time.time()
        return self.res_text

    def poll(self):
        if win32event.WaitForSingleObject(_show_evt, 0) == win32event.WAIT_OBJECT_0:
            self.q.put("show")
        try:
            while True:
                cmd = self.q.get_nowait()
                if cmd == "show":
                    self.root.deiconify()
                    self.root.lift()
                elif cmd == "start":
                    self.start()
                elif cmd == "stop":
                    self.stop()
                elif cmd == "quit":
                    self.session.stop()
                    self.tray.stop()
                    self.root.destroy()
                    return
        except queue.Empty:
            pass
        if self.session.running:
            self.status.config(text=live.STATE.get("msg", "") + ("  [pause: %d inconnue(s) %s]" % (len(live.STATE.get("pause_cells", ())), list(live.STATE.get("pause_cells", ()))[:3]) if live.STATE.get("paused") else ""))
            self.perf.config(text=self.perf_text())
        else:
            self.status.config(text="Arrete")
            self.perf.config(text="")
        self.root.after(200, self.poll)


if __name__ == "__main__":
    App().root.mainloop()


