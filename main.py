import argparse, os, sys, time
import cv2
import reader
from capture import grab_window, load_image


def show(res):
    print("Remaining Bombs:", res["remaining"], "| Score:", res["score"], "| scale=%.2f match=%.2f" % (res["geo"][0], res["geo"][3]))
    print("   " + " ".join(str(i) for i in range(reader.COLS)))
    for i, row in enumerate(res["grid"]):
        print("%d  %s" % (i, " ".join(row)))
    if res["unknown"]:
        print("Cases inconnues (a apprendre avec --learn r,c,valeur):", res["unknown"])


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--image", help="lire un fichier au lieu de capturer le jeu")
    p.add_argument("--title", default="PartyMu.NET")
    p.add_argument("--learn", action="append", default=[], help="r,c,valeur  (ex: 2,6,3 ; 0,0,B)")
    p.add_argument("--learn-num", action="append", default=[], help="remaining=11 ou score=90")
    p.add_argument("--debug", action="store_true", help="ecrit debug/norm.png et debug/overlay.png")
    p.add_argument("--watch", type=float, help="relit toutes les N secondes")
    a = p.parse_args()

    while True:
        frame = load_image(a.image) if a.image else grab_window(a.title)
        res = reader.read_board(frame)
        norm = res["norm"]
        for l in a.learn:
            r, c, v = l.split(",")
            reader.learn_cell(norm, int(r), int(c), v)
            print("appris case", l)
        for l in a.learn_num:
            k, v = l.split("=")
            reader.learn_number(norm, k, v)
            print("appris", l)
        if a.learn or a.learn_num:
            res = reader.read_board(frame)
        if a.debug:
            ov = norm.copy()
            for r in range(reader.ROWS):
                for c in range(reader.COLS):
                    x0, y0, x1, y1 = reader.cell_rect(r, c)
                    cv2.rectangle(ov, (x0, y0), (x1, y1), (0, 255, 255), 1)
                    cv2.putText(ov, res["grid"][r][c], (x0 + 8, y1 - 6), cv2.FONT_HERSHEY_SIMPLEX, 0.6, (255, 0, 255), 2)
            for b in (reader.BOX_REM, reader.BOX_SCORE):
                cv2.rectangle(ov, (b[0], b[1]), (b[2], b[3]), (0, 255, 0), 1)
            os.makedirs(reader.DEBUG_DIR, exist_ok=True)
            cv2.imwrite(os.path.join(reader.DEBUG_DIR, "norm.png"), norm)
            cv2.imwrite(os.path.join(reader.DEBUG_DIR, "overlay.png"), ov)
        show(res)
        if not a.watch:
            break
        time.sleep(a.watch)


if __name__ == "__main__":
    try:
        main()
    except (RuntimeError, FileNotFoundError) as e:
        sys.exit("Erreur: %s" % e)

