"""Focus mode can open and close the documents sidebar (INBOX 453 (1)).

The owner: "there should be a way to open and close the documents editor
sidebar when in full screen mode". The sidebar is one of the bands the mode
hides; the floating dock's Sidebar toggle brings it back as a panel fixed to
the window's left edge while the page gives up that room, the mirror of the
Suggestions panel on the right. `scratchpad/ui-sweeps/docfocussidebar.js`
measures the geometry; these lints hold the shapes.
"""

from __future__ import annotations

import re
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
FRONTEND = ROOT / "frontend"
CSS = sorted((FRONTEND / "css").glob("*.css"))


def _rules():
    for path in CSS:
        text = re.sub(r"/\*.*?\*/", "", path.read_text(encoding="utf-8"), flags=re.S)
        for match in re.finditer(r"(?:(?<=[{}])|\A)([^{}]+)\{([^{}]*)\}", text):
            yield path.name, match.group(1).strip(), match.group(2)


def _bar() -> str:
    html = (FRONTEND / "index.html").read_text(encoding="utf-8")
    tag = re.search(r"<div[^>]*id=\"doc-focus-bar\"[^>]*>", html)
    return html[tag.start(): html.index("\n    </div>", tag.start())]


def test_the_floating_dock_has_a_worded_sidebar_toggle() -> None:
    button = re.search(r"<button[^>]*id=\"doc-focus-sidebar\"[^>]*>.*?</button>", _bar(), flags=re.S)
    assert button, "focus mode has no way to open the sidebar"
    tag = button.group(0)
    assert 'aria-pressed="false"' in tag and 'aria-controls="doc-sidebar"' in tag
    assert "aria-label=" in tag and "title=" in tag
    assert re.search(r'<i class="ph [^"]*ph-lead"', tag), "the toggle has no icon"
    assert 'class="doc-focus-word">Sidebar<' in tag, "the toggle has no worded name"


def test_the_sidebar_is_a_fixed_left_panel_that_the_page_makes_room_for() -> None:
    rules = [(sel, body) for _, sel, body in _rules() if "doc-focus-sidebar" in sel and ".doc-sidebar" in sel]
    assert any("position: fixed" in b and "left:" in b for _, b in rules), (
        "the sidebar is not a panel fixed to the window's left edge in focus mode"
    )
    assert any("display: flex" in b for _, b in rules), "opening the sidebar does not show it"
    pad = [b for _, sel, b in _rules() if "doc-focus-sidebar" in sel and ".doc-main" in sel]
    assert any("padding-left" in b for b in pad), "the page does not give up the room the sidebar takes"
    assert any(
        "doc-focus-sidebar" in sel and "doc-focus-word" in sel or "button:has(.doc-focus-word)" in sel
        for _, sel, _ in _rules()
    ), "the toggle's name does not move to its label on a phone"


def test_the_sidebar_toggle_is_wired_restored_and_closed_by_escape() -> None:
    docs = (FRONTEND / "js" / "documents.js").read_text(encoding="utf-8")
    assert "const DOC_FOCUS_SIDEBAR_KEY" in docs
    setter = docs[docs.index("function setDocFocusSidebar("):]
    setter = setter[: setter.index("\n}\n")]
    for needle in ("aria-pressed", "aria-label", "sessionStorage", "doc-focus-sidebar"):
        assert needle in setter, f"setDocFocusSidebar does not handle {needle}"
    assert '$("doc-focus-sidebar")?.addEventListener("click"' in docs, "the toggle is not wired"
    enter = docs[docs.index("function toggleDocFocus("):]
    enter = enter[: enter.index("\n}\n")]
    assert "DOC_FOCUS_SIDEBAR_KEY" in enter and "setDocFocusSidebar(" in enter, (
        "a reload that restores focus mode does not restore the sidebar"
    )
    handler = docs.split('if (event.key !== "Escape" || event.defaultPrevented) return;', 1)[1].split("\n});", 1)[0]
    assert "doc-focus-sidebar" in handler and "setDocFocusSidebar(false)" in handler, (
        "Escape does not close the sidebar before it leaves focus mode"
    )
    assert handler.index("setDocFocusSidebar(false)") < handler.index("toggleDocFocus(false)"), (
        "Escape leaves focus mode before it closes the sidebar"
    )


def test_the_restore_runs_after_the_file_has_finished_loading() -> None:
    """Called inline, the restore reached `renderDocCounts`, whose
    `DOC_READING_WPM` is a `const` declared further down the file: a
    temporal-dead-zone error the surrounding `catch` swallowed after the
    class was set, so a reload brought back the mode and none of Tools, the
    sidebar or the idle watch."""
    docs = (FRONTEND / "js" / "documents.js").read_text(encoding="utf-8")
    restore = docs.index('sessionStorage.getItem(DOC_FOCUS_KEY) === "1"')
    assert "onDomReady(() => {" in docs[restore - 80 : restore], (
        "focus mode's reload restore runs inline, before the file's later constants exist"
    )
