"""The back/forward list names places, it does not print entry text (INBOX 654).

The owner, with a screenshot of the status bar's history popup: "the nav
history popup doesnt have md or image etc rendering". A note row read
"Notes: Girl with bell image WallpaperEngineOverride_random_1.png" (the note's
whole opening, markers and file name included) and the Library's sub-tabs
repeated (Files, Images, Images).

The rows now live in `frontend/js/nav-history.js`, a lazy bundle with its own
stylesheet. The behaviour that can be run without a DOM is run here in node
against the real `notePreviewText`, `flattenNoteMarkdown` and `noteRowImage`
the app uses; the rendering itself is `scratchpad/ui-sweeps/navhistory-rows.js`.
"""

from __future__ import annotations

import json
import re
import shutil
import subprocess
from pathlib import Path

import pytest

from tests._app_js import app_js_text, frontend_text

ROOT = Path(__file__).resolve().parents[1]
JS = ROOT / "frontend" / "js"
NAV_HISTORY = (JS / "nav-history.js").read_text(encoding="utf-8")
#: Every script the helpers could live in: the boot list ends before the
#: dashboard, and `noteRowImage` is the dashboard rows' own.
SOURCE = app_js_text() + "\n" + (JS / "dashboard.js").read_text(encoding="utf-8")


def _grab(pattern: str, what: str) -> str:
    match = re.search(pattern, SOURCE, re.S | re.M)
    assert match, f"{what} is gone from the app's scripts"
    return match.group(0)


def _harness() -> str:
    """The app's own helpers a title is built from, then nav-history.js."""
    parts = [
        _grab(r"^const INLINE_MD =\n?[^\n]*;\n", "INLINE_MD"),
        _grab(r"^const STAGED_URL_PREFIX = [^\n]*;\n", "STAGED_URL_PREFIX"),
        _grab(r"^function isRenderableUrl\(url\) \{.*?^\}\n", "isRenderableUrl"),
        _grab(r"^const FIRST_MD_IMAGE = [^\n]*;\n", "FIRST_MD_IMAGE"),
        _grab(r"^function firstNoteImage\(content\) \{.*?^\}\n", "firstNoteImage"),
        _grab(r"^function noteRowImage\(entry\) \{.*?^\}\n", "noteRowImage"),
        _grab(r"^function stripFrontmatter\(text\) \{.*?^\}\n", "stripFrontmatter"),
        _grab(r"^function previewBlocks\(text\) \{.*?^\}\n", "previewBlocks"),
        _grab(r"^function notePreviewText\(content\) \{.*?^\}\n", "notePreviewText"),
        _grab(r"^function flattenNoteMarkdown\(md\) \{.*?^\}\n", "flattenNoteMarkdown"),
        _grab(r"^function clipText\(text, limit\) \{.*?^\}\n", "clipText"),
    ]
    return "\n".join(parts) + "\n" + NAV_HISTORY


def _run(expression: str):
    script = _harness() + f"\nprocess.stdout.write(JSON.stringify({expression}));"
    out = subprocess.run(["node", "-e", script], capture_output=True, text=True, check=True).stdout
    return json.loads(out)


needs_node = pytest.mark.skipif(not shutil.which("node"), reason="needs node")


@needs_node
@pytest.mark.parametrize(
    ("note", "title"),
    [
        # A heading: its words, no marker; the file name below it is not the title.
        ({"title": "Girl with bell", "content": "# Girl with bell\n\n![](/files/1)\n\nWallpaperEngineOverride_random_1.png"}, "Girl with bell"),
        # Inline markdown is rendered away, links keep their text.
        ({"title": None, "content": "**Bold** and *soft* [a link](https://example.com/x) title\n\nbody"}, "Bold and soft a link title"),
        # Block markers go.
        ({"title": None, "content": "- [[Wiki target]] first\nsecond"}, "Wiki target first"),
        # An image-only note: its caption, or Image.
        ({"title": None, "content": "![Girl with bell](/files/1)"}, "Girl with bell"),
        ({"title": None, "content": "![](/files/1)"}, "Image"),
        # A caption that is only a file name is not a caption.
        ({"title": None, "content": "![WallpaperEngineOverride_random_1.png](/files/1)"}, "Image"),
        # A properties block is never the title.
        ({"title": None, "content": "---\ntags: a\n---\nReal first line\nmore"}, "Real first line"),
        # Private notes never put their words in a list.
        ({"title": None, "content": "secret words", "is_private": True}, "Private note"),
        # Nothing at all.
        ({"title": None, "content": ""}, "Empty note"),
    ],
)
def test_a_note_title_is_one_plain_line(note, title):
    got = _run(f"navHistoryNoteTitle({json.dumps(note)})")
    assert got == title
    assert not re.search(r"#|!\[|\]\(|\*\*|https?:", got)


@needs_node
def test_a_long_title_is_cut_not_wrapped():
    got = _run(f"navHistoryNoteTitle({json.dumps({'title': None, 'content': 'word ' * 60})})")
    assert len(got) <= 60 and got.endswith("…")


@needs_node
def test_consecutive_identical_rows_fold_and_history_is_untouched():
    stack = [{"id": k} for k in ["a", "b", "b", "b", "c", "c", "b"]]
    rows = {"a": "A", "b": "B", "c": "C"}
    expr = (
        f"(() => {{ const stack = {json.dumps(stack)}; const stackBefore = JSON.stringify(stack);"
        f" const rows = {json.dumps(rows)};"
        " const out = navHistoryGroups(stack, (e) => ({ key: rows[e.id] }), 12);"
        " return { keys: out.groups.map((g) => g.row.key), index: out.groups.map((g) => g.index),"
        " lowest: out.groups.map((g) => g.lowest), older: out.older, untouched: JSON.stringify(stack) === stackBefore }; })()"
    )
    got = _run(expr)
    # Newest first: b (6), c (5, 4), b (3, 2, 1), a (0). Runs fold; the two b
    # runs are separated by c, so they stay two rows.
    assert got["keys"] == ["B", "C", "B", "A"]
    assert got["index"] == [6, 5, 3, 0]
    assert got["lowest"] == [6, 4, 1, 0]
    assert got["older"] == 0 and got["untouched"] is True


