"""Lecture du mini-jeu 'Find Bombs' (8x6) a partir d'une capture."""
import os
import cv2
import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
REF_PATH = os.path.join(HERE, "assets", "ref.png")
CELL_DIR = os.path.join(HERE, "templates", "cells")
DIGIT_DIR = os.path.join(HERE, "templates", "digits")
DEBUG_DIR = os.path.join(HERE, "debug")

# Geometrie en coordonnees de l'image de reference (echelle 1.0)
COLS, ROWS = 8, 6
GRID_X0, GRID_Y0 = 159.0, 186.0      # centre de la case (0,0)
PITCH_X, PITCH_Y = 33.0, 35.6
CELL_HALF = 14
ANCHOR = (130, 408, 330, 490)         # libelles "Remaining Bombs" / "Score"
BOX_REM = (338, 406, 418, 440)
BOX_SCORE = (338, 458, 418, 494)

CLOSED = "#"
EMPTY = "."
BOMB = "B"  # bombe revelee (icone noire sur tuile marron)


def _gray(img):
    return cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)


def _match_at(fg, tpl, s):
    t = cv2.resize(tpl, None, fx=s, fy=s, interpolation=cv2.INTER_AREA if s < 1 else cv2.INTER_CUBIC)
    if t.shape[0] >= fg.shape[0] or t.shape[1] >= fg.shape[1]:
        return -1, (0, 0)
    r = cv2.matchTemplate(fg, t, cv2.TM_CCOEFF_NORMED)
    _, mx, _, loc = cv2.minMaxLoc(r)
    return mx, loc


_REF_CACHE = {}


def _ref():
    if "img" not in _REF_CACHE:
        _REF_CACHE["img"] = cv2.imread(REF_PATH)
        x0, y0, x1, y1 = ANCHOR
        _REF_CACHE["tpl"] = _gray(_REF_CACHE["img"][y0:y1, x0:x1])
    return _REF_CACHE["img"], _REF_CACHE["tpl"]


def locate(frame, scales=None, min_score=0.7):
    """Retrouve (echelle, ox, oy, score): coord_frame = ox + scale * coord_ref. None si absent.
    scales: echelles candidates (defaut: recherche large, lente ~5 s sur une capture 4K)."""
    _, tpl = _ref()
    x0, y0, _, _ = ANCHOR
    fg = _gray(frame)
    small = cv2.resize(fg, None, fx=0.5, fy=0.5, interpolation=cv2.INTER_AREA)
    scales = scales if scales is not None else np.arange(0.5, 2.51, 0.05)
    best = (-1, None, None)
    for s in scales:
        mx, loc = _match_at(small, tpl, s / 2)
        if mx > best[0]:
            best = (mx, s, loc)
    if best[1] is None or best[0] < min_score - 0.15:
        return None
    _, s, loc = best
    cx, cy = loc[0] * 2, loc[1] * 2
    best = (-1, s, (cx, cy))
    pad = 12
    for s2 in np.arange(s - 0.03, s + 0.031, 0.01):
        t = cv2.resize(tpl, None, fx=s2, fy=s2, interpolation=cv2.INTER_AREA if s2 < 1 else cv2.INTER_CUBIC)
        h, w = t.shape
        ax, ay = max(0, cx - pad), max(0, cy - pad)
        roi = fg[ay:cy + h + pad, ax:cx + w + pad]
        if roi.shape[0] < h or roi.shape[1] < w:
            continue
        r = cv2.matchTemplate(roi, t, cv2.TM_CCOEFF_NORMED)
        _, mx, _, l2 = cv2.minMaxLoc(r)
        if mx > best[0]:
            best = (mx, s2, (ax + l2[0], ay + l2[1]))
    mx, s, loc = best
    if mx < min_score:
        return None
    return s, loc[0] - s * x0, loc[1] - s * y0, mx


