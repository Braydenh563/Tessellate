"""The colour popover lists the notebook's saved palettes (WHITEBOARD_PLAN, "Placed
from INBOX, 2026-11-01", item 3): "Save these colours as a palette" put them in the
Library, but the picker that colours a shape never showed them. One row of swatches
per palette, under the board's colours."""

import json
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
FMT = (ROOT / "frontend" / "js" / "whiteboard-format.js").read_text(encoding="utf-8")


def _kit_function(name: str) -> str:
    start = FMT.index(f"  function {name}(")
    depth, i = 0, FMT.index("{", start)
    while True:
        depth += FMT[i] == "{"
        depth -= FMT[i] == "}"
        i += 1
        if depth == 0:
            return FMT[start:i]


def test_saved_palettes_are_cleaned_before_they_are_shown():
    script = "\n".join([
        _kit_function("wbColourPaletteList"),
        """
const entries = [
  { kind: "palette", name: "Autumn", payload: { colours: ["#AA5500", "#aa5500", "#112233", "red", 7] } },
  { kind: "palette", name: "Empty", payload: { colours: [] } },
  { kind: "element", name: "Not one", payload: { colours: ["#000000"] } },
  { kind: "palette", name: "", payload: { colours: ["#abcdef"] } },
  ...Array.from({ length: 12 }, (_, i) => ({ kind: "palette", name: "P" + i, payload: { colours: ["#00000" + (i % 10)] } })),
];
console.log(JSON.stringify(wbColourPaletteList(entries)));
""",
    ])
    out = json.loads(subprocess.run(["node", "-e", script], capture_output=True, text=True, timeout=30, check=True).stdout)
    # Only palettes, only real hex colours, lower-cased and de-duplicated; none empty; at most eight rows.
    assert out[0] == {"name": "Autumn", "colours": ["#aa5500", "#112233"]}
    assert out[1] == {"name": "Palette", "colours": ["#abcdef"]}
    assert all(row["colours"] for row in out) and len(out) == 8


def test_the_popover_shows_them_under_the_board_colours():
    open_menu = FMT[FMT.index("async function wbOpenColourMenu"):]
    assert open_menu.index("Board colours") < open_menu.index("wbColour.palettes(") < open_menu.index("wbColour.opacity(")
    assert "palettes: wbColourPalettes" in FMT
    # The library index is fetched on demand, never at load, and without drawing the Library panel.
    assert 'apiJson("/board-library")' in _kit_function("wbColourPalettes")
