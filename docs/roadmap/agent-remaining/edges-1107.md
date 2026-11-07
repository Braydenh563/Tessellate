# edges-1107 (INBOX 1683 k, x, y; 1692 a; companion-asks.md N3 to N10) remaining

Done (fake transport and fake clock only): screen edges model (`win32.bars`, `Monitor.screen` and `.bars`, rescan on cadence and on the taskbar event, the floor is a shown bottom bar's top, a figure whose floor drops falls), peeks from behind bars and every edge by mood, tuck behind a smaller window, fling off a moved window, scrabble then pull up, portal kept in `travel.MODES`, in-app shake-off with flail and miffed face.

Measured (seeded): 100 flings 61 fall, 22 portal, 17 puff; 100 hang slips 63 pull up, 37 drop; the seeded hour (both gaits, 6 seeds, 136 legs) glide 29.4%, walk 26.5%, jump 19.1%, portal 8.8%, climb 5.9%, edge 2.9%, puff 0%. The walk gait alone is 44.4% walk, so the 40% cap holds for the combined run only.

Unverified on real Windows (nothing here ran there):
- `ABM_GETTASKBARPOS` per taskbar and `ABM_GETSTATE` auto-hide, secondary taskbars found by a `FindWindowExW` loop (not `EnumWindows`, which the scan-count tests pin), the shell's taskbar-created event as a rescan trigger, DPI of each monitor's bar.
- The live scan cadence: a fling needs two scans close in time (`SCAN_RIDING`, 0.25 s while perched or tucked); a slow machine reads a drag as a smaller speed.
- `Output.clip` on a layered topmost window for the peek and the tuck (clear pixels take no clicks): the emulation of hiding behind a window is a rectangle, so a tuck needs a window that spans the figure's full height.
- Whether a real window drag moves the rect each scan (some apps move in steps).

Left:
- The wall-slide scrabble on the desk has no pull-up (a screen side wall has no top edge); only the hang slip pulls up.
- The top peek is a hang pose climbing up behind the edge, not an upside-down figure.
- The tuck is a choice inside the peek act, not its own `ACTS` key (seeded act tables unchanged).
- In-app: tuck behind a panel's SIDE edge is not built (a panel's top edge, the phone dock and the bars already peek); the shake-off was driven in node with the page stubbed, not in a browser. Drive it: `bash scratchpad/ui-sweeps/serve.sh`, perch on a widget, drag the widget fast, expect a flail, a landing and a face for 2 to 4 s.
- `monitors()` keeps its 2-tuple shape; `monitors_full` is the rich API.

Tests changed (intent moved, not weakened): `tests/test_overlay_moves.py` counted a hang that follows a top peek as a second big act, and its clip check had no top strip. A top peek ends as a hang by design, so that hang is the peek's own end; the clip check now also requires a top strip to lie outside the work area.