def refine(frame, geo, margin=24, min_score=0.7):
    """Verifie/ajuste une geometrie connue sans rechercher toute l'image. None si le dialogue a disparu/bouge trop."""
    s, ox, oy, _ = geo
    _, base = _ref()
    x0, y0, x1, y1 = ANCHOR
    tpl = cv2.resize(base, None, fx=s, fy=s, interpolation=cv2.INTER_AREA if s < 1 else cv2.INTER_CUBIC)
    ex, ey = int(round(ox + s * x0)), int(round(oy + s * y0))
    h, w = tpl.shape
    ax, ay = max(0, ex - margin), max(0, ey - margin)
    roi = _gray(frame[ay:ey + h + margin, ax:ex + w + margin])
    if roi.shape[0] < h or roi.shape[1] < w:
        return None
    r = cv2.matchTemplate(roi, tpl, cv2.TM_CCOEFF_NORMED)
    _, mx, _, loc = cv2.minMaxLoc(r)
    if mx < min_score:
        return None
    return s, ax + loc[0] - s * x0, ay + loc[1] - s * y0, mx


def normalize(frame, geo):
    """Remet la zone du dialogue a l'echelle 1.0 (taille de la reference)."""
    s, ox, oy, _ = geo
    H, W = 618, 551
    M = np.float32([[1 / s, 0, -ox / s], [0, 1 / s, -oy / s]])
    return cv2.warpAffine(frame, M, (W, H), flags=cv2.INTER_AREA if s > 1 else cv2.INTER_CUBIC)


def cell_rect(r, c):
    cx = GRID_X0 + PITCH_X * c
    cy = GRID_Y0 + PITCH_Y * r
    return int(round(cx - CELL_HALF)), int(round(cy - CELL_HALF)), int(round(cx + CELL_HALF)), int(round(cy + CELL_HALF))


def _closed_ratio(patch):
    hsv = cv2.cvtColor(patch, cv2.COLOR_BGR2HSV)
    m = (hsv[:, :, 0] >= 5) & (hsv[:, :, 0] <= 22) & (hsv[:, :, 1] > 90) & (hsv[:, :, 2] > 70)
    return float(m.mean())


def _text_mask(patch):
    """Pixels de chiffre: colores (1,2,3...) ou blancs (4) sur une case ouverte sombre."""
    hsv = cv2.cvtColor(patch, cv2.COLOR_BGR2HSV)
    colored = (hsv[:, :, 1] > 110) & (hsv[:, :, 2] > 110)
    white = (hsv[:, :, 1] < 60) & (hsv[:, :, 2] > 150)
    return (colored | white).astype(np.uint8)


def _glyph(mask, size=(12, 16)):
    ys, xs = np.where(mask > 0)
    if len(xs) < 6:
        return None
    g = mask[ys.min():ys.max() + 1, xs.min():xs.max() + 1].astype(np.float32)
    return cv2.resize(g, size, interpolation=cv2.INTER_AREA)


_TPL_CACHE = {}


def _load_templates(folder):
    if not os.path.isdir(folder):
        return []
    sig = tuple((f, os.path.getmtime(os.path.join(folder, f))) for f in sorted(os.listdir(folder)))
    hit = _TPL_CACHE.get(folder)
    if hit and hit[0] == sig:
        return hit[1]
    out = _load_templates_uncached(folder)
    _TPL_CACHE[folder] = (sig, out)
    return out


def _load_templates_uncached(folder):
    out = []
    for f in sorted(os.listdir(folder)):
        if f.lower().endswith(".png"):
            label = f.split("_")[0]
            img = cv2.imread(os.path.join(folder, f), cv2.IMREAD_GRAYSCALE)
            if img is not None:
                out.append((label, img.astype(np.float32) / 255.0))
    return out


def _match(glyph, templates):
    best, label = 1e9, None
    for lab, t in templates:
        d = float(np.abs(glyph - t).mean())
        if d < best:
            best, label = d, lab
    return label, best


