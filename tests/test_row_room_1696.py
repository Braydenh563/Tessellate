"""A row picked at a sidebar's edge keeps a row of room (INBOX 1696 e).

The owner, with a screenshot of the Settings nav, "Account & security" cut by
the scroller's bottom edge: "if I select something right at the bottom in the
settings sidebar and other sidebars, I feel it should scroll a little down to
give comfortable room for the selected item unless it is the last item".
Measured before at 1440 (scratchpad room sweep): the Settings nav's picked
row ended 12px under the edge (560 high), a notes sidebar row 3.3px above it
(260 high), the manual's contents row 0.2px (440 high). After: 32, 33.3 and
24.2, each at least the row's own height. The arithmetic runs here in node
against the app's own helper; the clicks are the sweep's.
"""

from __future__ import annotations

import json
import re
import shutil
import subprocess
from pathlib import Path

import pytest

JS = Path(__file__).resolve().parents[1] / "frontend" / "js"
SETTINGS = (JS / "settings.js").read_text(encoding="utf-8")


def _helper() -> str:
    match = re.search(r"^nearestScrollParent\.reveal = function revealRow\(.*?^\};\n", SETTINGS, re.S | re.M)
    assert match, "nearestScrollParent.reveal is gone from settings.js"
    return match.group(0)


def _scroll(box_top: float, box_bottom: float, row_top: float, row_h: float, scroll_top: int = 100, window_h: float = 900):
    """The scrollTop the helper asks for, or None when it leaves the box alone."""
    script = (
        "function nearestScrollParent() { return null; }\n"
        f"const innerHeight = {window_h};\n"
        "const document = { documentElement: {} };\n"
        + _helper()
        + f"const box = {{ scrollTop: {scroll_top}, asked: null, getBoundingClientRect: () => ({{ top: {box_top}, bottom: {box_bottom} }}),"
        " scrollTo(o) { this.asked = o.top; } };\n"
        f"const row = {{ isConnected: true, getBoundingClientRect: () => ({{ top: {row_top}, bottom: {row_top + row_h}, height: {row_h} }}) }};\n"
        "nearestScrollParent.reveal(row, box);\n"
        "process.stdout.write(JSON.stringify(box.asked));"
    )
    return json.loads(subprocess.run(["node", "-e", script], capture_output=True, text=True, check=True).stdout)


needs_node = pytest.mark.skipif(not shutil.which("node"), reason="needs node")


@needs_node
def test_a_row_cut_by_the_bottom_edge_gets_its_own_height_below():
    #: The Settings nav before: a 32px row 12px under a 425px box's edge.
    asked = _scroll(box_top=100, box_bottom=525, row_top=505, row_h=32)
    #: 505 + 32 - 525 = 12 under, plus 32 of room: the row moves up 44.
    assert asked == 100 + 44


@needs_node
def test_a_row_flush_with_the_top_edge_gets_its_own_height_above():
    asked = _scroll(box_top=100, box_bottom=525, row_top=104, row_h=32)
    assert asked == 100 - 28


@needs_node
def test_a_row_with_room_already_is_left_alone():
    assert _scroll(box_top=100, box_bottom=525, row_top=300, row_h=32) is None


@needs_node
def test_the_edge_is_the_one_seen_when_the_box_runs_past_the_window():
    #: A sidebar 40px taller than the window: the room is kept at the window's edge.
    asked = _scroll(box_top=0, box_bottom=300, row_top=230, row_h=30, window_h=260)
    assert asked == 100 + 30


@needs_node
def test_a_short_box_asks_half_its_room_at_most():
    #: Two rows high: a full row each side would push the row out the other edge.
    asked = _scroll(box_top=0, box_bottom=60, row_top=40, row_h=30)
    assert asked == 100 + 25


@needs_node
def test_fractions_round_away_from_the_row():
    #: scrollTop rounds; a 0.3px shortfall left the room 32.3 for a 32.6 row.
    asked = _scroll(box_top=0, box_bottom=153, row_top=117.4, row_h=32.6)
    assert asked == 100 + 30


def test_every_sidebar_pick_goes_through_the_one_helper():
    sites = {
        "settings-find.js": "nearestScrollParent.reveal(link, box, !still);",
        "library.js": "    nearestScrollParent.reveal(target);\n  };\n  const expanded",
        "manual.js": "if (current) nearestScrollParent.reveal(current.jump, contents);",
    }
    for name, site in sites.items():
        assert site in (JS / name).read_text(encoding="utf-8"), name
    #: The Settings nav, and the notes sidebar: its pick redraws it inside the row's click, so the list's own listener reads the redrawn row.
    #: A frame after the switch (INBOX 1111): the walk's style reads laid the window out inside the press.
    assert 'afterFrames(() => nearestScrollParent.reveal(document.querySelector(`#settings-nav button[data-section="${name}"]`)), 1);' in SETTINGS
    assert """$("category-list")?.addEventListener("click", (event) => nearestScrollParent.reveal(event.currentTarget.querySelector('li[aria-current="true"]')));""" in SETTINGS
    #: The helper and the sidebar's wiring stay out of the eager scripts' gzip budget (notes-list.js and menus.js).
    for name in ("notes-list.js", "menus.js"):
        assert "nearestScrollParent.reveal" not in (JS / name).read_text(encoding="utf-8"), name
    #: The follow's old 8px pad is gone, not kept beside the helper.
    assert "const pad = 8;" not in (JS / "settings-find.js").read_text(encoding="utf-8")


def test_a_short_window_scrolls_the_manual_contents_rather_than_squeezing_them():
    css = (JS.parent / "css" / "manual-lazy.css").read_text(encoding="utf-8")
    rule = re.search(r"^\.manual-jump \{(.*?)^\}", css, re.S | re.M)
    assert rule and "flex-shrink: 0;" in rule.group(1)
