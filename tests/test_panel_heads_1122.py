"""Source text: panel heads stay put while the body scrolls, and a moved or docked dialog lets go of the app (the owner
2026-11-22, via the hub: the Suggestions head and the Dictionary's head, count line and field scrolled away; the
Dictionary did not close on an outside press; after a dock or a drag the app stayed dimmed, blurred and inert).
Measured by scratchpad/ui-sweeps/panel-heads.js (a 400 px scroll moves no head; after a dock the dialog is not modal
and a press beside it reaches the app; an outside press and Escape close it).
"""

from __future__ import annotations

import re
from pathlib import Path

from tests._app_js import app_js_text


ROOT = Path(__file__).resolve().parents[1]
CSS = ROOT / "frontend" / "css"
HTML = (ROOT / "frontend" / "index.html").read_text(encoding="utf-8")
MOVABLE = (ROOT / "frontend" / "js" / "panel-movable.js").read_text(encoding="utf-8")
DICT = (ROOT / "frontend" / "js" / "documents-dictionary.js").read_text(encoding="utf-8")


def _rule(file: str, selector: str) -> str:
    text = (CSS / file).read_text(encoding="utf-8")
    start = text.index(selector + " {")
    return text[start : text.index("}", start)]


def test_the_suggestions_head_is_sticky_on_the_panel_ground() -> None:
    rule = _rule("05-sidebars-themes.css", ".doc-prose-panel > .doc-prose-head")
    assert "position: sticky" in rule and "top: calc(-1 * var(--space-3))" in rule
    # Its ground while stuck is the stuck-ground recipe (tests/test_nested_surfaces_1489.py).
    assert "background" not in rule


def test_the_dictionary_scrolls_its_body_not_its_head() -> None:
    dialog = re.search(r'<dialog id="doc-dictionary-dialog".*?</dialog>', HTML, re.S).group(0)
    body = dialog[dialog.index('<div class="doc-dictionary-body">') :]
    assert 'id="doc-dictionary-list"' in body and 'id="doc-smart-punctuation"' in body
    head_part = dialog[: dialog.index('<div class="doc-dictionary-body">')]
    for part in ("doc-dictionary-head", "doc-dictionary-count", "doc-dictionary-search"):
        assert part in head_part
    assert "overflow: hidden" in _rule("05-sidebars-themes.css", ".doc-dictionary-dialog[open]")
    assert "overflow-y: auto" in _rule("05-sidebars-themes.css", ".doc-dictionary-dialog > .doc-dictionary-body")


def test_an_outside_press_closes_every_modal_dialog_unless_it_is_kept_or_typed_in() -> None:
    # One rule for every `<dialog>`, markup or built (the hub 2026-11-22: "a test should list them so a
    # new one inherits the behaviour"). The rule reads any HTMLDialogElement, so a new dialog needs
    # nothing; a dialog that must stay open says `data-keep-open`, and this list may only shrink.
    app = app_js_text()
    rule = app[app.index("function dialogPressOutside(") :][:2000]
    assert 'window.addEventListener("pointerdown"' in rule and 'window.addEventListener("click"' in rule
    assert 'd.matches(":modal")' in rule and 'd.hasAttribute("data-keep-open")' in rule and "d._typed" in rule
    assert "requestClose" in rule and 'window.addEventListener("close"' in rule
    html = (ROOT / "frontend" / "index.html").read_text(encoding="utf-8")
    tags = re.findall(r"<dialog\b[^>]*>", html)
    assert len(tags) >= 18
    kept = sorted(re.search(r'id="([^"]+)"', t).group(1) for t in tags if "data-keep-open" in t)
    assert kept == ["recovery-key-dialog"]
    built = [p.name for p in (ROOT / "frontend" / "js").glob("*.js") if p.name != "app.js" and "data-keep-open" in p.read_text(encoding="utf-8")]
    assert built == []
    # The Dictionary's own copy went: one rule, not two.
    assert "pointerdown" not in DICT
    # A minimise or a re-open is not a close: what was typed still counts.
    assert "host._typed = typed;" in (ROOT / "frontend" / "js" / "panel-movable.js").read_text(encoding="utf-8")


def test_a_moved_or_docked_dialog_is_not_modal() -> None:
    sync = MOVABLE[MOVABLE.index("function panelModalSync(") :]
    sync = sync[: sync.index("\n  function ")]
    assert "panelReopen(host, !moved)" in sync and '"Escape"' in sync
    for caller in ("function panelSave(", "function panelReset("):
        body = MOVABLE[MOVABLE.index(caller) :]
        assert "panelModalSync(panel, st)" in body[: body.index("\n  }\n")]
    assert "if (en.isIntersecting) panelModalSync(" in MOVABLE


def test_a_moved_scrim_drops_the_blur_and_the_presses() -> None:
    lazy = (CSS / "panel-movable-lazy.css").read_text(encoding="utf-8")
    overlay = lazy[lazy.index('[data-panel-moved]:is(.modal-overlay, [id$="-overlay"]) {') :]
    assert "pointer-events: none" in overlay[: overlay.index("}")]
    assert "backdrop-filter: none" in _rule("07-whiteboard-misc.css", "dialog[data-panel-moved]::backdrop")
    assert "backdrop-filter: none" in _rule("01-forms-settings.css", ".modal-overlay[data-panel-moved]")


def test_every_modal_overlay_closes_on_an_outside_press_or_says_why_not() -> None:
    # A `.modal-overlay` closes by `wireBackdropClose` or by the shared rule pressing its own Close
    # (`#x-close` or `#x-cancel`). Kept open, with the reason: the skill run (its Cancel stops the run)
    # and the first-run tour (a stray press would end the welcome). This list may only shrink.
    html = (ROOT / "frontend" / "index.html").read_text(encoding="utf-8")
    kept = {"skill-run-overlay", "onboarding-overlay"}
    opens = [m for m in re.finditer(r"<div\b[^>]*>", html) if re.search(r'class="[^"]*\bmodal-overlay\b', m.group(0))]
    assert len(opens) >= 13
    for m in opens:
        oid = re.search(r'id="([^"]+)"', m.group(0)).group(1)
        if "data-keep-open" in m.group(0):
            assert oid in kept, oid
            continue
        body = html[m.end() : m.end() + 12000]
        assert re.search(r'<button[^>]*id="[^"]*-(close|cancel)"', body), oid
    app = app_js_text()
    assert "overlay._backdropWired = true;" in app and "o.querySelector(OVERLAY_CLOSE)?.click();" in app
