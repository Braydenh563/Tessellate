"""Ask is Chat in single-turn mode (CHAT_PLAN.md Phase 3, decisions 8 and 11).

Three claims, none of which the DOM-blind suite could make before:

1. A follow-up asked from the Ask tab carries the answer above it. The chips
   under an answer call `askQuestion`, which sends `conversation` as history,
   so this is a claim about `/chat/stream`: the previous turn has to reach the
   model as its own messages, not be summarised into the system prompt or
   dropped. Asserted against the fake transport, which records every message
   list it was asked to answer.
2. The Ask tab renders the answer object rather than a second, thinner shape:
   `answerObject` is the one builder and its foot is drawn from the Chat tab's
   own three components.
3. When no model is connected every AI control stays visible and disabled with
   the same sentence on it, and Ask itself is never among them (decision 11:
   "Ask falls back to search results with passages; nothing is hidden").
"""

from __future__ import annotations

import json
import re
from pathlib import Path

from tessellate.entry import manager
from tests._app_js import app_js_text

FRONTEND = Path(__file__).resolve().parents[1] / "frontend"
#: app.js plus palette.js: the popup agent (Ctrl+K) was split out of app.js
#: on 2026-09-24, and these tests read it wherever it lives.
APP = app_js_text() + "\n" + (FRONTEND / "js" / "ask-compose.js").read_text(encoding="utf-8") + "\n" + (FRONTEND / "js" / "palette.js").read_text(
    encoding="utf-8"
)
INDEX = (FRONTEND / "index.html").read_text(encoding="utf-8")
MARKUP = re.sub(r"<!--.*?-->", "", INDEX, flags=re.S)


def _ask(client, question, **body):
    with client.stream(
        "POST",
        "/chat/stream",
        #: Exactly what the Ask box sends: notes only, and no tools, which is
        #: what puts the turn on the plain streaming path rather than through
        #: the agent's tool loop.
        json={"question": question, "notes_only": True, "use_tools": False, **body},
    ) as response:
        for line in response.iter_lines():
            if line.strip():
                json.loads(line)


def test_a_followup_carries_the_answer_above_it(ai_client, fake_ollama, session):
    """The gate's own sentence: the second answer is written with the first in
    front of the model. Two turns over the same endpoint the chips use."""
    manager.create_entry(session, "The beans need netting next week")
    session.commit()

    fake_ollama.librarian_reply = "You wrote that the beans need netting next week."
    _ask(ai_client, "what did I write about beans")
    first = fake_ollama.librarian_reply

    _ask(
        ai_client,
        "when should I do that",
        history=[{"question": "what did I write about beans", "answer": first}],
    )
    sent = fake_ollama.chat_calls[-1]
    assert any(m["content"] == "what did I write about beans" for m in sent), sent
    assert any(m["content"] == first for m in sent), sent
    #: As their own turns, in order, not folded into the instructions: a
    #: history glued into the system prompt is a history the model weighs as
    #: rules rather than as what was just said.
    roles = [m["role"] for m in sent]
    assert roles[0] == "system"
    assert "user" in roles[1:] and "assistant" in roles[1:]


def test_the_followup_chips_reask_through_the_same_path_that_carries_history():
    """A chip that called its own fetch would be a second path to keep in step,
    and the context would live on exactly one of them."""
    start = APP.index("async function renderAskFollowups(")
    body = APP[start : APP.index("\n}\n", start)]
    assert "/chat/followups" in body
    assert "askQuestion(pick)" in body


def test_ask_builds_the_answer_object_and_draws_the_chat_tabs_components():
    """One shape (decision 3) and one set of components (decision 8)."""
    start = APP.index("function answerObject(")
    builder = APP[start : APP.index("\n}\n", start)]
    for field in ("sentences", "sources", "related", "next", "stats", "verification"):
        assert f"{field}:" in builder, field
    #: The sources list is the Chat tab's, so the two surfaces cannot number
    #: the same answer's sources differently.
    assert "chatSourcesFrom(" in builder

    start = APP.index("function renderAskAnswerFoot(")
    foot = APP[start : APP.index("\n}\n", start)]
    assert "renderRelatedElsewhere(" in foot
    assert "chatSourcesPanel(" in foot

    for element in ("ask-answer-foot", "ask-answer-related", "ask-answer-sources", "ask-followups"):
        assert f'id="{element}"' in MARKUP, element


