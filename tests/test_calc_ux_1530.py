"""The Calculator and equations UX audit (INBOX 1530 g, d231b19).

Static checks of the dialog's wiring, one block per finding; the measured side
(strip position, tab stops, widths) is the sweep named in each CHANGELOG line.
"""

from __future__ import annotations

import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
JS = ROOT / "frontend" / "js"
CSS = ROOT / "frontend" / "css"


def _read(name: str) -> str:
    return (JS / name).read_text(encoding="utf-8")


# --- the stale caught box (popupToolMaths) --------------------------------------


def test_a_tool_is_handed_its_box_never_a_remembered_one() -> None:
    features = _read("app-features.js")
    head = features.split("async function popupToolMaths(", 1)[1].split("{", 1)[0]
    assert "paletteCaught" not in head, "popupToolMaths must not default to the palette's last box"
    body = features.split("async function popupToolMaths(", 1)[1].split("\n}\n", 1)[0]
    assert "paletteCaught" not in body


def test_the_palette_caught_box_is_live_only_while_the_palette_runs_a_row() -> None:
    palette = _read("app-palette.js")
    run = palette.split("function paletteRun(", 1)[1].split("\n}\n", 1)[0]
    assert "paletteCaught.live = true" in run and "paletteCaught.live = false" in run
    assert "finally" in run, "a row that throws must not leave the caught box live"
    panes = _read("settings-panes.js")
    now = panes.split("function paletteCaughtNow()", 1)[1].split("\n}\n", 1)[0]
    assert ".live" in now, "outside a palette run there is no caught box"


def test_the_palette_rows_read_the_caught_box_before_they_wait() -> None:
    features = _read("app-features.js")
    tools = next(line for line in features.splitlines() if "...POPUP_TOOLS.map((t) =>" in line)
    assert "t.open(paletteCaughtNow().target)" in tools
    count = next(line for line in features.splitlines() if "Count words" in line and "act:" in line)
    assert count.index("paletteCaughtNow()") < count.index("ensureModule"), "read after the wait, the palette's run is over"


def test_only_the_palette_and_its_reader_name_the_caught_const() -> None:
    for path in sorted(JS.glob("*.js")):
        for number, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
            code = line.split("//", 1)[0]
            if re.search(r"\bpaletteCaught\b(?!Now)", code):
                assert path.name in {"app-palette.js", "settings-panes.js"}, f"{path.name}:{number} reads paletteCaught"
