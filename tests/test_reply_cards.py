"""Replies the app helps draw (INBOX 1300 C06, the owner: "if I ask for stats
I want a panel with cards and icons and visualised statistics and a link to
open the statistics panel ... an interactive calculator popup that is
accessible and also link it to the /calc command as well as other unit
conversions"). The stream says which panel an answer carries (`panel`
events); one lazy renderer draws it on every surface, whoever wrote the
words (CHAT_PLAN decision 75: the panel assists, the model still leads).
"""

from __future__ import annotations

import json
import re
from pathlib import Path

from tessellate.ai import tools
from tests._app_js import app_js_text

ROOT = Path(__file__).resolve().parents[1]
JS = ROOT / "frontend" / "js"


def _stream(client, question):
    events = []
    with client.stream("POST", "/chat/stream", json={"question": question}) as response:
        for line in response.iter_lines():
            if line.strip():
                events.append(json.loads(line))
    return events


def _panels(events):
    return [e for e in events if e["type"] == "panel"]


def _seed(session):
    for text, tags in (("Boiler pressure is low", ["home"]), ("Gym plan for the week", ["health"])):
        tools.execute_tool(session, "create_note", {"content": text, "tags": tags})
    session.commit()


def test_a_stats_question_carries_the_statistics_panel(ai_client, fake_ollama, session):
    fake_ollama.running = False
    _seed(session)
    assert _panels(_stream(ai_client, "notebook stats")) == [{"type": "panel", "panel": "statistics"}]
    assert _panels(_stream(ai_client, "/stats")) == [{"type": "panel", "panel": "statistics"}]


def test_the_panel_comes_whoever_writes_the_words(ai_client, fake_ollama, session):
    fake_ollama.running = True
    _seed(session)
    assert _panels(_stream(ai_client, "notebook stats")) == [{"type": "panel", "panel": "statistics"}]


def test_a_sum_or_a_conversion_carries_the_calculator(ai_client, fake_ollama, session):
    fake_ollama.running = False
    assert _panels(_stream(ai_client, "/calc 12*(3+4)")) == [{"type": "panel", "panel": "calculator", "input": "12*(3+4)"}]
    assert _panels(_stream(ai_client, "/calc")) == [{"type": "panel", "panel": "calculator", "input": ""}]
    assert _panels(_stream(ai_client, "5 km to miles")) == [{"type": "panel", "panel": "calculator", "input": "5 km to miles"}]
    #: An answer about the notes carries no panel.
    assert _panels(_stream(ai_client, "hello")) == []


def test_the_calculator_works_out_through_the_chat_tools_reader(ai_client):
    got = ai_client.get("/utilities/work", params={"q": "5 km to miles"}).json()
    assert got["answer"] == "5 kilometres is 3.11 miles." and got["read_as"] == "5 kilometres in miles"
    assert ai_client.get("/utilities/work", params={"q": "12*(3+4)"}).json()["answer"] == "12*(3+4) is 84."
    assert "error" in ai_client.get("/utilities/work", params={"q": "banana"}).json()
    units = ai_client.get("/utilities/units").json()
    assert "kilometres" in units["length"] and "USD" in units["currency"]


