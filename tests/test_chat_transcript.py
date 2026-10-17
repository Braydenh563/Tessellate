"""The chat transcript: what it costs to draw, and what a reply looks like
(the 2026-09-26 chat pass, `scratchpad/ui-sweeps/chataudit.js`).

The numbers live in the sweep, which needs a browser; what these hold is the
shape that produced them, so a later change cannot quietly undo it.
"""

from __future__ import annotations

import re
from pathlib import Path

from tests._app_js import app_js_text, frontend_text

ROOT = Path(__file__).resolve().parents[1]
CSS = "\n".join(p.read_text(encoding="utf-8") for p in sorted((ROOT / "frontend" / "css").glob("*.css")))


def _function(source: str, name: str) -> str:
    start = source.index(f"function {name}(")
    return source[start : source.index("\n}\n", start)]


def test_a_reply_head_is_drawn_once_per_face_and_copied() -> None:
    """Opening a 150-turn chat took 939ms when every reply built its own
    head (a p5 emblem each); copying the first cut it to 410ms. The persona
    heads (2026-09-27) keep that: the first reply of a face draws it, every
    later one is a deep copy, and no reply head starts a p5 sketch
    (chatheads.js: 0 canvases in 150 replies)."""
    app = app_js_text()
    paint = _function(app, "paintPersonaAvatar") + _function(app, "assistantAvatar")
    assert "renderEmblem" not in paint, "a reply head builds a p5 sketch again"
    assert "chatHeadSources.get(key)" in paint
    assert "source.cloneNode(true)" in paint or "face.cloneNode(true)" in paint
    assert paint.count("chatHeadSources.set(") == 2, "one per kind of face: a persona's, Atlas's"
    key = _function(app, "chatHeadKey")
    for part in ("size", "atlasLook()", "atlasStyle()", "name"):
        assert part in key, f"the copy is not keyed on {part}: a stale face would be copied"


def test_a_code_block_in_an_answer_is_not_a_run_of_inline_chips() -> None:
    """`.msg.assistant .bubble-answer code` matched a fenced block's `code`
    too and out-ranked its reset, so every line wore an inline chip."""
    rules = re.findall(r"\.msg\.assistant \.bubble-answer ([^{]*)code \{", CSS)
    assert rules, "the answer's inline code rule is gone"
    for prefix in rules:
        assert ":not(pre) >" in prefix, "inline code styling reaches the code inside a <pre> again"


def test_escape_stops_the_answer_and_the_stop_button_holds_the_keyboard() -> None:
    """CHAT_PLAN section 6: "Escape stops streaming". Only Ctrl+. did, and the
    composer is disabled mid-answer, so the focus fell to the page. Measured
    by chataudit.js, part keys: Escape stopped nothing before; after, 34ms,
    with the Stop button holding the focus while the answer streams."""
    app = app_js_text()
    esc = app[app.index("//: **Escape stops the answer being written**") :]
    esc = esc[: esc.index("\n});\n")]
    assert 'document.addEventListener("keydown"' in esc, "Escape must be heard on the page: the box is disabled mid-answer"
    assert "chatController.abort()" in esc
    assert '$("tab-chat").classList.contains("hidden")' in esc, "Escape on another tab must not stop a chat"
    assert "event.defaultPrevented" in esc, "an Escape a menu or dialog already used must be left alone"
    send = _function(app, "sendChatMessage")
    assert '$("chat-stop").focus(' in send, "the Stop button no longer takes the focus while the answer streams"


def test_escape_leaves_an_answer_being_written_in_another_chat_alone() -> None:
    """The review of 2026-09-27: `chatController` outlives a switch, since a
    turn keeps streaming into the chat it was asked in while the reader opens
    another (`releaseChatComposer` hides Stop and hands the box back). Escape
    keyed on the controller alone, so an Escape in the new chat's box stopped
    an answer nobody could see. Measured with the fake answer model: streaming
    in chat A, New chat, Escape in the box: A's answer stopped (after: still
    streaming). The Stop button is on screen exactly while the chat on screen
    is being answered, so Escape asks it."""
    app = app_js_text()
    esc = app[app.index("//: **Escape stops the answer being written**") :]
    esc = esc[: esc.index("\n});\n")]
    guard = esc.index('$("chat-stop").classList.contains("hidden")')
    assert guard < esc.index("chatController.abort()")


