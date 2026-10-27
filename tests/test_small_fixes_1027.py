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


def test_board_thumbnails_are_not_faded_by_the_minimap_card_fill():
    """The owner, 2026-10-27: board and map thumbnails looked paled out on
    the light theme. A stored thumbnail is an element carrying the size class
    `board-minimap-card`, and the minimap's card fill (opacity 0.55) matched
    the whole picture. Measured: thumbnail opacity 0.55 before, 1 after."""
    css = (ROOT / "frontend/css/07-whiteboard-misc.css").read_text(encoding="utf-8")
    assert "rect.board-minimap-card,\n.board-minimap-object {" in css
    assert not re.search(r"(^|[\s,])\.board-minimap-card\s*[{,:]", css, re.M)


def test_the_image_tile_menu_chip_outranks_the_bare_icon_reset():
    """The owner, 2026-10-27: the image tiles' ⋯ could not be seen on the
    light theme. The chip rule of 2026-10-26 lost to the bare-icon reset
    (0,6,1) and drew transparent with a grey glyph. Measured after: panel at
    80% with blur, ink glyph, in both themes; glass off drops the blur."""
    css = (ROOT / "frontend/css/library-lazy.css").read_text(encoding="utf-8")
    sel = '.library-image-tile .library-image-actions > .menu-wrap > button.ghost.icon-only:not(.active):not([aria-pressed="true"]):not([aria-expanded="true"]) {'
    body = css[css.index(sel):]
    body = body[: body.index("}")]
    assert "color: var(--ink);" in body and "background: var(--modal-bg);" in body
    assert "backdrop-filter" not in body
    #: Glass only while the glass look is on (the owner, 2026-10-27).
    glass = css[css.index(':root:not([data-glass="off"]) ' + sel):]
    assert "backdrop-filter: var(--glass-filter-clear);" in glass[: glass.index("}")]
    off = (ROOT / "frontend/css/03-dashboard-widgets.css").read_text(encoding="utf-8")
    assert ':root[data-glass="off"] .library-image-tile .library-image-actions > .menu-wrap > button.ghost,' in off


def test_the_guide_leads_with_how_to_change_not_what_changed():
    """The owner, 2026-10-27: "How do I change the widgets?" answered with the
    Dashboard's 134-word inventory, which says "what changed" and "edited",
    over the sentence that says how. A past form of the doing asked
    describes; it does not instruct."""
    from tessellate.ai import composer, help_chat

    q = "How do I change the widgets?"
    line, _ = composer.help_line(q, help_chat.topics_for(q, "dashboard"))
    assert line.startswith("Customise, beside the search box, has Edit layout and Widgets")


def test_opening_the_guide_never_closes_it():
    """The owner, 2026-10-27: a starter chip pressed inside the open Guide
    ("How do I change the widgets?") shut the panel, since `openHelpChat`
    had become a toggle and the chip opens before it asks. Measured
    (scratchpad guidechip.js): after, the panel stays with the answer, and
    the status button still opens and closes it."""
    js = (ROOT / "frontend/js/help-chat.js").read_text(encoding="utf-8")
    body = js[js.index("function openHelpChat() {"):]
    body = body[: body.index("helpChatHome = {")]
    assert "if (document.querySelector('[data-sheet=\"guide\"]')) return null;" in body
    assert "helpChatSheetClose" not in body
    toggle = js[js.index("function toggleHelpChat() {"):]
    assert "helpChatSheetClose?.();" in toggle[: toggle.index("\n}\n")]
    wiring = (ROOT / "frontend/js/wiring.js").read_text(encoding="utf-8")
    assert '$("status-guide")?.addEventListener("click", () => {\n  toggleHelpChat();' in wiring


def test_the_guide_never_leads_with_a_whole_long_sentence():
    """INBOX 1406: "how do I see what changed" led with the Dashboard's
    134-word inventory. A lead is short: the Dashboard's first sentence is
    split, and any other sentence over 40 words leads with its best clause
    (the `;` clauses outside brackets), capitalised and ended."""
    from tessellate.ai import composer, help_chat

    for q, tab in (
        ("How do I see what changed?", "dashboard"),
        ("how do I see my streak", "dashboard"),
        ("how do I see the week digest", "dashboard"),
    ):
        line, topic = composer.help_line(q, help_chat.topics_for(q, tab))
        assert topic == "dashboard" and len(line.split()) <= 40, (q, line)
    q = "how do I see what changed"
    line, _ = composer.help_line(q, help_chat.topics_for(q, "dashboard"))
    assert "what changed since yesterday" in line
    #: Other questions that drew a long sentence: the voice topic's 45-word
    #: opener, and the slash commands, a 213-word list ended on "/".
    q = "how do I use voice"
    line, topic = composer.help_line(q, help_chat.topics_for(q, "notes"))
    assert topic == "voice" and len(line.split()) <= 40, line
    q = "how do I list my pinned notes with a slash command"
    line, topic = composer.help_line(q, help_chat.topics_for(q, "notes"))
    assert topic == "slash-commands" and line.startswith("/pinned"), line


def test_a_long_sentence_leads_with_the_clause_that_answers():
    from tessellate.ai import composer

    long = (
        "The panel has a tidy lead about layout and colour and other things that nobody asked about, "
        "with a great many words in it to run past the budget of forty words in all, and then some more; "
        "press Ctrl+K to open the palette from anywhere in the app; "
        "the rest of the sentence rambles on about unrelated features of the panel for a good while longer."
    )
    line, _ = composer.help_line("how do I open the palette", [{"id": "panel", "body": long}])
    assert line == "Press Ctrl+K to open the palette from anywhere in the app."
    short = "Press Ctrl+K to open the palette; Esc closes it again."
    line, _ = composer.help_line("how do I open the palette", [{"id": "panel", "body": short}])
    assert line == short


def test_a_clause_split_ignores_semicolons_in_brackets():
    from tessellate.ai import composer

    text = (
        "Pick a subject (a topic you keep writing about; a busy week; anything else you like to see) "
        "and the list narrows to it, which is useful when a great many notes pile up over the months and years; "
        "clear the filter to see every note again, whatever the subject was, in the order you wrote them."
    )
    clauses = composer._clauses(text)
    assert len(clauses) == 2 and clauses[0].count(";") == 2