def test_every_answer_surface_draws_the_panel_with_one_renderer():
    code = app_js_text()
    assert 'event.type === "panel" && onPanel' in code
    assert re.search(r'replyKit: \["/css/reply-kit-lazy\.css", "/js/reply-kit\.js"\]', code)
    kit = (JS / "reply-kit.js").read_text(encoding="utf-8")
    assert "function renderReplyPanel(holder, event)" in kit
    assert "onPanel:" in (JS / "chat-attach.js").read_text(encoding="utf-8")
    #: Ask and the popup agent draw theirs once the answer is final, through one drawer.
    ask = (JS / "capture-ask.js").read_text(encoding="utf-8")
    assert "function drawAnswerPanels(holder, panels, before = null)" in ask and "replyDrawAll(holder, panels, before)" in ask
    assert "renderReplyPanel(holder, event)" in kit and "drawAnswerPanels(timeline.holder, [event])" in (JS / "chat-attach.js").read_text(encoding="utf-8")
    for name in ("capture-ask.js", "palette.js"):
        source = (JS / name).read_text(encoding="utf-8")
        assert "onPanel:" in source and "drawAnswerPanels(answerBox" in source, name
    #: One recipe: a reply panel is drawn by reply-kit.js and nowhere else.
    others = [p.name for p in JS.glob("*.js") if p.name != "reply-kit.js" and '"reply-panel' in p.read_text(encoding="utf-8")]
    assert not others, f"a reply panel built outside reply-kit.js: {others}"


def test_web_results_are_cards_and_a_read_page_is_a_fold():
    """INBOX 1300 C06: "a websearch shows the link as a clickable card not
    just a url, and also if it does a url fetch, it has a dropdown that opens
    a semi large panel with the extracted and formatted contents inside as
    well as a link and data"."""
    kit = (JS / "ask-compose.js").read_text(encoding="utf-8")
    assert 'item.className = "web-result-card";' in kit and "web-result-title card-open" in kit
    assert "function renderWebSources(holder, sources, { read = false } = {})" in kit
    #: The reader is the page's blocks as Markdown, with its facts line.
    assert "renderMarkdown(body, markdown)" in kit and "web-reader-facts" in kit
    for name in ("chat-attach.js", "palette.js"):
        source = (JS / name).read_text(encoding="utf-8")
        assert 'event.tool === "read_url"' in source and "read: true }]" in source, name
    css = (ROOT / "frontend" / "css" / "ask-compose-lazy.css").read_text(encoding="utf-8")
    assert "max-block-size: min(32rem, 60dvh);" in css


def test_the_calculator_is_one_sheet_reached_three_ways():
    """INBOX 1300 C06: "an interactive calculator popup that is accessible
    and also link it to the /calc command as well as other unit
    conversions"."""
    kit = (JS / "reply-kit.js").read_text(encoding="utf-8")
    assert "calculator: (event) => replyCalcPanel(event)" in kit
    assert 'function openCalculator(input = "", mode = "work")' in kit and 'name: "calculator"' in kit and "openSheet({" in kit
    #: Accessible: a live result, a keypad that is one Tab stop walked by the
    #: arrows, keys named for what they do, a mode switch that says which is on.
    assert 'out.setAttribute("aria-live", "polite")' in kit
    assert "key.tabIndex = i === 0 ? 0 : -1;" in kit and "ArrowDown: 4" in kit
    assert '"*": "Times"' in kit and 'modes.className = "tabs-line popup-kinds calc-modes";' in kit
    #: The same reader as /calc, and the units from the app's own tables.
    assert "/utilities/work?q=" in kit and 'apiJson("/utilities/units")' in kit
    #: "/calc" alone opens it; the palette has a row with its line of help.
    assert "if (!event.input) requestAnimationFrame(() => openCalculator());" in kit
    panes = (JS / "settings-panes.js").read_text(encoding="utf-8")
    #: The row now comes from the `POPUP_TOOLS` registry (K27), which the
    #: palette, Features, the "/" menus and the Guide all read.
    entry = panes[panes.index('id: "calculator", name: "Calculator"'):][:600]
    assert "about:" in entry and 'ensureModule("replyKit").then(() => openCalculator())' in entry


