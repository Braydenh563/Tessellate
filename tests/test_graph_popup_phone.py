"""INBOX 883 and 884: the graph node panel's action row on a phone.

The owner: the buttons "wrap onto like 3 different rows when on phone", and
"i have no clue what the buttons do as I cant hover over them". The row is one
line of words plus a kebab where a finger is the pointer, and the icons-only
row where a tooltip can be read. INBOX 1400 (the owner: the popups "could be
improved", the tools "aren't really easy to understand") moved the intent:
every width now has worded buttons and a kebab, four words where there is
room (Open, Focus, Pin, Link), two on a phone. DOM behaviour is measured by
`scratchpad/ui-sweeps/graphpopupphone.js`; these pin the source shape."""

import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
GRAPH = (ROOT / "frontend" / "js" / "graph.js").read_text(encoding="utf-8")
CSS = (ROOT / "frontend" / "css" / "07-whiteboard-misc.css").read_text(encoding="utf-8")
RESPONSIVE = (ROOT / "frontend" / "css" / "10-responsive.css").read_text(encoding="utf-8")


def _body(name: str) -> str:
    start = GRAPH.index(f"function {name}(")
    return GRAPH[start : GRAPH.index("\nfunction ", start + 10)]


def test_the_compact_row_is_two_worded_buttons_and_a_kebab() -> None:
    body = _body("renderGraphPopupActions")
    assert "GRAPH_POPUP_COMPACT" in GRAPH
    assert re.search(r'GRAPH_POPUP_COMPACT = "\(max-width: 599\.98px\), \(hover: none\)"', GRAPH)
    assert "kebabMenu(" in body, "the overflow is the app's one menu recipe"
    assert '["open", "link"]' in body, "on a phone two actions keep a button"
    assert '["open", "focus", "pin", "link"]' in body, "with room, the four moves a map is for"
    assert "ph:${a.icon} ${a.short || a.word}" in body, "the shown buttons carry their word"


def test_every_action_has_a_word_and_a_title_in_one_list() -> None:
    body = _body("graphPopupActionList")
    keys = re.findall(r'key: "(\w+)"', body)
    assert keys == ["open", "similar", "trace", "grow", "focus", "pin", "link", "remind", "favourite", "bin"]
    assert len(re.findall(r"\bword:", body)) == 10 and len(re.findall(r"\btitle:", body)) == 10
    assert "danger: true" in body, "the bin stays the red row"


def test_the_compact_row_never_wraps() -> None:
    rule = re.search(r"\n\.graph-popup-actions \{([^}]*)\}", CSS)
    assert rule and "flex-wrap: nowrap" in rule.group(1)


def test_the_fab_does_not_float_over_the_panels_kebab() -> None:
    #: The rule was scoped to the graph's own path in dec5b0b (OPEN 813: a bare
    #: :has() re-matched on every board write); the intent, no fab while the
    #: popup or the new-note panel is open, is unchanged.
    assert re.search(r"\.tab-page:has\(> #graph-card > #graph-box > :is\(#graph-popup, #graph-new\):not\(\.hidden\)\) > \.dock-fab \{\s*display: none;", RESPONSIVE)


def test_a_sheet_never_lands_focus_on_a_select_under_touch() -> None:
    """INBOX 885: tapping the graph's settings button opened the Layout
    dropdown by itself, because `openSheet` focused the first `select`."""
    shell = (ROOT / "frontend" / "js" / "phone-shell.js").read_text(encoding="utf-8")
    start = shell.index("function openSheet(")
    body = shell[start : shell.index("\n}\n", start)]
    assert '(hover: none), (pointer: coarse)' in body
    touch = re.search(r"touchOnly\s*\?\s*\[\.\.\.card\.querySelectorAll\(\"([^\"]+)\"\)\]", body)
    assert touch, "the touch branch has its own field selector"
    assert "select" not in touch.group(1), "no select is auto-focused under touch"
    assert "document.activeElement === target" in body, "a refused focus falls through to the next landing"