@needs_node
def test_the_list_is_capped_and_says_how_much_is_left():
    stack = [{"id": k} for k in range(20)]
    expr = (
        f"(() => {{ const out = navHistoryGroups({json.dumps(stack)}, (e) => ({{ key: String(e.id) }}), 5);"
        " return { n: out.groups.length, older: out.older, first: out.groups[0].index, last: out.groups[4].index }; })()"
    )
    assert _run(expr) == {"n": 5, "older": 15, "first": 19, "last": 15}


def test_the_rows_are_a_lazy_bundle_with_its_own_stylesheet():
    app = (JS / "app.js").read_text(encoding="utf-8")
    assert 'navHistory: ["/css/nav-history-lazy.css", "/js/nav-history.js"]' in app
    nav = (JS / "navigation.js").read_text(encoding="utf-8")
    assert "function renderNavHistoryMenu" not in nav, "the rows moved out of the boot script"
    opener = re.search(r"async function openNavHistoryMenu\(anchorEl\) \{(.*?)\n\}", nav, re.S)
    assert opener, "openNavHistoryMenu must be async: it fetches the rows first"
    assert 'ensureModule("navHistory")' in opener.group(1)
    assert opener.group(1).index("ensureModule") < opener.group(1).index("renderNavHistoryMenu()")


def test_a_row_is_an_icon_a_lazy_thumbnail_and_a_two_line_label():
    # The thumbnail is the dashboard rows' own helper and loads lazily, from
    # the URL the note already holds: no request of its own.
    assert "noteRowImage(" in NAV_HISTORY and "mediaSrc(row.image.url)" in NAV_HISTORY
    assert 'thumb.loading = "lazy"' in NAV_HISTORY
    for token in ("nav-history-kind", "nav-history-title", "nav-history-sub", "nav-history-thumb", 'aria-current", "page"'):
        assert token in NAV_HISTORY, token
    # Kinds the owner named: note, document, board, map, tab.
    for fragment in ('kind: "note"', 'kind: "document"', 'kind: isMap ? "map" : "board"', 'kind: "tab"'):
        assert fragment in NAV_HISTORY, fragment
    # Text goes in with textContent, never innerHTML.
    assert "innerHTML" not in NAV_HISTORY


def test_the_row_text_is_never_the_raw_entry_label():
    """`entryLabel` still names the Back/Forward tooltips; the list's rows are
    built from the note itself, so its flattened opening cannot come back."""
    assert "noteLabel(" not in NAV_HISTORY
    assert "navHistoryNoteTitle(note)" in NAV_HISTORY


# The history's X sits inside the row's fill and Clear is a quiet footer button (INBOX 845, 846).

CSS = ROOT / "frontend" / "css"


def test_the_nav_history_x_is_drawn_inside_the_rows_fill():
    """"there's an excessive gap on the right for the x close buttons on the
    nav history, can you integrate them together??" (INBOX 846). Measured at
    1440: the row's button filled 177px and the X sat 4px past it (28px,
    outside the highlight). The X is laid over the button's right end, the fill
    follows the row, and the button yields the X's width only while shown."""
    css = (CSS / "nav-history-lazy.css").read_text(encoding="utf-8")
    row = css[css.index(".nav-history-row {") :].split("}", 1)[0]
    assert "position: relative;" in row
    remove = css[css.index(".nav-history-remove {") :].split("}", 1)[0]
    assert "position: absolute;" in remove and "opacity: 0;" in remove
    fill = css[css.index(".nav-history-row:hover > .nav-history-item,") :].split("}", 1)[0]
    assert "background-color: var(--ghost-btn-bg);" in fill and "padding-inline-end:" in fill


def test_the_nav_history_clear_action_is_a_quiet_footer_text_button():
    """"can you redesign or change the design of this 'clear this list'
    button??" (INBOX 845). It was a bordered, tinted button with a trash icon on
    a row of its own (32px tall, a 1px border, a lilac fill). Now one footer row:
    the older-steps count left, a muted text action right, the destructive ink
    only under the pointer or keyboard; no icon, no fill at rest."""
    js = (JS / "nav-history.js").read_text(encoding="utf-8")
    assert "ph:trash" not in js and 'foot.className = "nav-history-foot";' in js
    assert 'clear.className = "nav-history-clear";' in js
    css = (CSS / "nav-history-lazy.css").read_text(encoding="utf-8")
    rest = css[css.index(".nav-history-clear {") :].split("}", 1)[0]
    assert "background: none;" in rest and "color: var(--muted);" in rest
    hover = css[css.index(".nav-history-clear:hover,") :].split("}", 1)[0]
    assert "color: var(--error);" in hover


# The places list can lose a row or be cleared (owner 2026-10-10).


def test_the_places_list_can_lose_a_row_or_be_cleared():
    """"no way to clear the destination history or delete individual
    records??". Measured on six visits: the X (28 px, shown on hover) took
    Library off (5 left, current kept), Back then walked the edited stack to
    Timeline, and Clear this list left only where you are (Back disabled)."""
    nav = frontend_text("nav-history.js")
    assert "function navHistoryForget(group, event)" in nav and "function navHistoryClear(event)" in nav
    assert "tabHistory.edited = true;" in nav
    assert "tabHistory.edited ||" in frontend_text("router.js")