def test_a_note_a_reply_gives_is_previewed_on_every_surface():
    """INBOX 1300 C07: "if it is going to give me a note, can it at least
    preview it for me as well??"."""
    ask = (JS / "capture-ask.js").read_text(encoding="utf-8")
    assert "function finishReply(answers, opts)" in ask and "replyFinish(answers, opts)" in ask
    #: Chat, Ask, the popup agent and the Guide each finish a reply through it.
    calls = {
        "chat-attach.js": "finishReply(answerEls, { composed: meta?.composed",
        #: The meta is the options (its `composed`, and `match_info` for the records, INBOX 1310).
        "capture-ask.js": "finishReply(answerBox, { composed: answerMeta?.composed, match_info: answerMeta?.match_info });",
        "palette.js": "finishReply(answerBox, { composed: meta?.composed, head: agentLabel",
        "help-chat.js": 'finishReply(answerRow.querySelector(".help-chat-prose")',
    }
    for name, call in calls.items():
        assert call in (JS / name).read_text(encoding="utf-8"), name
    kit = (JS / "reply-kit.js").read_text(encoding="utf-8")
    #: The citation peek for every note link, and up to three cards in the
    #: document embed's recipe; a longer list keeps the peek only.
    assert "openCitationPeek(link, { noteId: id" in kit and "const REPLY_NOTE_CARDS = 3;" in kit
    assert 'card.className = "embed-card reply-note-card";' in kit and "openNoteAtPassage(id" in kit
    css = (ROOT / "frontend" / "css" / "reply-kit-lazy.css").read_text(encoding="utf-8")
    assert ".citation-peek-number:empty" in css


def test_a_wall_of_text_in_a_reply_folds_to_its_gist():
    """INBOX 1300 C08: "if it outputs a mass block of text like from the ocr
    of one of my note's images, maybe it could be in a collapsible subtle
    panel or smth or abrieviated/summarised by the composer somehow??"."""
    kit = (JS / "reply-kit.js").read_text(encoding="utf-8")
    assert "for (const answer of list) replyFoldLong(answer);" in kit
    #: The Thinking fold's disclosure, shut, its summary the gist and length.
    assert 'fold.className = "agent-step long-fold";' in kit and 'summary.className = "fold-summary";' in kit
    assert "const REPLY_FOLD_CHARS = 600;" in kit and 'block.matches("p, pre, blockquote")' in kit
    css = (ROOT / "frontend" / "css" / "reply-kit-lazy.css").read_text(encoding="utf-8")
    assert "max-block-size: min(24rem, 50dvh);" in css


def test_a_composed_reply_takes_one_reveal_on_every_surface(ai_client, fake_ollama):
    """INBOX 1300 C28: one reveal for a reply no model wrote, on Chat, Ask,
    the popup agent and the Guide, with a switch under Interface animations
    and a quick fade under Reduce motion."""
    kit = (JS / "reply-kit.js").read_text(encoding="utf-8")
    assert "if (opts.composed) replyReveal(list);" in kit
    body = kit[kit.index("function replyReveal(answers)") :].split("\n}\n", 1)[0]
    assert "still ? [{ opacity: 0 }, {}]" in body and "delay: still ? 0" in body
    assert 'prefs.get("reply-motion", "on") !== "off"' in kit and 'root.dataset.uiMotion !== "off"' in kit
    #: The one reveal: Chat's own per-block animation is gone.
    chat = (JS / "chat-attach.js").read_text(encoding="utf-8")
    assert ".animate([{ opacity: 0, translate" not in chat
    #: The Guide says when no model wrote it, and then does not type it out.
    guide = (JS / "help-chat.js").read_text(encoding="utf-8")
    assert "composed: !!done?.composed," in guide and "result?.composed ? content :" in guide
    fake_ollama.running = False
    done = ai_client.post("/help/ask", json={"question": "how do I pin a note"}).json()
    assert done.get("composed") is True
    #: The switch, under Interface animations, wired where Settings' rows are.
    html = (ROOT / "frontend" / "index.html").read_text(encoding="utf-8")
    assert html.index('id="ui-motion-toggle"') < html.index('id="reply-motion-toggle"')
    rows = (JS / "settings-rows.js").read_text(encoding="utf-8")
    assert '{ key: "reply-motion", id: "reply-motion-toggle", on: "on", off: "off", base: "on" }' in rows