def test_the_streams_end_gives_the_box_the_focus_only_from_the_stop_button() -> None:
    """The review of the chat pass (2026-09-27): the stream's end called
    `input.focus()` whenever the chat was on screen, so a reader who had
    moved to the search box or the sidebar while the answer streamed had
    the box take the focus from them as it ended. Only from the Stop button
    (which took it when the answer began) or from nowhere."""
    app = app_js_text()
    end = app[app.index("// The composer belongs to whatever conversation is on screen.") :]
    end = end[: end.index("clearPending();")]
    assert 'document.activeElement === $("chat-stop")' in end
    assert "if (fromStop) input.focus();" in end
    assert "\n      input.focus();\n" not in end, "the box takes the focus unconditionally again"


def test_enter_on_a_citation_mark_moves_the_keyboard_into_the_peek() -> None:
    """The peek is lifted to <body>, so Tab from a mark reaches the next mark,
    never the peek: its preview and Open note were unreachable in sequence
    (chatkeys.js, the review of 2026-09-27: Enter, then Tab, both left the
    keyboard on the marks). A click with no pointer (`detail` 0) moves the
    focus onto the preview; Escape brings it back."""
    app = app_js_text()
    marker = _function(app, "citationMarker")
    click = marker[marker.index('link.addEventListener("click"') :]
    click = click[: click.index("\n  });\n")]
    assert "event.detail === 0" in click
    assert '.citation-peek-preview")?.focus(' in click
    close = _function(app, "closeCitationPeek")
    assert "link.focus({ preventScroll: true })" in close
    #: And that focus must not open the peek again: the mark opens its peek
    #: on focus, so the focus a closing peek handed back reopened it (Escape
    #: from inside the peek left it on the page, measured by chatkeys.js).
    assert "citationPeekState.restoring = true" in close
    focus = marker[marker.index('link.addEventListener("focus"') :]
    focus = focus[: focus.index("\n  });\n")]
    assert "if (citationPeekState.restoring) return;" in focus


def test_tab_off_either_end_of_a_pinned_peek_closes_it_at_the_mark() -> None:
    """The peek is at the end of <body> and a pinned one ignores focusout, so
    Tab past Open note left it open until Escape (OPEN.md, 2026-09-27)."""
    peek = _function(app_js_text(), "openCitationPeek")
    keys = peek[peek.index('panel.addEventListener("keydown"') :]
    keys = keys[: keys.index("\n  });\n")]
    assert 'event.key !== "Tab"' in keys and "event.shiftKey ? 0 : stops.length - 1" in keys
    assert "closeCitationPeek({ restoreFocus: true })" in keys


def test_a_grounding_chip_fits_its_answer_and_says_its_sentences_in_characters() -> None:
    """At 390 an answer is 288px wide and the chips were 352px, running 79px
    past the bubble; and the chip's tooltip printed the answer's Markdown
    (6 of 9 tooltips in the seeded chats showed `**`, 0 after)."""
    chip = re.search(r"\n\.result-reason-chip \{([^}]*)\}", CSS)
    assert chip, "the chip rule is gone"
    assert "max-width: min(22rem, 100%)" in chip.group(1), "the chip may be wider than the answer holding it again"
    grounding = _function(app_js_text(), "renderAnswerGrounding")
    assert 'chip.title = plainText(forSentences.join(" "))' in grounding, "the tooltip prints raw Markdown again"


def test_a_touch_action_row_has_room_of_its_own_under_its_message() -> None:
    """Under `(hover: none)` the action row is always shown, positioned below
    its bubble; with no room kept for it, a question's Copy, Edit and Delete
    lay 31px over the answer beneath (0 after, chataudit.js at 390)."""
    sheet = (ROOT / "frontend" / "css" / "02-chat-graph.css").read_text(encoding="utf-8")
    touch = sheet[sheet.index("@media (hover: none)") :]
    touch = touch[: touch.index("\n}\n")]
    assert re.search(
        r"#chat-messages > \.msg:has\(> \.msg-actions\) \{\s*margin-bottom: calc\(var\(--target-min\) \+ var\(--space-2\)\);",
        touch,
    ), "the always-shown touch row has no room of its own and sits on the next message"


def test_a_citation_mark_takes_a_finger_sized_tap_on_a_touch_screen() -> None:
    """The mark opens the peek, the only way to a source on a phone, and was
    10 by 13px: a tap 8px off any edge missed. An invisible box `--target-min`
    tall takes it (23 by 44px measured at 390, the line's own height unchanged
    at 46px); at every width since Brief 88, where it was 10 by 13 at 1440."""
    sheet = (ROOT / "frontend" / "css" / "02-chat-graph.css").read_text(encoding="utf-8")
    after = sheet[sheet.index("\n.answer-citation-link::after {") :]
    after = after[: after.index("\n}\n")]
    assert "height: var(--target-min)" in after, "the mark's touch box is not the touch floor's height"
    assert "position: absolute" in after, "the touch box must not take room in the line"


