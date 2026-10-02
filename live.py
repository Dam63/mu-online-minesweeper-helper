"""Assistant en direct: capture -> lecture -> solveur -> surimpression (click-through)."""
import collections, ctypes, json, os, sys, threading, time
import numpy as np
from ctypes import wintypes

ctypes.windll.shcore.SetProcessDpiAwareness(2)

import tkinter as tk
import win32gui
import reader, solver
from capture import FrameStream
from overlay import KEY, visible_bounds, find_hwnd, GWL_EXSTYLE, WS_EX_LAYERED, WS_EX_TRANSPARENT, WS_EX_TOOLWINDOW, WS_EX_NOACTIVATE

TITLE = "PartyMu.NET"
HEADER = 40
ALPHA = 0.6  # transparence globale du calque (1.0 = opaque)
STATE = {"paused": False, "seq": 0, "ok": False, "msg": "demarrage...", "ts": 0.0}


def fmt(res, sol):
    lines = ["Remaining Bombs: %s | Score: %s" % (res["remaining"], res["score"])]
    for r, row in enumerate(res["grid"]):
        lines.append("  " + " ".join(row))
    if sol:
        lines.append("Sures: %s" % [tuple(v) for v in sol["safe"]])
        lines.append("Bombes: %s" % [tuple(v) for v in sol["mines"]])
        if sol["best"]:
            lines.append("Meilleur pari: %s (%.0f%% de bombe)" % (sol["best"], 100 * sol["prob"][sol["best"]]))
        if sol["warning"]:
            lines.append("Attention: " + sol["warning"])
    return "\n".join(lines)


HINT_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "debug", "hint.json")
PERF = {"cycle": 0.0, "locate": 0.0, "read": 0.0, "solve": 0.0, "idle": 1.0, "change_ms": None, "change_at": None, "interval": 0.15}


def load_hint():
    try:
        with open(HINT_PATH) as f:
            d = json.load(f)
        return tuple(d["shape"]), d["scale"]
    except Exception:
        return None


def save_hint(shape, scale):
    try:
        os.makedirs(os.path.dirname(HINT_PATH), exist_ok=True)
        with open(HINT_PATH, "w") as f:
            json.dump({"shape": list(shape), "scale": scale}, f)
    except Exception:
        pass


def worker(stream, stop):
    geo, last_key, pending, last_ts = None, None, None, 0.0
    hint, last_full = load_hint(), 0.0
    busy = collections.deque()
    PERF["interval"] = stream.every
    while not stop.is_set():
        frame, ts = stream.get()
        if frame is None or ts == last_ts:
            time.sleep(0.01)
            continue
        last_ts = ts
        t0 = time.perf_counter()
        t_loc = t_read = t_solve = 0.0
        try:
            g = reader.refine(frame, geo) if geo else None
            if g is None:
                tl = time.perf_counter()
                shape = frame.shape[:2]
                if hint and hint[0] == shape:
                    cands = [hint[1]]
                else:
                    est = shape[0] / 2173.0  # echelle de reference observee sur un ecran 4K
                    cands = np.arange(max(0.3, est - 0.15), est + 0.151, 0.03)
                g = reader.locate(frame, scales=cands)
                if g is None and time.time() - last_full > 15:
                    last_full = time.time()
                    g = reader.locate(frame)  # recherche large, rare
                if g:
                    hint = (shape, g[0])
                    save_hint(shape, g[0])
                t_loc = time.perf_counter() - tl
            geo = g
            if geo is None:
                STATE.update(ok=False, msg="mini-jeu non visible", ts=ts)
                last_key = pending = None
                continue
            tr = time.perf_counter()
            res = reader.read_board(frame, geo)
            t_read = time.perf_counter() - tr
            if res["unknown"]:  # curseur ou symbole inconnu devant des cases: on garde le dernier resultat
                STATE.update(geo=geo, ts=ts, ok=True, paused=True, pause_cells=res["unknown"])
                pending = None
                continue
            STATE["paused"] = False
            key = (tuple(map(tuple, res["grid"])), res["remaining"])
            if key != pending:  # il faut deux lectures identiques (evite les animations)
                pending = key
                STATE.update(geo=geo, ts=ts)
                continue
            if key == last_key:
                STATE.update(geo=geo, ts=ts, ok=True)
                continue
            last_key = key
            sol = None
            ts0 = time.perf_counter()
            if True:
                rem = int(res["remaining"]) if res["remaining"] and res["remaining"].isdigit() else None
                # les bombes posees par le joueur ne sont pas interpretees: ce sont des cases fermees comme les autres
                placed = {(r, c) for r, row in enumerate(res["grid"]) for c, v in enumerate(row) if v == "B"}
                grid = [["#" if v == "B" else v for v in row] for row in res["grid"]]
                sol = solver.solve(grid, None if rem is None else rem + len(placed), ignore=placed)
                sol["placed"] = placed
                msg = "%d sures, %d bombes" % (len(sol["safe"]), len(sol["mines"]))
            t_solve = time.perf_counter() - ts0
            PERF["change_at"] = time.time()
            PERF["change_ms"] = 1000 * (time.perf_counter() - t0)
            STATE.update(seq=STATE["seq"] + 1, ok=True, geo=geo, ts=ts, msg=msg, res=res, sol=sol)
            print("\n--- plateau modifie ---\n" + fmt(res, sol) + ("\n" + msg if not sol else ""), flush=True)
        except Exception as e:  # noqa
            STATE.update(ok=False, msg="erreur: %s" % e, ts=ts)
        finally:
            now = time.perf_counter()
            busy.append((now, now - t0))
            while busy and now - busy[0][0] > 5:
                busy.popleft()
            PERF.update(cycle=1000 * (now - t0), locate=1000 * t_loc, read=1000 * t_read,
                        idle=max(0.0, 1 - sum(d for _, d in busy) / 5.0))
            if t_solve:
                PERF["solve"] = 1000 * t_solve