def test_a_browsed_turn_is_drawn_as_the_answer_object_too():
    """INBOX 241: reopening a turn from the history panel redrew the prose and
    the results and stopped, so the citations and the source cards were lost
    the moment an answer was browsed rather than asked.

    The same two calls the live path ends on: `renderAnswerGrounding`, which
    puts the numbered markers into the answer as well as drawing the chip row
    that is their key, and the foot built from `answerObject`.
    """
    start = APP.index("async function viewAskHistoryTurn(")
    body = APP[start : APP.index("\nasync function toggleAskHistoryPin(", start)]
    for call in ("renderAnswerGrounding(", "renderAskAnswerFoot(", "answerObject("):
        assert call in body, call
    assert body.index("renderAnswerGrounding(") < body.index("renderAskAnswerFoot(")
    #: And exactly once, from inside `renderAnswerGrounding`. A second pass
    #: here would mark every grounded sentence twice: the live path's own
    #: second call is a repair for a re-render this path does not do.
    assert "addInlineCitations(" not in body
    #: Drawn from what the route sends, not recomputed in the browser: the
    #: grounding is a fact about the answer as it was written.
    assert "turn.grounding" in body


def test_related_items_are_not_written_into_the_box_that_clears_them():
    """The bug the restructuring found: `renderAnswerGrounding` opens with
    `replaceChildren()`, and the grounding event always arrives after the
    related one, so "Elsewhere in your notebook" was drawn and deleted."""
    start = APP.index("async function askQuestion(")
    body = APP[start : APP.index("\nfunction retryAnswer(", start)]
    assert 'renderRelatedElsewhere($("ai-answer-grounding")' not in body
    assert "relatedItems = event.items" in body


def test_ask_is_never_disabled_when_the_model_is_off():
    """Decision 11. Ask answers from search alone, so greying it out would hide
    the one thing that still works.

    The gate reads `data-needs-model` off the markup now (INBOX 203), so this
    is a claim about the markup: Ask's own three controls carry no such
    attribute, and nothing marks them from script either.
    """
    for never in ("ask-btn", "question", "stop-btn"):
        block = re.search(r'\sid="%s"[^>]*>' % never, MARKUP)
        assert block, never
        assert "data-needs-model" not in block.group(0), never
    # Other controls may be marked from script (the digest button, the skills
    # trigger); Ask's three never are, so the check names them.
    for line in APP.splitlines():
        if "dataset.needsModel =" in line or 'setAttribute("data-needs-model"' in line:
            assert not re.search(r"ask-btn|\bquestion\b|stop-btn|askBtn|stopBtn", line), line


# --- the popup agent (CHAT_PLAN.md decision 9) --------------------------------


def _starter_table() -> str:
    start = APP.index("const AGENT_STARTERS = [")
    return APP[start : APP.index("\n];", start)]


def test_the_popup_agent_offers_twelve_starters_grouped_by_verb():
    """Four was the count, and the report was that the useful things were not
    among them. Twelve, in five groups, in the plan's own order."""
    table = _starter_table()
    assert table.count("{ group:") == 12, table.count("{ group:")
    groups = re.findall(r'group: "(\w+)"', table)
    assert list(dict.fromkeys(groups)) == ["Capture", "Find", "Summarise", "Remind", "Do"]