def _save_template(folder, label, glyph):
    os.makedirs(folder, exist_ok=True)
    n = len([f for f in os.listdir(folder) if f.startswith(label + "_")])
    cv2.imwrite(os.path.join(folder, "%s_%d.png" % (label, n)), (glyph * 255).astype(np.uint8))


def classify_cell(norm, r, c, templates, max_dist=0.25):
    """Classification stricte: tout ce qui n'est pas parfaitement reconnu (curseur, symbole inconnu) donne '?'."""
    x0, y0, x1, y1 = cell_rect(r, c)
    patch = norm[y0:y1, x0:x1]
    closed = _closed_ratio(patch)
    hsv = cv2.cvtColor(patch, cv2.COLOR_BGR2HSV)
    bright = int(((hsv[:, :, 2] > 150) & (hsv[:, :, 1] < 50)).sum())
    if closed > 0.3 and (hsv[7:21, 7:21, 2] < 45).mean() > 0.25:
        return (BOMB, 0.0) if bright <= 8 else ("?", 1.0)
    if closed > 0.6:
        return (CLOSED, 0.0) if bright <= 3 else ("?", 1.0)
    if closed > 0.3:
        return "?", 1.0
    mask = _text_mask(patch)
    if int(mask.sum()) < 4:
        return EMPTY, 0.0
    g = _glyph(mask)
    if g is None:
        return "?", 1.0
    lab, d = _match(g, templates)
    if lab is None or d > max_dist:
        return "?", d
    return lab, d


def read_number(norm, box, templates, max_dist=0.3):
    x0, y0, x1, y1 = box
    g = _gray(norm[y0:y1, x0:x1])
    m = (g > 110).astype(np.uint8)
    cols = np.where(m.sum(0) > 0)[0]
    if len(cols) == 0:
        return None, []
    groups, start, prev = [], cols[0], cols[0]
    for x in cols[1:]:
        if x - prev > 1:
            groups.append((start, prev))
            start = x
        prev = x
    groups.append((start, prev))
    glyphs, text = [], ""
    for a, b in groups:
        gl = _glyph(m[:, a:b + 1], (10, 14))
        if gl is None:
            continue
        glyphs.append(gl)
        lab, d = _match(gl, templates)
        text += lab if (lab is not None and d <= max_dist) else "?"
    return text, glyphs


def read_board(frame, geo=None, save_unknown=True):
    geo = geo or locate(frame)
    if geo is None:
        raise RuntimeError("Mini-jeu 'Find Bombs' non detecte dans la capture (ouvre-le a l'ecran)")
    norm = normalize(frame, geo)
    cells_t = _load_templates(CELL_DIR)
    digits_t = _load_templates(DIGIT_DIR)
    grid, unknown = [], []
    for r in range(ROWS):
        row = []
        for c in range(COLS):
            v, _ = classify_cell(norm, r, c, cells_t)
            if v == "?":
                unknown.append((r, c))
            row.append(v)
        grid.append(row)
    rem, _ = read_number(norm, BOX_REM, digits_t)
    score, _ = read_number(norm, BOX_SCORE, digits_t)
    return {"grid": grid, "remaining": rem, "score": score, "geo": geo, "norm": norm, "unknown": unknown,
            "frame_w": frame.shape[1], "frame_h": frame.shape[0]}


def learn_cell(norm, r, c, label):
    x0, y0, x1, y1 = cell_rect(r, c)
    g = _glyph(_text_mask(norm[y0:y1, x0:x1]))
    if g is None:
        raise ValueError("rien a apprendre dans la case (%d,%d)" % (r, c))
    _save_template(CELL_DIR, label, g)


def learn_number(norm, which, text):
    box = BOX_REM if which == "remaining" else BOX_SCORE
    cur, glyphs = read_number(norm, box, [])
    if len(glyphs) != len(text):
        raise ValueError("%d glyphes detectes pour '%s'" % (len(glyphs), text))
    for ch, g in zip(text, glyphs):
        _save_template(DIGIT_DIR, ch, g)




