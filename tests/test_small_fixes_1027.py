"""Owner reports, 2026-10-27: the popup agent's Send button, the graph fold
chevron touching its "?"."""

from __future__ import annotations

import re
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent


def test_the_popup_agent_has_a_send_button_that_takes_enters_path():
    html = (ROOT / "frontend/index.html").read_text(encoding="utf-8")
    bar = html[html.index('class="command-palette-bar"'):]
    bar = bar[: bar.index("</div>")]
    assert re.search(r'<button[^>]*id="command-palette-send"[^>]*aria-label="Send"', bar)
    js = (ROOT / "frontend/js/palette.js").read_text(encoding="utf-8")
    assert '$("command-palette-send").addEventListener("click", cmdPaletteSend)' in js
    keydown = js[js.index('cmdPaletteInput.addEventListener("keydown"'):]
    assert "cmdPaletteSend();" in keydown[: keydown.index("});")]


def test_the_graph_fold_chevron_stops_a_gap_short_of_the_help_button():
    css = (ROOT / "frontend/css/graph-lazy.css").read_text(encoding="utf-8")
    rule = css[css.index("#graph-options .graph-fold-wrap > details > summary"):]
    rule = rule[: rule.index("}")]
    assert "max(var(--control-h), var(--target-min)) + var(--space-" in rule


def test_the_first_answer_ticks_get_started_even_after_leaving_for_the_dashboard():
    """E2E first-run, 2026-10-27: the answer took 2.4 s in CI, the dashboard
    was opened at 0.8 s and drew "1 of 3 done" for good. The badge refresh
    that follows every saved answer redraws the steps on the first one."""
    js = (ROOT / "frontend/js/capture-ask.js").read_text(encoding="utf-8")
    body = js[js.index("async function loadAskHistoryBadge()"):]
    body = body[: body.index("\n}\n")]
    assert "if (stats.total === 1) renderFirstStepsLazy();" in body


def test_words_typed_before_the_palette_loaded_still_ask_for_their_notes():
    """E2E shell, 2026-10-27: Ctrl+K takes keys while app-palette.js loads,
    and the input listener that asks /search for matching notes is attached
    by that file, so the typed words got only the Search everything row."""
    js = (ROOT / "frontend/js/app-palette.js").read_text(encoding="utf-8")
    body = js[js.index("async function openPalette()"):]
    body = body[: body.index("\n}\n")]
    assert body.index('paletteAskNotes($("palette-input").value);') > body.index('renderPalette($("palette-input").value);')


def test_a_lasting_toast_steps_aside_for_the_buttons_of_the_section_in_use():
    """E2E first-run, 2026-10-27: at 1280 by 720 the search-by-meaning
    question (kept up until answered) covered the composer's Save, and the
    click landed on the toast for 90 s. A toast without a timer fades for
    the buttons of the focused control's form or section, and the check
    runs again when a toast arrives over a control already focused."""
    js = (ROOT / "frontend/js/status.js").read_text(encoding="utf-8")
    body = js[js.index("function toastYield(target = document.activeElement) {"):]
    body = body[: body.index("\n}\n")]
    assert 'target.closest("form, section")?.querySelectorAll("button")' in body
    assert "!el.toastTimer && work.some(" in body
    stack = js[js.index("function toastStack(box, change) {"):]
    assert 'if (box.id === "toast-box") toastYield();' in stack[: stack.index("\n}\n")]


def test_a_connector_drag_never_leaves_the_delete_target_up():
    """INBOX 1405, the owner 2026-10-27: dragging a connector drawn between
    two cards brought up "Drop here to delete" and it stayed until another
    object was clicked. Measured (scratchpad wbtrash.js): before, the target
    and the move gesture were still live after release; after, both clear,
    and a card dropped on the target is still deleted."""
    js = (ROOT / "frontend/js/whiteboard.js").read_text(encoding="utf-8")
    assert 'd._gesture = d._dragOriginalD == null ? null : wbBeginGesture(() => wbRestoreMove("sketch", d), true);' in js
    net = js[js.index('window.addEventListener("pointerup", () => setTimeout(() => {'):][:160]
    assert "if (wbGesture?.move) wbGesture = null;" in net and "wbTrashHide();" in net
