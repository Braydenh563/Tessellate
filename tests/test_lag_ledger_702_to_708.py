"""Source pins for the lag rows L702 to L708 and L-general-34.

Each row was measured in a Playwright run at a 4x CPU throttle (CDP `Emulation.setCPUThrottlingRate`),
medians of at least five runs, before and after in the same session; the numbers are in the
CHANGELOG lines and the LEDGER rows. These pins hold the shape of each fix so a later edit
cannot put the forced read back.
"""

from __future__ import annotations

import re
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
JS = ROOT / "frontend" / "js"
CSS = ROOT / "frontend" / "css"


def _fn(text: str, head: str) -> str:
    """The body of the function whose head line starts with `head`, by brace depth."""
    start = text.index(head)
    open_at = text.index("{", start)
    depth = 0
    for i in range(open_at, len(text)):
        depth += {"{": 1, "}": -1}.get(text[i], 0)
        if depth == 0:
            return text[start : i + 1]
    raise AssertionError(f"{head} does not close")


# L702: the equation palette's first draw reads no layout, and its groups below the fold are not laid out.
def test_l702_first_palette_draw_reads_no_layout() -> None:
    editor = (JS / "math-editor.js").read_text(encoding="utf-8")
    draw = _fn(editor, "  const draw = () => {")
    assert "const again = drawn;" in draw
    # The scroll height and the group rects are read on a redraw only.
    assert "again ? scroller?.scrollHeight" in draw
    assert "if (!again) return markFirst();" in draw
    assert draw.index("markFirst()") < draw.index("\n    mark();")


def test_l702_palette_groups_below_the_fold_skip_layout() -> None:
    css = (CSS / "math-editor-lazy.css").read_text(encoding="utf-8")
    rule = re.search(r"\.math-editor-grid \{([^{}]*)\}", css)
    assert rule and "content-visibility: auto" in rule.group(1)
    assert "contain-intrinsic-size" in rule.group(1)




def test_l705_timeline_scroll_to_today_lays_out_once():
    body = _fn((JS / "timeline.js").read_text(), "function timelineScrollToToday")
    assert "window.innerHeight" in body
    assert "box.clientHeight;" not in body.split("feed.style.paddingBottom")[0]


def test_l705_notes_rail_measures_after_layout():
    text = (JS / "notes-list.js").read_text() + (JS / "notes-wire.js").read_text()
    render = _fn(text, "async function renderNotesRail")
    assert 'renderNotesRail.ro?.observe($("entry-list"))' in render
    assert "getBoundingClientRect" not in render
    assert "ResizeObserver" in text


def test_l705_art_sketch_starts_without_a_layout_read():
    text = (JS / "dash-art.js").read_text()
    setup = _fn(text, "p.setup = () =>")
    assert "clientWidth" not in setup
    assert "artLastWidth" in setup
    assert "artLastWidth = next" in text


def test_l706_the_look_is_never_written_on_the_companion_itself():
    """A write on `#nm-buddy` restyled its 647 descendants (109 ms at 4x); on the readers it is 0.4 to 1.1 ms."""
    text = (JS / "avatars.js").read_text()
    assert not re.search(r'buddy\.style\.setProperty\("--nmb-(ex|ey|hx)"', text)
    assert "nameMarkBuddyAim.set = (buddy, name, value) => {" in text
    assert re.search(r'@property --nmb-ex \{ syntax: "<number>"; inherits: false;', (CSS / "08-consistency.css").read_text())