def test_every_starter_family_has_a_glyph_that_the_app_actually_ships():
    """INBOX 205: the set reads as five families plus two, one glyph each.

    Two ways this breaks silently. A family added to the table with no row in
    `AGENT_STARTER_ICONS` renders `ph-undefined`, a class that matches nothing;
    and a name that is not in the vendored Phosphor subset draws nothing at all
    (see `tests/test_icon_names.py` for why that is invisible). Neither throws,
    neither logs, and both look like a chip that lost its icon.
    """
    start = APP.index("const AGENT_STARTER_ICONS = {")
    table = APP[start : APP.index("\n};", start)]
    icons = dict(re.findall(r'(\w+): "([a-z0-9-]+)"', table))
    groups = set(re.findall(r'group: "(\w+)"', _starter_table()))
    assert groups <= set(icons), f"starter families with no glyph: {groups - set(icons)}"
    #: The two groups that are not families of their own (the tab's own row and
    #: the recents) name their glyph in the renderer instead.
    renderer = APP[APP.index("function renderAgentStarters(") :]
    renderer = renderer[: renderer.index("\n}\n")]
    wanted = set(icons.values()) | set(re.findall(r', "([a-z-]+)"\]\)', renderer))
    available = set(
        re.findall(
            r"\.ph-([a-z0-9-]+):before",
            (FRONTEND / "vendor" / "phosphor" / "style.css").read_text(encoding="utf-8"),
        )
    )
    assert len(wanted) == 7, sorted(wanted)
    assert wanted <= available, f"not in the vendored subset: {sorted(wanted - available)}"


def test_a_starter_is_a_stem_or_a_whole_instruction_and_never_both():
    """The trailing space is the contract the click handler reads: a stem waits
    with the caret after it, anything else runs on the press. A starter ending
    in a space *and* a full stop would run half a sentence."""
    for text in re.findall(r'text: "([^"]+)"', _starter_table()):
        if text.endswith(" "):
            assert not text.rstrip().endswith((".", "?")), text
        else:
            assert text.rstrip().endswith((".", "?")), text


def test_a_complete_starter_runs_and_a_stem_does_not():
    """It used to test for a question mark, so the seven starters that are
    instructions ("Tag my untagged notes.") sat in the box doing nothing."""
    start = APP.index('$("command-palette-intro")?.addEventListener')
    handler = APP[start : APP.index("\n});", start)]
    assert "rememberAgentStarter(starter)" in handler
    assert "endsWith(\"?\")" not in handler
    assert "cmdPaletteAsk(starter.trim())" in handler


def test_the_palette_can_keep_its_conversation_and_says_where_it_went():
    """INBOX 215, the owner: "I want to be able to save conversations with the
    popup agent as a permanent chat session."

    The palette's turns live in `cmdPaletteTurns` and nowhere else, so this is
    the only path off that array. Three claims: the first turn creates the
    conversation and the rest are appended (the create route takes one turn and
    makes the title from its question), the foot's menu is the app's own menu
    recipe rather than a fifth hand-built one, and the row is dead until there
    is something to save.
    """
    start = APP.index("async function cmdPaletteSaveAsChat(")
    body = APP[start : APP.index("\n}\n", start)]
    assert '"/conversations"' in body and 'method: "POST"' in body
    assert "/turns`" in body, "the turns after the first are appended"
    assert "toastAction(" in body, (
        "the way into the saved thread is a toast action: the status line is "
        "one ellipsised line and a long title would push a link off the end"
    )

    start = APP.index("function renderCmdPaletteMenu(")
    menu = APP[start : APP.index("\n}\n", start)]
    assert "kebabMenu(" in menu, (
        "the palette's foot menu is `kebabMenu` (DESIGN.md's recipe index): it "
        "clamps, escapes a clipping ancestor and closes on an outside click"
    )
    assert "Save as chat" in menu and "Start over" in menu
    assert "disabled: !saved" in menu, (
        "with nothing asked yet there is nothing to save and nothing to clear, "
        "and a row that does nothing when pressed is what this app keeps being "
        "told about"
    )
    #: The menu is rebuilt when the thing it depends on changes, or it offers a
    #: dead row for the whole of the first conversation.
    assert APP.count("renderCmdPaletteMenu()") >= 3