def test_a_bubbles_hover_row_hangs_over_its_own_foot_not_the_next_message() -> None:
    """CHAT_PLAN (OPEN.md triage): hung 2px under its bubble, the 25px row
    overran the 13px between messages and lay 7 to 13px across the answer
    under a question at 640 to 820. It now starts inside its own bubble's
    foot padding, 2px under the last line (a probe, 640 and 1280).

    2026-10-06 (the owner: "these buttons are too high and clash with the
    message bubble"): the row now hangs just below its bubble, in the room
    #chat-messages' gap keeps for it (measured: 2px under the bubble, 15px
    clear of the next message at 1440)."""
    rule = CSS[CSS.index(".msg-actions {\n  position: absolute;") :]
    rule = rule[: rule.index("\n}")]
    assert "top: calc(100% + var(--space-1));" in rule
    assert "100% + 2px" not in rule


# The owner's 2026-10-10 list: chat, Ask, first-run and small UI items.


def test_a_finished_runs_bar_goes():
    """"says done but the bar is still there??" (the Agent activity row
    "Installing 1 package", Done, with its bar at 1 of 1). Measured: a run at
    60% shows its bar; after `endAgentRun` the bar is hidden and the detail
    line stays."""
    js = frontend_text("agent-activity.js")
    assert 'const bar = run.state === "running" && fraction !== null;' in js
    assert 'run.bar.classList.toggle("hidden", !bar);' in js


def test_a_slash_row_that_opens_a_picker_waits_for_the_press_to_end():
    """"I tried to press a note on the slash menu in the chat tab and the
    panel flickered then nothing happened". Reproduced with a press held
    250 ms: the picker opened before mouseup and the press's own click closed
    it (8 of 8 samples hidden). After: open in all 8 for a held press, a fast
    click and Enter, for A note and A document."""
    editor = frontend_text("editor.js")
    assert "editorMenuState.pressing = true;" in editor and "editorMenuState.pressing = false;" in editor
    commands = editor[editor.index("function chatCommands() {") :][:3000]
    assert 'document.addEventListener("mouseup", () => setTimeout(fn), { once: true, capture: true });' in commands
    assert "const pick = (source) => afterPress(" in commands
    assert "const press = (id) => afterPress(" in commands


def test_the_ask_again_row_has_its_menu():
    """"There's no way to clear your ask history" (the Ask again chips).
    Measured: the row's ⋯ (28 px, on the chips' line) lists Forget per
    question and Clear question history; Forget drops one chip, Clear hides
    the row. Backend: tests/test_recent_questions_surface.py."""
    assert 'ensureModule("askHistory").then(() => askAgainMenu(box, questions));' in frontend_text("status.js")
    ask = frontend_text("ask-history.js")
    assert "function askAgainMenu(box, questions)" in ask
    assert 'box.appendChild(kebabMenu(items, "Ask again options"));' in ask
    clear = ask[ask.index("async function clearAskHistory()") :][:900]
    assert "askHistoryRepaint();" in clear
    assert "loadRecentQuestions();" in ask[ask.index("function askHistoryRepaint()") :][:200]


def test_a_board_in_the_results_is_drawn_and_opened_as_a_board():
    """"a whitebaord showed as a note in the notes ask subtab matching records
    column" (INBOX 744 (a): "clicking it takes me to the notes page").
    Measured: asking "zebra crossing" listed the board as "zebra crossing
    board, Board" (title "Open it"), Sources read "1 board", and pressing it
    opened #/library/board/3. Backend: test_library_boards.py."""
    cards = frontend_text("note-cards.js")
    assert '"ph:tree-structure Mind map" : "ph:pencil-circle Board"' in cards
    ask = frontend_text("capture-ask.js")
    assert "entry.board_kind ? () => openWhiteboardBoard(entry.id) : () => flashEntry(entry.id)" in ask
    agent = frontend_text("chat-agent.js")
    assert 'kind: board === "map" ? "map" : board ? "board" : "note",' in agent
    assert '{ key: "board", icon: "ph:pencil-circle", one: "board", many: "boards" },' in agent


