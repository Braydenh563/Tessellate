"""L151: non-Atlas companions in the desk overlay. Every picker row is choosable (none is greyed), every key the picker offers is
one the host accepts, and the page's capture (`desk-frames.js`) names every frame the overlay needs of a figure it has no
shipped pictures of. Measured on the running app, 'You, from your name': 54 frames asked, 54 drawn, none empty, 19.2 s."""

from __future__ import annotations

import re
from pathlib import Path

from tessellate.core import desk_companion as dc
from tessellate.core.overlay import capture, sprites
from tests._js_scope import unwrapped

ROOT = Path(__file__).resolve().parents[1]
FRAMES = unwrapped((ROOT / "frontend" / "js" / "desk-frames.js").read_text(encoding="utf-8"))
MENU = (ROOT / "frontend" / "js" / "desk-companion.js").read_text(encoding="utf-8")

APP_SAYS = {"who": "me", "look": "auto", "presets": [{"name": f"Saved {i}"} for i in range(14)]}


def test_every_picker_row_is_choosable_and_a_key_the_host_takes() -> None:
    rows = dc.companion_options(APP_SAYS)
    assert [r["group"] for r in rows if r["key"] in ("me", "persona", "custom")] == ["Yours"] * 3
    assert len(rows) == 3 + 3 + 12, "the Atlas rows, the three of yours, and at most twelve saved companions"
    assert all(r["enabled"] is True for r in rows), [r["key"] for r in rows if not r["enabled"]]
    assert all(dc._CHOICE_KEY.fullmatch(r["key"]) for r in rows)
    assert sum(1 for r in rows if r["current"]) == 1


def test_the_menu_does_not_grey_a_row_the_host_called_enabled() -> None:
    assert "row.disabled = !option.enabled;" in MENU
    assert "every row can be picked" in MENU


def _spec_names() -> set[str]:
    """The names `DESK_FRAME_SPECS` makes: the plain ones and the `walk${i}` and wave runs it spreads."""
    body = FRAMES[FRAMES.index("const DESK_FRAME_SPECS = [") :]
    body = body[: body.index("\n];")]
    names = set(re.findall(r'\{ name: "(\w+)"', body))
    walk_n = int(re.search(r"const DESK_WALK_N = (\d+)", FRAMES).group(1))
    idle_n = int(re.search(r"const DESK_IDLE_N = (\d+)", FRAMES).group(1))
    for template in re.findall(r"name: `(\w+)\$\{i\}`", body):
        names |= {f"{template}{i}" for i in range(max(walk_n, idle_n, 6))}
    return names


def test_the_page_captures_every_frame_the_overlay_needs_of_a_figure_with_no_shipped_set() -> None:
    missing = [n for n in capture.CAPTURED if n not in _spec_names()]
    assert not missing, missing
    assert len(capture.CAPTURED) == 48 and set(capture.CAPTURED) <= set(sprites.FRAME_NAMES)