def test_the_open_note_toggle_scopes_the_run_to_what_is_open():
    start = APP.index("function agentScopeForRun(")
    body = APP[start : APP.index("\n}\n", start)]
    #: A document and a note reach the server through different fields; sent as
    #: one, a document arrives as its title and nothing else.
    assert "documentIds" in body and "noteIds" in body
    assert 'id="command-palette-use-note"' in MARKUP

    #: Resolved when the message is sent, not when the box was ticked: the
    #: palette stays open while you move around the app.
    start = APP.index("async function cmdPaletteAsk(")
    ask = APP[start : APP.index("\n}\n", start)]
    assert "agentScopeForRun(text)" in ask and "...agentScope," in ask  # resolved at send (attach-1026 named it)


def test_the_toggle_never_offers_to_use_nothing():
    start = APP.index("function syncAgentOpenNoteToggle(")
    body = APP[start : APP.index("\n}\n", start)]
    #: Hidden, not disabled, when nothing is open (AGENT_SKILLS_REFORM
    #: "Deepened 2026-10-10" row 1: 0 disabled controls with no model).
    assert 'label.classList.toggle("hidden", !subject)' in body
    assert "box.disabled" not in body
    #: The words are written onto a span, not onto the label: a label's own
    #: `textContent` includes the checkbox inside it.
    assert "command-palette-use-note-text" in body


# --- no model connected (CHAT_PLAN.md decision 11) ----------------------------


def test_every_ai_only_control_names_settings_not_one_provider():
    """It said "start Ollama to use this", which is the wrong instruction for
    the two other providers this app supports."""
    start = APP.index("function syncModelGatedControls(")
    body = APP[start : APP.index("\n}\n", start)]
    assert "AI_OFFLINE_HINT" in body
    assert "start Ollama to use this" not in APP
    assert 'const AI_OFFLINE_HINT = "Connect a model in Settings";' in APP


def test_the_offline_note_is_one_click_from_connecting_a_model():
    start = APP.index("function renderAiOfflineNotice(")
    body = APP[start : APP.index("\n}\n", start)]
    assert 'openSettingsModal("models")' in body
    for element in ("ask-offline", "command-palette-offline"):
        assert f'id="{element}"' in MARKUP, element


def test_the_agents_field_stays_open_with_no_model():
    """AGENT_SKILLS_REFORM "Deepened 2026-10-10" row 1 replaces decision 11's
    "visible, disabled" for the agent: with no model it runs acts and
    readings (`ai/starter_acts.py`), so neither the field nor a starter is
    disabled, and `cmdPaletteBusy` closes the field only while a run is in
    hand."""
    start = APP.index("function syncAgentPaletteAvailability(")
    body = APP[start : APP.index("\n}\n", start)]
    assert "disabled" not in body

    start = APP.index("function cmdPaletteBusy(")
    busy = APP[start : APP.index("\n}\n", start)]
    assert "cmdPaletteInput.disabled = busy;" in busy


# --- links the AI writes (CHAT_PLAN.md decision 12, INBOX 172) ----------------


def test_a_link_on_its_own_line_is_a_card_and_one_in_a_sentence_is_not():
    start = APP.index("function renderMarkdown(")
    body = APP[start : APP.index("\n// --- tabs", start)]
    assert "LONE_LINK" in body
    #: Only when the paragraph is that one line: a link on the third line of a
    #: paragraph is inside a sentence whatever it looks like on its own.
    assert "para.length === 1 ? LONE_LINK.exec(para[0]) : null" in body


def test_the_card_never_asks_the_web_for_anything():
    """The decision, as a test: an app that fetches nothing must not start by
    fetching a favicon."""
    start = APP.index("function linkCard(")
    body = APP[start : APP.index("\n}\n", start)]
    for fetched in ("favicon", "google.com/s2", "<img", 'createElement("img")'):
        assert fetched not in body, fetched
    assert 'rel = "noopener noreferrer"' in body


