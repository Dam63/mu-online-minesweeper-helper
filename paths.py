"""Resource and user-data locations (source checkout vs. PyInstaller build)."""
import os, sys

FROZEN = getattr(sys, "frozen", False)
RES = getattr(sys, "_MEIPASS", os.path.dirname(os.path.abspath(__file__)))
if FROZEN:
    DATA = os.path.join(os.environ.get("APPDATA", os.path.expanduser("~")), "MUOnlineMinesweeperHelper")
else:
    DATA = os.path.join(os.path.dirname(os.path.abspath(__file__)), "debug")
os.makedirs(DATA, exist_ok=True)
