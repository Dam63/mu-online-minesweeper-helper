# MU Online Minesweeper Helper — a passive "Find Bombs" overlay helper

A small Windows utility that reads the **Find Bombs** (minesweeper-style) mini-game of a MU Online client from
a window capture, works out the safest moves, and shows them as a transparent overlay on top of the board.

> **Status:** early / experimental. Tested on a single client (PartyMu.NET, 4K display at 150 % scaling).

## What it does

- Reads the 8×6 board, the *Remaining Bombs* counter and the *Score* from the window pixels.
- Solves the board exactly (constraint enumeration + the global bomb count) and computes a mine probability for every closed cell.
- Draws a click-through overlay on the board:
  - **green square** — cell is 100 % safe
  - **red square** — cell is a certain mine, or a bomb you already placed
  - **coloured number** — mine probability in %, green (safe) to red (dangerous)
  - **orange square** — best guess when no safe cell exists
- Recomputes only when the board changes, and pauses while the in-game cursor or an unknown symbol covers a cell.
- Tray icon and a tiny Start / Stop window, with timing and CPU / RAM stats.

## What it does **not** do

- It does **not** read or write game memory, inject code, hook the client, or touch its files or network traffic.
- It does **not** send clicks or keystrokes. You make every move yourself.
- It only looks at pixels, using the standard Windows Graphics Capture API (the same API OBS uses).

## Please read: fair-play disclaimer

This tool gives you information you would otherwise work out by hand. Whether that is acceptable depends on
**your server's rules**. Some servers forbid any third-party tool, even a passive one, and some anti-cheat
systems may flag screen-capture software. **Check your server's rules before using it. You use it at your own risk**;
the author is not responsible for bans or any other consequences.

This project is an independent fan-made helper and is **not affiliated with, endorsed by, or connected to Webzen,
any MU Online server, or their operators**. "MU" and "MU Online" are trademarks of their respective owners.

## Download (Windows, no Python needed)

Grab `MUOnlineMinesweeperHelper.exe` from the [Releases](https://github.com/Dam63/mu-online-minesweeper-helper/releases) page and run it (single file, nothing to install; the first launch takes a few seconds to unpack). The exe is unsigned, so Windows SmartScreen may warn about an unknown publisher (More info > Run anyway); the build is produced publicly by GitHub Actions from this repository. Settings and logs are stored in `%APPDATA%\MUOnlineMinesweeperHelper`.

## Requirements

- Windows 10 (1903+) or Windows 11
- Python 3.9+ (64-bit)
- The game client in **windowed or borderless** mode (exclusive fullscreen cannot be captured)

## Installation

```powershell
git clone https://github.com/Dam63/mu-online-minesweeper-helper.git
cd mu-online-minesweeper-helper
py -3 -m pip install -r requirements.txt
```

## Usage

```powershell
py -3 app.pyw        # tray icon + Start / Stop window (no console: use pythonw.exe)
py -3 live.py        # same engine, console only, overlay starts immediately
py -3 main.py        # one-shot read: print the board from the game window
py -3 main.py --image screenshot.png --debug     # read a screenshot, write debug/overlay.png
```

1. Start the game and open the *Find Bombs* window.
2. Run `app.pyw` and press **Start**.
3. Follow the overlay. Only one instance can run at a time; starting it again brings the window to the front.

The overlay opacity is `ALPHA` in `live.py`.

## Teaching it new symbols

Symbols are recognised by template matching, so unseen digits show up as `?` and the analysis pauses
(the window lists the unknown cells). Currently known on the board: `1`–`5`, closed cells, empty cells, revealed bombs.
**Digits `6`, `7`, `8` are not learned yet.**

```powershell
py -3 main.py --learn 2,4,6              # row 2, column 4 is a "6" in the current game window
py -3 main.py --learn-num remaining=12   # teach the digits of the counters
py -3 main.py --learn-num score=640
```

Templates are stored in `templates/`. Pull requests with templates from other servers or themes are welcome.

## How it works

| Module | Role |
|--------|------|
| `capture.py` | Window capture through Windows Graphics Capture (works even if the window is covered) |
| `reader.py` | Finds the dialog at any scale, normalises it, classifies each cell strictly (anything unknown becomes `?`) |
| `solver.py` | Exact probabilities: connected components of the frontier + the global mine count |
| `live.py` | Worker loop (change detection, pause logic, timing) and the click-through overlay |
| `app.pyw` | Tray icon, Start / Stop window, single-instance guard |

## Limitations

- Calibrated on one client skin and resolution. Other themes or fonts need new reference data (`assets/ref.png`) and templates.
- Flags placed by the player are shown but deliberately **not** used as information by the solver.
- If the board has a genuine 50/50, no tool can help — the overlay only tells you the odds.

## Contributing

This is an early, probably buggy release, so issues and pull requests are very welcome, especially: more digit templates, other resolutions / servers, and an easier
"learn this symbol" flow.

## License

[MIT](LICENSE).