def test_the_cards_two_lines_do_not_say_the_same_thing():
    """`readableUrl` (the inline form) opens with the host, and the card writes
    the host on its second line: using it as the title printed "arxiv.org / … /
    2401.12345" over "arxiv.org"."""
    start = APP.index("function linkCard(")
    body = APP[start : APP.index("\n}\n", start)]
    assert "linkCardPath(url)" in body
    assert "readableUrl(url)" not in body


def test_the_ask_foot_does_not_redraw_the_records_column():
    """INBOX 274, the owner with a screenshot: "having the notes appear as
    sources below the ai response in the notes tab ask subtab is uncnecessary
    when they are shown already on the right next to the ai response".
    Measured on that screen: five numbered source cards under the answer and
    the same five notes, same ids in the same order, as rows in Matching
    records beside it.

    The decision taken: the column is the one place for the notes, and under
    the answer there is one line saying how many and where. A note the column
    is not showing, and every source that is not a note, keeps a card, because
    the column is notes and an answer can draw on a file or a page.

    The Chat tab keeps its panel whole and that is not an inconsistency: Chat
    has no column beside it, so the cards are the only place its sources can
    be. This asserts the arrangement, not the components.
    """
    start = APP.index("function renderAskAnswerFoot(")
    foot = APP[start : APP.index("\n}\n", start)]
    #: The split: what the column already holds, and what it does not.
    assert "askNotesOnTheRight(" in foot, (
        "the foot has to know which notes the records column is showing, or "
        "it cannot tell a duplicate from a source that has nowhere else to be"
    )
    #: **And no control for the notes it is already showing** (the owner,
    #: 2026-09-21: "remove the show x notes used button in the ask subtab as
    #: well, it isnt needed"). The button counted the notes the column holds
    #: and scrolled to the first one the answer cites, which is a second door
    #: to a list already on screen beside the answer, carrying the answer's own
    #: numbers on its rows. Asserted as an absence because a helpful edit would
    #: put it back: the split above is the feature, not the button.
    assert "askSourcesLine" not in APP, (
        "the notes the records column already shows get no button of their own"
    )
    assert "elsewhere" in foot, (
        "a source the column does not hold still needs a card; dropping all of "
        "them would lose the files and web pages an answer drew on"
    )


def test_a_citation_mark_still_has_something_to_land_on():
    """The half of the change above that is easy to forget. `showCitedPassage`
    found its target by `.chat-source-card[data-note-id]`, and on the Ask tab
    those cards are gone: without this the marks in the answer became
    decoration, which is a feature quietly lost rather than a duplicate
    removed. The records row is where a cited note is drawn on that tab."""
    start = APP.index("function showCitedPassage(")
    body = APP[start : APP.index("\n}\n", start)]
    assert "chat-source-card[data-note-id=" in body, "the Chat tab's cards"
    assert "#raw-results li[data-id=" in body, (
        "and the Ask tab's records rows, which are where a cited note is "
        "drawn there"
    )
    clear = APP[APP.index("function clearCitedPassage(") :]
    clear = clear[: clear.index("\n}\n")]
    assert ".is-cited" in clear, (
        "clearing has to reach both, or a mark left on a records row stays "
        "lit under the next answer"
    )


def test_the_sources_panel_can_be_given_a_subset_without_renumbering_it():
    """The numbers on the cards are the numbers in the answer. The Ask tab now
    hands the panel only the sources its column is not showing, and a panel
    that numbered its own rows would call them 1 and 2 while the answer above
    printed [4] and [5]."""
    start = APP.index("function chatSourcesPanel(")
    body = APP[start : APP.index("\nfunction ", start + 10)]
    assert "numberFrom" in body, (
        "chatSourcesPanel must accept the full list the citations were "
        "numbered against"
    )
    assert "numbering.indexOf(source)" in body, (
        "and number each card by its place in that list, not by its place in "
        "the subset it was handed"
    )