def test_who_wrote_a_reply_is_one_badge_on_every_surface():
    """INBOX 1300 C14: "Should 'composer' and the model should be a badge or
    smnth similar". One `chip item-label` beside the name on Chat, the popup
    agent and the Guide; Ask's `#answered-by` is the same chip."""
    kit = (JS / "reply-kit.js").read_text(encoding="utf-8")
    assert 'chip.className = "chip item-label answer-model reply-by";' in kit
    assert "if (opts.head && list.some((answer) => answer.textContent.trim())) replyByline(opts.head, opts);" in kit
    facts = kit[kit.index("function replyBylineFacts(") :].split("\n}\n", 1)[0]
    assert '"From your notes"' in facts and '"Composer"' in facts and '"From the help"' in facts
    chat = (JS / "chat-attach.js").read_text(encoding="utf-8")
    assert 'const head = bubble.querySelector(".msg-role");' in chat and "who.textContent" not in chat
    palette = (JS / "palette.js").read_text(encoding="utf-8")
    assert "head: agentLabel, model: stats?.model || meta?.answered_by, engine: Boolean(meta)" in palette
    guide = (JS / "help-chat.js").read_text(encoding="utf-8")
    assert 'head: answerRow.querySelector(".msg-role"), help: true' in guide
    html = (ROOT / "frontend" / "index.html").read_text(encoding="utf-8")
    assert 'id="answered-by" class="chip item-label answer-model"' in html


def test_the_no_model_badge_opens_a_help_popover_1344():
    """INBOX 1344: "a hover/click tooltip popup with a disclaimer and
    description for the composer message badge". A badge no model wrote
    (From your notes, Composer, From the help) is a button on the
    `data-help-for` recipe with its own `.help-body`; a model's name stays a
    plain chip. Hover opens it where hover exists; click, Enter and Space
    always do."""
    kit = (JS / "reply-kit.js").read_text(encoding="utf-8")
    assert 'chip.setAttribute("data-help-for", panel.id);' in kit
    assert "wireHelpPopover(chip, panel);" in kit
    assert "function replyByHelpPanel(" in kit and "written without an AI model" in kit
    assert "(hover: hover)" in kit
    assert "switch labelled AI" in kit[kit.index("function replyByHelpPanel(") :].split("\n}\n", 1)[0]
    css = (ROOT / "frontend" / "css" / "reply-kit-lazy.css").read_text(encoding="utf-8")
    assert "button.reply-by" in css


def test_the_slash_menu_clears_the_agent_popup_overlay_1333a():
    """INBOX 1333a: "the / command menu doesnt appear" in the Agent popup.
    Measured in Chromium (1440x900): the menu opened (19 rows, 610x386 at
    480,235) but sat at z-index 60 under the popup's overlay (2000), and
    `elementFromPoint` on it returned `.command-palette-intro`. The menu is
    the one Chat uses (`agentCommands` -> `chatSlashRows`), so the fix is its
    layer, not a second menu."""
    css = (ROOT / "frontend" / "css" / "05-sidebars-themes.css").read_text(encoding="utf-8")
    rule = css[css.index("\n.editor-menu {") :].split("}", 1)[0]
    assert "z-index: 2550;" in rule
    overlay = (ROOT / "frontend" / "css" / "07-whiteboard-misc.css").read_text(encoding="utf-8")
    assert "z-index: 2000;" in overlay


def test_the_badge_panel_waits_inside_the_head_not_between_the_bubbles_blocks():
    #: Measured 2026-10-27: the hidden panel after the head broke
    #: `.msg-role:has(+ .agent-steps)` and the bubble grew 2.4px on hover.
    kit = (JS / "reply-kit.js").read_text(encoding="utf-8")
    body = kit[kit.index("function replyByline(") :].split("\n}\n", 1)[0]
    assert "head.appendChild(panel);" in body
    assert "head.after(panel)" not in body
