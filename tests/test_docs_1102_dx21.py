"""Documents audit 1102 DX21: a focus stop nobody can see, and targets under 24px.

At 390 `#doc-counts` is 0px wide but was still a tab stop; the Read view's task
box was 14.7px and a footnote number 7 by 15 (WCAG 2.5.8 asks 24, and 44 under
touch is the app's own floor).
"""

from __future__ import annotations

from pathlib import Path

from tests._app_js import documents_text

ROOT = Path(__file__).resolve().parents[1]


def _css(name: str) -> str:
    return (ROOT / "frontend/css" / name).read_text(encoding="utf-8")


def test_the_counts_leave_the_tab_order_while_they_have_no_width():
    js = documents_text()
    #: On the file's own observer: a new one would raise the wake-source ratchet.
    assert 'watchDocGutter($("doc-counts"));' in js
    assert "entry.target.tabIndex = entry.target.clientWidth >= 1 ? 0 : -1" in js.split("docGutterObserver = new ResizeObserver")[1][:900]


def test_a_read_task_box_is_the_live_views_box_with_its_press_strip():
    js = documents_text()
    wire = js[js.index("function docWireReadTasks(") :]
    wire = wire[: wire.index("\n}\n")]
    assert '"cm-md-task-hit"' in wire and 'classList.add("cm-md-task")' in wire
    assert "box.click()" in wire, "a press on the strip is forwarded to its box"
    assert 'querySelectorAll("li.md-task input[type=checkbox]")' in wire
    # The strip is never under 24px tall, and the struck-through rule finds a boxed input.
    editor = _css("09-editor.css") + _css("library-lazy.css")  # L-ui-modernisation-31: moved rules
    assert "height: max(1.6em, 24px);" in editor
    assert "#doc-preview .md-task:has(input:checked) {" in editor
    # One box: the old Read-only native-box rule is gone.
    assert '#doc-preview .md-task > input[type="checkbox"]:not(:disabled)' not in _css("library-lazy.css")


def test_a_footnote_number_has_a_24px_target_and_a_44px_one_under_touch():
    css = _css("05-sidebars-themes.css")
    rule = css.split(".md-fn-ref a,\n.md-fn-back {")[1].split("}")[0]
    assert "padding: var(--space-3) var(--space-5);" in rule
    assert "margin-inline: calc(var(--space-5) * -1);" in rule, "the padding must not move the text"
    touch = css.split("@media (pointer: coarse) {\n  .md-fn-ref a,")[1].split("}")[0]
    assert "var(--space-6) var(--space-7)" in touch
    live = documents_text()
    assert '"var(--space-3) var(--space-5)"' in live.split('".cm-md-footnote-ref": {')[1].split("}")[0]