def test_the_ask_wait_is_on_screen():
    """INBOX 727: "there's no searching animation or indicator for when I
    enter a search in the ask tab and nothing has shown yet". Measured with
    the stream held 2.5 s: before, the phase line sat in the hidden results
    grid (0x0) for the whole wait; after, the line is 26 px tall at once and
    the records column reads "Searching your notes…" (532x43)."""
    ask = frontend_text("capture-ask.js")
    body = ask[ask.index("async function askQuestion(") :][:9000]
    assert 'setLabel(searching, "ph:spin Searching your notes…");' in body
    assert body.index('$("chat-results").classList.remove("hidden");') < body.index("await streamChat(")


def test_a_percentage_on_every_card_or_none():
    """INBOX 728: "how come only some of the ask tab matching records notes
    green arrows have % number similarity and others dont show a number??"
    Measured with three rows: all scored, 68%, 90%, 50% similar; one row
    without a score, the scored chip reads "Similar" (the number in its
    title) and no card shows a number."""
    ask = frontend_text("capture-ask.js")
    assert "function everyRowScored(rows, info, connected)" in ask
    assert 'scored ? text : text.replace(/\\d+% similar/, "Similar")' in ask
    for name in ("capture-ask.js", "chat-agent.js", "ask-history.js"):
        assert "matchReasonBadge(matchInfo[entry.id], scored)" in frontend_text(name), name


def test_a_reply_says_who_wrote_it_and_a_composed_one_arrives():
    """"Composer chat messages ... should say if the composer or a specific
    ai model generated it"; "Composer responses just appear, I think there
    should be an animation". Measured: the head reads "Atlas, from your
    notes" (it read "Atlas"); a two-block composed answer's blocks rise with
    delays 0 and 60 ms; reduced motion skips it."""
    attach = frontend_text("chat-attach.js")
    assert 'const by = meta?.composed ? "from your notes" : stats?.model || meta?.answered_by || (meta ? "composer" : "");' in attach
    assert "who.textContent = `${bubble.dataset.persona}, ${by}`;" in attach
    assert "if (meta?.composed && !reducedMotionWanted()) {" in attach
    assert '"ph:notebook Your notes, no AI"' not in attach


def test_web_pieces_of_the_owners_list():
    """Web sources first ("1 web page · 2 notes", kinds web, note, note);
    "a retry button for failed web searches" (Try again, 32 px, beside the
    error); "I saved a website as a bookmark but the icon didnt change"
    (pressed: `active`, aria-pressed true, title "In your bookmarks");
    "the notification said it takes a while to pull the first image for
    searxng but ive already used multiple times" (said only when absent)."""
    agent = frontend_text("chat-agent.js")
    assert 'return [...sources.filter((s) => s.kind === "web"), ...sources.filter((s) => s.kind !== "web")];' in agent
    groups = agent[agent.index("const CHAT_SOURCE_GROUPS = [") :][:200]
    assert groups.index('key: "web"') < groups.index('key: "note"')
    chat = frontend_text("chat.js")
    assert 'smallButton("ph:arrow-clockwise Try again", "Search again", () => runWebSearch())' in chat
    assert 'webEngineInfo?.state === "absent" ? "Setting SearXNG up…' in chat
    assert "the first run pulls the image" not in chat + frontend_text("settings-controls.js")
    clip = frontend_text("web-clip.js")
    assert "function readerBookmark()" in clip and 'button.classList.toggle("active", kept);' in clip


def test_a_result_card_keeps_its_reason_and_ends_with_its_date():
    """INBOX 745 (a): "note dates arent in the corner like i asked"; INBOX 728
    again: in Ask's records the reason chip was folded to its icon (24 px,
    words display:none) on cards whose facts line ran out of room, so some
    cards showed a number and some only the mark. Measured after: the chip
    keeps its words (144 px, "73% similar · “garden”"; the links count folds
    to its icon first) and the date ends the line at the right edge (1292 to
    1348 of a 888 to 1364 line; 107 px from the card's right before)."""
    cards = frontend_text("note-cards.js")
    assert 'text.parentElement.matches(".review, .result-reason-chip")' in cards
    ask = frontend_text("capture-ask.js")
    assert 'meta.insertBefore(badge, meta.querySelector(":scope > .entry-date"));' in ask
    assert 'if (date) date.style.marginInlineStart = "auto";' in ask
    for name in ("capture-ask.js", "chat-agent.js", "ask-history.js"):
        assert "placeResultBadge(row, badge);" in frontend_text(name), name