def risk_colour(p):
    """Vert (0 %) -> jaune -> rouge (100 %)."""
    p = min(1.0, max(0.0, p))
    r = min(255, int(510 * p))
    g = min(255, int(510 * (1 - p)))
    return "#%02x%02x00" % (r, g)


class Overlay:
    def __init__(self, master=None):
        self.root = tk.Toplevel(master) if master else tk.Tk()
        r = self.root
        r.overrideredirect(True)
        r.attributes("-topmost", True)
        r.attributes("-transparentcolor", KEY)
        r.attributes("-alpha", ALPHA)
        self.cv = tk.Canvas(r, bg=KEY, highlightthickness=0)
        self.cv.pack(fill="both", expand=True)
        r.geometry("10x10+0+0")
        r.update_idletasks()
        h = ctypes.windll.user32.GetParent(r.winfo_id()) or r.winfo_id()
        st = ctypes.windll.user32.GetWindowLongW(h, GWL_EXSTYLE)
        ctypes.windll.user32.SetWindowLongW(h, GWL_EXSTYLE, st | WS_EX_LAYERED | WS_EX_TRANSPARENT | WS_EX_TOOLWINDOW | WS_EX_NOACTIVATE)
        r.withdraw()
        self.hwnd = None
        self.drawn = None
        self.visible = False

    def tick(self):
        try:
            self.update()
        except Exception as e:  # noqa
            print("overlay:", e, flush=True)
        self.root.after(150, self.tick)

    def update(self):
        fresh = time.time() - STATE.get("ts", 0) < 3
        if not (STATE.get("ok") and fresh and STATE.get("geo")):
            if self.visible:
                self.root.withdraw()
                self.visible = False
            return
        if not self.hwnd or not win32gui.IsWindow(self.hwnd):
            self.hwnd = find_hwnd(TITLE)
            if not self.hwnd:
                return
        left, top, right, bottom = visible_bounds(self.hwnd)
        frame_w = STATE["res"]["frame_w"]
        frame_h = STATE["res"]["frame_h"]
        fx, fy = (right - left) / frame_w, (bottom - top) / frame_h
        s, ox, oy, _ = STATE["geo"]
        x0, y0, _, _ = reader.cell_rect(0, 0)
        _, _, x1, y1 = reader.cell_rect(reader.ROWS - 1, reader.COLS - 1)
        bx, by = left + (ox + s * x0) * fx, top + (oy + s * y0) * fy
        bw, bh = s * (x1 - x0) * fx, s * (y1 - y0) * fy
        geom = (int(bx), int(by) - HEADER, int(bw), int(bh) + HEADER)
        sig = (geom, STATE["seq"], STATE.get("paused", False))
        if sig == self.drawn and self.visible:
            return
        self.drawn = sig
        self.root.geometry("%dx%d+%d+%d" % (geom[2], geom[3], geom[0], geom[1]))
        self.draw(s * fx, s * fy, ox, oy, bx, by)
        if not self.visible:
            self.root.deiconify()
            self.visible = True

    def draw(self, kx, ky, ox, oy, bx, by):
        cv = self.cv
        cv.delete("all")
        sol, res = STATE.get("sol"), STATE.get("res")
        cv.create_text(4, 0, anchor="nw", fill="#ffff00", font=("Segoe UI", 11, "bold"), text=STATE["msg"] + ("  [pause: %d case(s) non reconnue(s)]" % len(STATE.get("pause_cells", ())) if STATE.get("paused") else ""))
        if not sol:
            return
        half = reader.CELL_HALF
        fs = max(7, int(9 * kx))

        def centre(r, c):
            cx = reader.GRID_X0 + reader.PITCH_X * c
            cy = reader.GRID_Y0 + reader.PITCH_Y * r
            return (ox + STATE["geo"][0] * cx) * (kx / STATE["geo"][0]) - (bx - 0) + 0, 0

        s = STATE["geo"][0]
        fx_ = kx / s
        fy_ = ky / s

        def pos(r, c):
            cx = reader.GRID_X0 + reader.PITCH_X * c
            cy = reader.GRID_Y0 + reader.PITCH_Y * r
            x0, y0, _, _ = reader.cell_rect(0, 0)
            return (cx - x0) * kx, (cy - y0) * ky + HEADER

        hw, hh = (half - 2) * kx, (half - 2) * ky
        ex, ey = 2 * kx, 2 * ky  # l'ombre du bouton decale le centre: on agrandit a droite et en bas
        safe, mines, best = set(sol["safe"]), set(sol["mines"]), sol["best"]
        placed = sol.get("placed", set())
        for (r, c), p in sol["prob"].items():
            x, y = pos(r, c)
            if (r, c) in placed and (r, c) not in safe:
                cv.create_rectangle(x - hw, y - hh, x + hw + ex, y + hh + ey, outline="#ff2020", width=3)
            elif (r, c) in safe:
                cv.create_rectangle(x - hw, y - hh, x + hw + ex, y + hh + ey, outline="#00ff00", width=4)
            elif (r, c) in mines:
                cv.create_rectangle(x - hw, y - hh, x + hw + ex, y + hh + ey, outline="#ff2020", width=3)
            elif p is not None:
                col = risk_colour(p)
                if (r, c) == best:
                    cv.create_rectangle(x - hw, y - hh, x + hw + ex, y + hh + ey, outline="#ffa500", width=3)
                cv.create_text(x, y, text="%d" % round(100 * p), fill=col, font=("Segoe UI", fs, "bold" if (r, c) == best else "normal"))


class Session:
    """Capture + analyse; start()/stop() pour l'utilitaire."""

    def __init__(self):
        self.stream = self.stop_evt = None

    @property
    def running(self):
        return self.stream is not None

    def start(self):
        if self.running:
            return
        STATE.update(ok=False, msg="demarrage...", ts=0.0, geo=None)
        self.stream = FrameStream(TITLE)
        self.stop_evt = threading.Event()
        threading.Thread(target=worker, args=(self.stream, self.stop_evt), daemon=True).start()

    def stop(self):
        if not self.running:
            return
        self.stop_evt.set()
        self.stream.stop()
        self.stream = self.stop_evt = None
        STATE.update(ok=False, ts=0.0)


def main():
    stream = FrameStream(TITLE)
    stop = threading.Event()
    threading.Thread(target=worker, args=(stream, stop), daemon=True).start()
    ov = Overlay()
    ov.tick()
    print("Assistant lance. Ctrl+C dans cette console pour quitter.", flush=True)
    try:
        ov.root.mainloop()
    except KeyboardInterrupt:
        pass
    stop.set()
    stream.stop()


if __name__ == "__main__":
    main()