def test_a_notes_questions_are_on_its_card_and_grouped():
    """INBOX 745 (c). Measured: the lease note's card reads "1 open question"
    (115 px), the shed note's "2 open questions"; pressing one shows only its
    questions with "Show every note's"; the list has a 40 px heading per note
    (a plain labelled button, no icon-only box). Backend: test_questions_own."""
    lst = frontend_text("notes-list.js")
    assert "path: (ids) => `/questions/counts?ids=${ids}`," in lst
    assert 'ensureModule("questionsView").then(() => questionsForNote(entry.id));' in lst
    view = frontend_text("questions-view.js")
    assert 'head.className = "question-group";' in view and "function questionsForNote(entryId)" in view
    assert "if (seq !== questionsView.seq) return;" in view
    assert "item.display || item.text" in view


def test_show_them_opens_your_notes():
    """"I pressed show them, but it just navigated me to the Ask subtab on the
    notes tab as that was what I was just on". Measured: Ask open last, then
    the bell's Show them: Your notes, the filter is:untagged, 16 rows."""
    lst = frontend_text("notes-list.js")
    body = lst[lst.index("function showNotesFilter(query) {") :][:400]
    assert 'showNotesSection("browse");' in body


def test_the_glide_follows_a_row_that_moves():
    """"There's overlap on these settings tabs in the sidebar" (the chosen
    row's fill drawn under it, beside the row's hover). Reproduced at 1024
    and 1280: 18 px inserted above the chosen row left the fill 20 px below
    it; with `childList` observed it lands on the row (0 px)."""
    shell = frontend_text("shell-reminders.js")
    body = shell[shell.index("function glideStrip(strip) {") :][:3500]
    assert "childList: true," in body


def test_every_help_button_has_the_icon_button_corner():
    """"Some tooltip buttons are circles and some are rounded squares". Census
    at 1440 before: five '?' at 50% (the Notes rail's, four in Settings)
    beside 35 icon buttons at `--radius-md`. DESIGN.md has the row."""
    css = (ROOT / "frontend" / "css" / "03-dashboard-widgets.css").read_text(encoding="utf-8")
    for selector in (".graph-help-toggle {", "#wb-help-btn {"):
        rule = css[css.index(selector) :]
        rule = rule[: rule.index("\n}")]
        assert "border-radius: var(--radius-md);" in rule and "border-radius: 50%" not in rule, selector
    assert "Some tooltip buttons are circles" in (ROOT / "docs" / "DESIGN.md").read_text(encoding="utf-8")


def test_packages_progress_stays_with_the_bundle_pressed_and_a_blocked_file_offers_install():
    """"I pressed install on the documents package and the progress bars
    appeared for the vision package" (Read scanned PDFs is in both bundles):
    measured with a running bulk of Documents' three, Vision drew 0 bars and
    0 steps after (1 and 1 before). "it should have given me ... an install
    button directly": the viewer's note on a PDF with no reader carries
    Install, which closes the viewer and opens Settings, Packages."""
    pkgs = frontend_text("settings-packages.js")
    assert "packagesUi.bulkBundle = bundleId;" in pkgs
    assert "shownIn(item.id) === bundle.id" in pkgs
    view = frontend_text("lightbox-view.js")
    assert 'revealFeature("extra-row", payload.extra);' in view


def test_quick_access_has_its_own_menu_on_its_title_line():
    """"a subtle like meatball icon in the top right on the same line as the
    quick access title". Measured: the ⋯ centred on the title's line (320 and
    320 px at 1440; 317 and 317 at 390), at the row's right (1424 of 1428),
    no fill at rest, holding Edit quick access and Reset quick access."""
    dash = frontend_text("dashboard.js")
    assert 'kebabMenu(dashCustomiseItems().filter((item) => item.group === "quick"), "Quick access options")' in dash


def test_a_finished_task_opens_its_log():
    """"no way to view logs of bg processes". Measured with a routed history
    row ("Installing Search by meaning (sentence-transformers)"): the row has
    Logs (32 px line), pressing it opens Settings, Logs with the filter
    "sentence-transformers"."""
    assert "row.append(name, taskLogButton(item));" in frontend_text("chat-tasks.js")
    settings = frontend_text("settings.js")
    assert "function taskLogButton(item)" in settings
    assert "async function openTaskLog(item)" in frontend_text("settings-controls.js")


def test_a_turned_down_tag_can_be_undone_and_listed():
    """"if I click the not about [this tag], don't show this again, is there a
    way to undo it or see the list". Measured: x on #ollama gives "Won't
    suggest #ollama for this note again." with Undo; Undo brings it back;
    the edit form reads "Not suggested: #university" with a restore chip.
    Backend: test_suggest_tags_no_model.py."""
    tags = frontend_text("tag-suggest.js")
    assert "for this note again.`, post({ restore: [tag] }), post(body)" in tags
    assert 'down.append("Not suggested:");' in frontend_text("note-edit-panels.js")
