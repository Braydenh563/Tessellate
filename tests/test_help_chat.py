"""ROADMAP.md item 40's mini AI chat: app-guidance-only, utility model,
no persisted history. `ai_client`/`fake_ollama` give the happy path;
`client` proves it degrades without crashing when the model is offline."""

from __future__ import annotations

import re
from pathlib import Path

from tessellate.ai import help_chat
from tests._app_js import app_js_text


def test_ask_without_ai_answers_from_the_help_text_never_5xx(client):
    """With no model, the route still answers, and now it answers usefully.

    It used to return a sentence saying the guide was unavailable, while
    holding the exact hand-written paragraph the question was about. The
    badges were empty for the same reason, and they are the thing that turns
    "reminders live on the Reminders tab" into a way of getting there.
    """
    response = client.post("/help/ask", json={"question": "how do I set a reminder?"})
    assert response.status_code == 200
    body = response.json()
    #: INBOX 1414: the reply says it is the app's help through its byline
    #: (`composed`) and its "From the help" tab, not a second time in the text.
    assert body["composed"] is True and "system" in body
    assert help_chat.OFFLINE_LEAD not in body["content"]
    assert "reminder" in body["content"].lower()
    assert {"label": "Reminders", "tab": "reminders"} in body["badges"]


def test_ask_with_only_whitespace_is_a_no_op_not_a_model_call(ai_client, fake_ollama):
    # min_length=1 lets " " through the Pydantic body; help_chat.answer()
    # itself is what actually guards against calling the model on nothing.
    response = ai_client.post("/help/ask", json={"question": " "})
    assert response.status_code == 200
    assert response.json() == {"content": "", "badges": [], "sources": []}


def test_ask_with_working_model(ai_client, fake_ollama):
    fake_ollama.librarian_reply = "Open the Reminders tab and click New reminder."
    response = ai_client.post("/help/ask", json={"question": "how do I set a reminder?"})
    assert response.status_code == 200
    body = response.json()
    assert "New reminder" in body["content"]
    assert {"label": "Reminders", "tab": "reminders"} in body["badges"]


def test_ask_never_writes_history_server_side(ai_client, fake_ollama):
    # Two independent calls with no shared state get no cross-talk, proof
    # this endpoint never reads a database table for context.
    fake_ollama.librarian_reply = "Answer one."
    first = ai_client.post("/help/ask", json={"question": "q1"}).json()
    fake_ollama.librarian_reply = "Answer two."
    second = ai_client.post("/help/ask", json={"question": "q2"}).json()
    assert first["content"] == "Answer one."
    assert second["content"] == "Answer two."


def test_ask_passes_along_client_held_history(ai_client, fake_ollama):
    fake_ollama.librarian_reply = "Following up on that."
    response = ai_client.post(
        "/help/ask",
        json={
            "question": "and what about dark mode?",
            "history": [
                {"role": "user", "content": "how do I change the theme?"},
                {"role": "assistant", "content": "Settings -> Appearance."},
            ],
        },
    )
    assert response.status_code == 200
    assert response.json()["content"] == "Following up on that."


def test_help_chat_answer_function_is_grounded_in_app_guidance_only():
    assert "app guidance only" in help_chat.SYSTEM_PROMPT or "app itself" in help_chat.SYSTEM_PROMPT


def test_ask_grounds_the_model_in_the_matching_reference_notes(ai_client, fake_ollama):
    # The model has no idea what Tessellate is on its own, item 40's whole
    # "never invent a feature" instruction is only followable if the prompt
    # actually hands it real facts. Assert the reference text lands in the
    # messages sent to the model, not just that the reply looks plausible.
    fake_ollama.librarian_reply = "Open the Reminders tab."
    ai_client.post("/help/ask", json={"question": "how do I set a reminder?"})
    sent = fake_ollama.chat_calls[-1]
    reference_messages = [m["content"] for m in sent if "Reference notes" in m["content"]]
    assert reference_messages
    assert "Overdue" in reference_messages[0]  # from the reminders HELP_TOPICS entry


def test_ask_with_no_matching_topic_sends_no_reference_block(ai_client, fake_ollama):
    fake_ollama.librarian_reply = "I'm not sure: try the Help topics above."
    ai_client.post("/help/ask", json={"question": "purple elephants dance quietly"})
    sent = fake_ollama.chat_calls[-1]
    assert not any("Reference notes" in m["content"] for m in sent)


def test_matching_topics_finds_known_features():
    topics = help_chat._matching_topics("Check the Graph tab for your concept map")
    assert any(t["id"] == "graph" for t in topics)


def test_matching_topics_caps_at_max_topics():
    text = "reminder graph timeline dashboard library document template"
    assert len(help_chat._matching_topics(text)) <= help_chat.MAX_TOPICS


def test_matching_topics_no_match_is_empty():
    assert help_chat._matching_topics("the weather is nice today") == []


def test_matching_topics_keyword_match_is_whole_word_not_substring():
    # "ask" is a keyword (the ask-chat topic); "basket" and "task" both
    # contain it as a raw substring but neither is asking about chat.
    assert help_chat._matching_topics("where's the picnic basket for our task?") == []


def test_badges_for_derives_from_matched_topics():
    topics = help_chat._matching_topics("how do I set a reminder?")
    badges = help_chat.badges_for(topics)
    assert {"label": "Reminders", "tab": "reminders"} in badges


def test_every_help_topic_has_a_non_empty_body_and_badge():
    for topic in help_chat.HELP_TOPICS:
        assert topic["body"].strip()
        assert topic["keywords"]
        assert topic["badge"].get("label")
        assert topic["badge"].get("tab") or topic["badge"].get("section")


# Reported live: clicking the "Whiteboard" badge (a `data-goto-tab="whiteboard"`
# button) blanked the whole app, `switchTab()` hides every tab panel and shows
# none when given a name that matches no real tab, since "whiteboard" is a
# Library *sub*-tab, not a top-level one, and the badge system only knows how to
# switch to a top-level tab.
#
# **Read out of app.js rather than copied into a literal here.** The original
# list was hand-copied and named "documents" among the sub-tabs: true when it
# was written, and false since Documents was promoted to a tab of its own. So
# this test spent that time refusing a badge that would have worked perfectly,
# which is the failure mode a duplicated constant always eventually has. The
# whole point of this lint is that Python cannot see `switchTab`; reading its
# actual `TABS` line is as close as it gets.
def _real_top_level_tabs() -> set[str]:
    match = re.search(r"^const TABS = \[(.*?)\];", app_js_text(), re.M)
    assert match, "app.js no longer declares `const TABS = [...]` on one line"
    return set(re.findall(r'"([a-z-]+)"', match.group(1)))


REAL_TOP_LEVEL_TABS = _real_top_level_tabs()


def test_the_tab_list_was_actually_found():
    """A regex that quietly matched nothing would make the lint below vacuous."""
    assert "dashboard" in REAL_TOP_LEVEL_TABS
    assert len(REAL_TOP_LEVEL_TABS) >= 7


def test_every_badge_tab_is_a_real_top_level_tab():
    for topic in help_chat.HELP_TOPICS:
        tab = topic["badge"].get("tab")
        if tab is not None:
            assert tab in REAL_TOP_LEVEL_TABS, (
                f"{topic['id']!r}'s badge points at {tab!r}, which switchTab() "
                "can't resolve: it isn't one of the app's top-level tabs"
            )


# --- INBOX 190: the Guide is reachable from every tab, so it is told which ---


def test_the_tab_pulls_in_its_own_topics_for_a_question_that_names_none(
    ai_client, fake_ollama
):
    """"How does this work?" has no keyword in it and used to match nothing.

    That is the question the Guide gets most now that it opens from every
    tab's header rather than only from the bottom of the Help pane, and with
    no reference notes the system prompt tells the model to say it is not
    sure, which is the one answer that is never useful.
    """
    fake_ollama.librarian_reply = "The graph draws a dot per note."
    ai_client.post("/help/ask", json={"question": "how does this work?", "tab": "graph"})
    sent = fake_ollama.chat_calls[-1]
    reference = [m["content"] for m in sent if "Reference notes" in m["content"]]
    assert reference, "a tab with topics must ground the answer even with no keyword match"
    assert "graph" in reference[0].lower()
    assert any("graph tab open" in m["content"] for m in sent)


def test_what_the_question_names_still_wins_over_the_tab(ai_client, fake_ollama):
    # Asking about reminders from the Graph tab is a question about reminders.
    fake_ollama.librarian_reply = "Reminders tab."
    ai_client.post(
        "/help/ask", json={"question": "how do I set a reminder?", "tab": "graph"}
    )
    reference = [
        m["content"] for m in fake_ollama.chat_calls[-1] if "Reference notes" in m["content"]
    ]
    assert reference
    assert help_chat.topics_for("how do I set a reminder?", "graph")[0]["id"] == "reminders"


def test_an_unknown_tab_adds_nothing_rather_than_failing(ai_client, fake_ollama):
    fake_ollama.librarian_reply = "Not sure."
    response = ai_client.post(
        "/help/ask", json={"question": "how does this work?", "tab": "nonesuch"}
    )
    assert response.status_code == 200
    assert help_chat.topics_for("how does this work?", "nonesuch") == []


def test_the_surfaces_own_help_copy_reaches_the_model_and_is_capped(
    ai_client, fake_ollama
):
    """The client sends the `.help-body` text of whatever is on screen.

    It is the app's own wording, which makes it the best reference note there
    is; it is also user-supplied input on the wire, so the cap is asserted
    here rather than trusted to the browser that sent it.
    """
    fake_ollama.librarian_reply = "That toggle turns web search off."
    ai_client.post(
        "/help/ask",
        json={
            "question": "what is this toggle?",
            "tab": "notes",
            "context": "A quiet marker on a note you have not read since it changed.",
        },
    )
    sent = fake_ollama.chat_calls[-1]
    assert any("quiet marker on a note" in m["content"] for m in sent)

    over = "x" * (help_chat.MAX_CONTEXT_CHARS + 500)
    response = ai_client.post(
        "/help/ask", json={"question": "what is this?", "context": over}
    )
    # The route's own Field(max_length=...) refuses it rather than truncating,
    # which is the shape every other bounded body field in this app has.
    assert response.status_code == 422


def test_no_tab_behaves_exactly_as_before(ai_client, fake_ollama):
    fake_ollama.librarian_reply = "Reminders tab."
    ai_client.post("/help/ask", json={"question": "how do I set a reminder?"})
    sent = fake_ollama.chat_calls[-1]
    assert not [m for m in sent if "tab open" in m["content"]]
    assert help_chat.topics_for("how do I set a reminder?") == help_chat._matching_topics(
        "how do I set a reminder?"
    )


# --- INBOX 204: the guide has a name, and knows what it is -------------------


def test_the_guide_is_named_once_and_the_interface_agrees(ai_client, fake_ollama):
    """CHAT_PLAN decision 15. The owner asked for "a name fitting for the
    application like a persona"; a persona whose name is typed out in nine
    places is a persona that gets renamed in eight of them.

    So the server holds one constant, the frontend holds one constant, and this
    asserts that the word in the model's prompt is the word on the screen.
    """
    from pathlib import Path

    frontend = Path(__file__).resolve().parents[1] / "frontend"
    app_js = app_js_text()
    #: The chat itself moved to help-chat.js (a lazy bundle); read as one.
    settings_js = (frontend / "js" / "settings.js").read_text(encoding="utf-8") + (frontend / "js" / "help-chat.js").read_text(encoding="utf-8")
    index = (frontend / "index.html").read_text(encoding="utf-8")

    assert help_chat.GUIDE_NAME == "Atlas"
    #: Spelt once on each side (INBOX 225): the frontend's `AI_NAME` is the
    #: word, and `GUIDE_NAME` reads it, so the guide and the librarian can
    #: never drift apart by one edit. The constant is in app.js, the first
    #: script index.html loads, not settings.js, the last: a name declared in
    #: the last script on the page cannot be read by anything that runs at
    #: load, which is why `aiNameNow()` needed a fallback to exist at all.
    assert f'const AI_NAME = "{help_chat.GUIDE_NAME}"' in app_js
    assert "const GUIDE_NAME = AI_NAME" in settings_js
    #: The sheet's own title comes from that constant rather than a literal.
    #: It is the name plus one word since 2026-09-20 (the owner: "the atlas
    #: help panel needs a better title to make it evident that it is the
    #: guide"), and that word is added to the constant rather than typed out
    #: beside it, so a rename still costs one edit. The sheet's accessible
    #: label is the same string as the visible title: two that disagree is a
    #: screen reader describing a panel nobody can see.
    assert "const GUIDE_TITLE = `${GUIDE_NAME} guide`" in settings_js
    assert "label: GUIDE_TITLE," in settings_js
    assert "name.textContent = GUIDE_TITLE;" in settings_js
    #: And the one surface that is markup says the same word.
    assert f"Ask {help_chat.GUIDE_NAME}</h4>" in index
    #: The model is told who it is in the first system message, not in a
    #: reference note that a question may or may not pull in.
    assert help_chat.SYSTEM_PROMPT.startswith(f"You are {help_chat.GUIDE_NAME},")
    #: The offline reply no longer names the guide, because it is no longer
    #: the guide speaking: it is the app's own help text, handed over
    #: verbatim (`offline_answer`). Claiming a persona wrote it would be the
    #: one false note in a reply whose whole point is that nothing wrote it.


def test_the_guide_can_answer_what_it_is():
    """It could not. "Who are you?" and "what can you do?" carry none of the
    feature keywords, so no topic matched, and the prompt tells the model to
    say it is not sure when it has no reference notes: the guide answered "I'm
    not sure" to the first question anybody asks a chat.
    """
    for question in ("who are you?", "what can you do?", "what is Atlas?"):
        ids = [topic["id"] for topic in help_chat.topics_for(question)]
        assert "guide" in ids, question
    body = next(t for t in help_chat.HELP_TOPICS if t["id"] == "guide")["body"]
    #: The three facts that make it useful rather than just present: the model
    #: it uses, what it cannot see, and that nothing is kept.
    assert "utility model" in body
    assert "cannot read your notes" in body
    assert "nothing said to it is saved" in body


def test_the_empty_chat_says_what_it_is_and_the_first_turn_retires_it():
    """An empty log under a field is a chat that has to be guessed at. The
    description is markup (it is true before anything has happened) and the
    two places that change the transcript are the two that have to know about
    it: the first appended row hides it, "New chat" brings it back.
    """
    from pathlib import Path

    frontend = Path(__file__).resolve().parents[1] / "frontend"
    index = (frontend / "index.html").read_text(encoding="utf-8")
    #: The chat itself moved to help-chat.js (a lazy bundle); read as one.
    settings_js = (frontend / "js" / "settings.js").read_text(encoding="utf-8") + (frontend / "js" / "help-chat.js").read_text(encoding="utf-8")

    assert 'id="help-chat-empty"' in index
    assert "cannot read your notes or your documents" in index
    start = settings_js.index("function helpChatAppendRow(")
    assert 'empty.hidden = true' in settings_js[start : settings_js.index("\n}\n", start)]
    #: New chat is a menu row since INBOX 224, not a button in the head.
    start = settings_js.index("function helpChatNewChat(")
    clear = settings_js[start : settings_js.index("\n}\n", start)]
    #: `replaceChildren()` here took the description away with the transcript
    #: and left a blank rectangle under the field.
    assert "list.replaceChildren()" not in clear
    assert 'empty.hidden = false' in clear


def test_every_atlas_prompt_hangs_off_a_help_panel_that_exists():
    """INBOX 224: the questions the app offers to ask Atlas live in one table,
    keyed by the id of the `data-help-for` panel they belong under.

    A key that names no panel is invisible: `addAtlasLine` looks the panel up
    and finds nothing, so the line simply never appears and nothing says so.
    Three of the first eight keys written were wrong in exactly that way, and
    only a sweep against the running app found them.
    """
    from pathlib import Path

    frontend = Path(__file__).resolve().parents[1] / "frontend"
    app = app_js_text()
    index = (frontend / "index.html").read_text(encoding="utf-8")

    table = app[app.index("const ATLAS_PROMPTS = {") :]
    table = table[: table.index("\n};")]
    keys = re.findall(r'"([a-z0-9-]+)": "', table)
    assert len(keys) >= 8, keys
    panels = set(re.findall(r'data-help-for="([^"]+)"', index))
    missing = [key for key in keys if key not in panels]
    assert not missing, f"ATLAS_PROMPTS keys with no help popover: {missing}"
    #: And every question reads as a question, since that is what is printed
    #: after "Ask Atlas: ".
    asked = re.findall(r'": "([^"]+)"', table)
    assert all(q.endswith("?") for q in asked), [q for q in asked if not q.endswith("?")]


def test_the_palette_offers_a_typed_question_to_atlas():
    """A jump list has no answer for "how do I turn off web search?", so the
    box went empty, which reads as "this app has no answer"."""

    app = app_js_text()
    start = app.index("function paletteMatches(")
    body = app[start : app.index("\n}\n", start)]
    assert 'endsWith("?")' in body and "askAtlasAbout" in body
    #: The palette lists no documents any more (INBOX 666), so the guard for
    #: the Library's lazy `docs` went with the document group.
    assert "docs" not in body


def test_the_palette_offers_a_how_question_without_its_question_mark():
    """Audit 1028 S43: help is a typed question away. "how do I export" has
    the same answer as the same line with a "?", so the palette offers both to
    the Guide; a command's own name ("how to use focus") is still a command."""

    import re

    from tests._app_js import app_js_text

    app = app_js_text()
    rule = re.search(r"const PALETTE_ASKS = (/.+?/i);", app)
    assert rule, "the palette has no PALETTE_ASKS rule"
    body = app[app.index("function paletteMatches(") :]
    body = body[: body.index("\n}\n")]
    assert "PALETTE_ASKS.test(" in body and "askAtlasAbout" in body
    pattern = re.compile(rule.group(1)[1:-2], re.I)
    for typed in ("how do I export my notes", "where is the bin", "how to turn off web search", "can I change the font", "why is search slow"):
        assert pattern.search(typed), typed
    for typed in ("export", "bin", "how", "graph", "font size", "whatever"):
        assert not pattern.search(typed), typed


def test_atlas_has_a_shortcut_and_it_is_in_the_registry():
    """In `DEFAULT_SHORTCUTS`, which is what puts it in the shortcuts sheet and
    in the collision check, rather than bound in a listener of its own."""

    app = app_js_text()
    start = app.index("const DEFAULT_SHORTCUTS = {")
    table = app[start : app.index("\n};", start)]
    assert "askAtlas: {" in table
    assert "askAtlas: () => askAtlasAbout" in app


def test_atlas_has_a_stop_while_a_question_is_out():
    """The owner, 2026-09-14: "there's no way to stop a response on the atlas
    interface window". The send button is the stop while busy: the request
    carries an abort signal, the reveal checks it, and a click while busy
    aborts instead of submitting."""
    from pathlib import Path

    js = "".join((Path(__file__).resolve().parents[1] / "frontend" / "js" / n).read_text(encoding="utf-8") for n in ("settings.js", "help-chat.js"))
    assert "helpChatAbort = new AbortController()" in js
    ask = js[js.index('apiJson("/help/ask"'):]
    assert "signal," in ask[:200]
    assert "function helpChatReveal(row, content, signal = null)" in js
    assert "if (signal?.aborted)" in js
    assert 'sendBtn.type = busy ? "button" : "submit"' in js
    assert 'icon.className = busy ? "ph ph-stop"' in js


def test_new_chat_is_offered_after_a_stopped_question():
    from pathlib import Path

    js = "".join((Path(__file__).resolve().parents[1] / "frontend" / "js" / n).read_text(encoding="utf-8") for n in ("settings.js", "help-chat.js"))
    assert 'const said = helpChatHistory.length > 0 || Boolean($("help-chat-messages")?.querySelector(".help-chat-msg"))' in js
    finally_block = js[js.index("    helpChatSetBusy(false);") :]
    assert "renderHelpChatMenu();" in finally_block[:120]


def test_the_help_turn_can_be_streamed(monkeypatch):
    """Reported of the Guide: the reply "will be blurted out really fast like
    it isnt streaming but just outputting at once", and its thinking "only
    shows up after the response is finished". Both followed from the route
    answering in one piece: the panel could only fake the writing with a timer
    and had nothing to show until the whole turn existed."""

    class FakeProvider:
        def is_running(self):
            return True

        def chat_stream(self, model, messages, mode=None):
            yield {"thinking_delta": "weighing it up"}
            yield {"content_delta": "Press "}
            yield {"content_delta": "the button."}

    class FakeManager:
        def utility_model(self):
            return "test-model"

    events = list(
        help_chat.answer_stream("how do I save?", FakeManager(), FakeProvider())
    )
    assert [e["type"] for e in events] == ["thinking", "delta", "delta", "done"]
    assert events[0]["text"] == "weighing it up"
    assert events[-1]["content"] == "Press the button."


def test_the_streamed_turn_sends_the_same_prompt_as_the_one_shot_turn():
    """One builder for both, so a fix to the grounding of one surface cannot
    miss the other."""
    streamed, topics = help_chat._prompt_for("how do I save?", [], "notes", "")
    assert streamed[0]["content"] == help_chat.SYSTEM_PROMPT
    assert streamed[-1] == {"role": "user", "content": "how do I save?"}
    assert isinstance(topics, list)


class _Offline:
    def is_running(self):
        return False


class _FakeManager:
    def utility_model(self):
        return "test-model"


def test_a_stopped_provider_still_answers_the_streamed_turn():
    events = list(help_chat.answer_stream("anything", _FakeManager(), _Offline()))
    assert events[-1]["type"] == "done"
    assert events[-1]["content"]


#: **The guide answers with no model at all.**
#:
#: Asked for directly: "I want to maximise the ability and function of all the
#: application features without ai, the ai features should just be the bonus."
#:
#: The guide is the one AI surface that never needed a model to be useful: its
#: whole knowledge of this app is `HELP_TOPICS`, hand-written, and those
#: paragraphs are also the model's only source of facts when a model does
#: answer. With the provider stopped it used to say it was unavailable while
#: holding the exact paragraph that answered the question.
def test_the_guide_answers_from_its_own_help_text_with_no_model():
    reply = help_chat.offline_answer("how do I set a reminder?")
    #: INBOX 1414: that it is the app's help is said by the byline and the
    #: "From the help" tab (`system`), once, not repeated in the text.
    assert "system" in reply and help_chat.OFFLINE_LEAD not in reply["content"]
    #: The body of the topic the keywords reached, not a paraphrase of it:
    #: the answer's "From the help" view (INBOX 787; the composed answer is
    #: the default view).
    topics = help_chat.topics_for("how do I set a reminder?")
    assert topics, "the fixture question must match a topic, or this proves nothing"
    assert topics[0]["body"] in reply["system"]["content"]
    #: And the same chips an answered turn carries: they are what turn "that
    #: lives on the Reminders tab" into a way to get there, and they are
    #: exactly as true with the model off.
    assert reply["badges"] and reply["sources"]


def test_the_streamed_offline_turn_is_the_same_reply():
    """One composer, so the streamed and one-shot turns cannot drift: the same
    reason `_prompt_for` exists for the online pair."""
    question = "how do I set a reminder?"
    once = help_chat.answer(question, _FakeManager(), _Offline())
    streamed = list(help_chat.answer_stream(question, _FakeManager(), _Offline()))
    assert streamed[-1]["content"] == once["content"]
    assert streamed[-1]["badges"] == once["badges"]
    assert "".join(e["text"] for e in streamed if e["type"] == "delta") == once["content"]


def test_a_question_the_help_text_cannot_place_says_so_and_says_what_to_try():
    reply = help_chat.offline_answer("xyzzy plugh frobnicate")
    assert reply["content"] == help_chat.OFFLINE_NOTHING_MATCHED
    assert "Settings" in reply["content"], "it has to name somewhere to look next"


def test_an_unplaceable_question_falls_back_to_what_is_on_screen():
    """A question this could not place is still asked from somewhere, and that
    somewhere describes itself: the app sends the help text for the surface in
    view as `context`."""
    reply = help_chat.offline_answer(
        "xyzzy plugh frobnicate", context="The board holds cards you can drag."
    )
    assert "The board holds cards you can drag." in reply["content"]


def test_performance_mode_has_a_help_topic():
    """Reported with a screenshot: "What does Performance mode do?" answered
    "I'm not sure" with a Dashboard badge. The setting existed, the help
    text did not, so the model was told to say it was not sure and did."""
    topics = help_chat._matching_topics("What does Performance mode do?")
    assert [t["id"] for t in topics][:1] == ["appearance"]
    assert "Performance mode" in topics[0]["body"]
    assert "2 cores" in topics[0]["body"]



# --- which model a real request actually takes (INBOX 274) --------------------
#
# The owner, 2026-09-20: the Guide "doesnt use the utility model and instead
# uses the chat model". Every line of copy around the panel says "your utility
# model", and `help_chat` does call `model_manager.utility_model()`, so the
# disagreement is not in this module at all: it is in what `utility_model()`
# answers. It falls back to the chat model in two separate cases, and a reading
# of the source is not proof of which one a running app is in, so these drive a
# real request through a real `ModelManager` and read back the model the
# provider was actually handed.


def _guide_model(ai_client, fake_ollama) -> str:
    """The model a real streamed Guide request hands the provider."""
    fake_ollama.chat_models.clear()
    response = ai_client.post("/help/ask/stream", json={"question": "how do I save a note?"})
    assert response.status_code == 200
    assert fake_ollama.chat_models, "the turn never reached the provider"
    return fake_ollama.chat_models[-1]


def test_the_guide_takes_the_utility_model_when_one_is_set(ai_client, fake_ollama):
    """The case the copy describes, and the only one of the three in which
    "your utility model" is the whole truth."""
    from tessellate.core import deps

    manager = deps.get_model_manager()
    manager.set_chat_model("big-chat-model")
    manager.set_utility_model("small-utility-model")
    assert _guide_model(ai_client, fake_ollama) == "small-utility-model"


def test_the_guide_falls_back_to_the_chat_model_when_no_utility_model_is_chosen(
    ai_client, fake_ollama
):
    """Fallback one, and the likelier of the two to be what was reported: the
    preference ships empty, so a notebook that has never opened Settings and
    picked a small model is running the chat model here by design. Nothing to
    fix in `help_chat`; the fix, if the reader wants a different model, is to
    choose one, and this pins that the fallback is the chat model and not
    something else."""
    from tessellate.core import deps

    manager = deps.get_model_manager()
    manager.set_chat_model("big-chat-model")
    manager.set_utility_model("")
    assert _guide_model(ai_client, fake_ollama) == "big-chat-model"


def test_the_guide_keeps_the_utility_model_when_smart_routing_is_off(
    ai_client, fake_ollama
):
    """The owner's decision, 2026-09-24 (WORLD_CLASS_PLAN section 20): the
    routing switch moves background jobs onto the chat model; the Guide is a
    panel you type into, so it keeps the utility model either way."""
    from tessellate.core import deps

    manager = deps.get_model_manager()
    manager.set_chat_model("big-chat-model")
    manager.set_utility_model("small-utility-model")
    deps.get_config().set_preference("smart_model_routing_enabled", False)
    assert _guide_model(ai_client, fake_ollama) == "small-utility-model"


def test_the_streamed_guide_turn_does_not_turn_thinking_off(ai_client, fake_ollama):
    """The owner: "thinking boxes dont render". They could not: the streamed
    turn ran in the `quick` preset, whose `think` is `False`, so
    `request_extras` sent `think: False` to any model with thinking to turn
    off and `chat_stream`'s `thinking_delta` branch never fired. The panel's
    `.help-chat-think` block was drawing an event that could not arrive.

    `presets.GUIDE_MODE` is Quick's brevity with `think` left unset, and unset
    means the field is never sent, so a reasoning model reasons and an
    ordinary one is unaffected."""
    from tessellate.ai import presets

    fake_ollama.chat_modes.clear()
    response = ai_client.post("/help/ask/stream", json={"question": "how do I save a note?"})
    assert response.status_code == 200
    assert fake_ollama.chat_modes[-1] == presets.GUIDE_MODE
    mode = presets.resolve(presets.GUIDE_MODE)
    assert mode.think is None, "the Guide must not send think: False, or its thinking box is dead"
    #: Not Quick's 256 since INBOX 410: a controls reference listed in full
    #: needs more (`test_help_controls.py` checks it against the longest).
    assert mode.max_output_tokens > presets.MODES["quick"].max_output_tokens
    assert mode.temperature == presets.MODES["quick"].temperature


def test_the_guide_preset_is_not_on_the_mode_picker():
    """It is the app's own choice for one panel, not a fourth thing for the
    reader to weigh up in the chat dock. `routes_chat` builds the picker from
    `MODES` and `routes_settings` refuses a preference outside it, so both stay
    three long."""
    from tessellate.ai import presets

    assert presets.GUIDE_MODE not in presets.MODES
    assert presets.GUIDE_MODE in presets.INTERNAL_MODES
    assert len(presets.MODES) == 3


def test_the_thinking_a_model_produces_reaches_the_stream(ai_client, fake_ollama):
    """End to end over the real route: a provider that thinks produces a
    `thinking` event on the wire, before the answer, which is what the panel
    reads to un-hide `.help-chat-think`."""
    import json

    fake_ollama.librarian_thinking = "checking the help text"
    response = ai_client.post("/help/ask/stream", json={"question": "how do I save a note?"})
    assert response.status_code == 200
    events = [json.loads(line) for line in response.text.splitlines() if line.strip()]
    kinds = [event["type"] for event in events]
    assert kinds[0] == "thinking", kinds
    assert events[0]["text"] == "checking the help text"
    assert "delta" in kinds and kinds[-1] == "done"


def test_the_streamed_answer_arrives_in_more_than_one_piece(ai_client, fake_ollama):
    """The owner: "the streaming is just off". A reply delivered as one
    `delta` is a reply the panel can only paint in one frame, whatever the
    client does with it, so the route is held to passing the provider's pieces
    through as pieces rather than joining them and sending the join."""
    import json

    response = ai_client.post("/help/ask/stream", json={"question": "how do I save a note?"})
    deltas = [
        json.loads(line)
        for line in response.text.splitlines()
        if line.strip() and json.loads(line)["type"] == "delta"
    ]
    assert len(deltas) >= 2, deltas


def test_the_guide_preset_sends_no_thinking_toggle_to_ollama():
    """The seam the fix actually turns on, tested at the seam.

    `Provider.request_extras` is where a preset's `think` becomes a field in
    the request, and it is Ollama's dialect that has one: the OpenAI shape has
    no standard equivalent and its `request_extras` returns nothing, so a
    browser measurement against an OpenAI-compatible stand-in cannot tell the
    two presets apart at all. This can.

    On a model that declares `thinking`, `quick` sends `think: False` and the
    model obeys, which is why the Guide's `.help-chat-think` block had never
    been drawn on an Ollama backend. `GUIDE_MODE` sends nothing, and nothing
    means "whatever the model does by default".
    """
    from tessellate.ai import presets
    from tessellate.ai.ollama_client import OllamaClient

    class _Thinker(OllamaClient):
        def supports(self, model, capability):
            return capability == "thinking"

    client = _Thinker(base_url="http://127.0.0.1:1")
    assert client.request_extras("quick", "reasoner") == {"think": False}
    assert client.request_extras(presets.GUIDE_MODE, "reasoner") == {}
    #: And the headroom follows the toggle: a turn that may think is given
    #: room to think in on top of its reply cap, rather than the reply and the
    #: reasoning competing for the same 256 tokens (§35A.3).
    assert client.thinking_allowance("quick", "reasoner") == 0
    assert client.thinking_allowance(presets.GUIDE_MODE, "reasoner") > 0


# --- The guide answers for the surfaces the app has (INBOX 304) -------------
#
# The owner asked the Atlas guide "Where do reminders live?", which is the
# first question the panel itself offers, and was told "I'm not sure where
# reminders live. Please check the Help topics above this chat", with Notes
# and What it remembers named as the sources. Measured, the corpus had a
# reminders entry all along: `_matching_topics` never reached it, because its
# keyword is "reminder" and the pattern is `\breminder\b`, which the plural in
# the question does not match. Nothing matched, the Notes tab's own topics
# filled the gap, and the model was handed reference notes about capture and
# memory for a question about reminders. Every plural in the app had the same
# hole: "documents", "notes", "spaces", "backups".
#
# These are the tests that hold the guide to its job rather than to its code.
# A guide that cannot answer for a surface this app ships is broken however
# well its retrieval reads, and a panel that offers a question it cannot
# answer is the worst version of the same fault.

#: One question per major surface, in the words a person uses rather than the
#: words the keyword table happens to hold, and the topic each must reach.
_SURFACE_QUESTIONS = [
    ("Where do reminders live?", "reminders"),
    ("Where do my documents live?", "documents"),
    ("How do I take notes?", "capture"),
    ("What is the whiteboard for?", "whiteboard"),
    ("What do the graphs show me?", "graph"),
    ("What goes in the library?", "library"),
    ("How do I chat with my notes?", "ask-chat"),
    ("What does the timeline show?", "timeline"),
    ("What are spaces?", "spaces"),
    ("Where are my backups kept?", "storage"),
    ("What is the status bar telling me?", "statusbar"),
]


def test_every_major_surface_has_reference_notes_of_its_own():
    for question, expected in _SURFACE_QUESTIONS:
        ids = [topic["id"] for topic in help_chat.topics_for(question)]
        assert ids, f"no reference notes at all for {question!r}"
        assert expected in ids, f"{question!r} reached {ids}, not {expected!r}"


def test_a_surface_question_reaches_the_model_grounded_not_empty_handed(
    ai_client, fake_ollama
):
    """End to end, through the route the panel calls.

    The system prompt tells the model to say it is not sure when it is given
    no reference notes, so "was a reference block sent" is the measurable
    form of "could this answer have been 'I'm not sure'". There is no model
    in this sandbox: `fake_ollama` stands in for one, and what is asserted is
    the prompt that reached it, not the words it replied with.
    """
    for question, expected in _SURFACE_QUESTIONS:
        fake_ollama.librarian_reply = "Reference answer."
        response = ai_client.post("/help/ask", json={"question": question})
        assert response.status_code == 200
        sent = fake_ollama.chat_calls[-1]
        reference = [m["content"] for m in sent if "Reference notes" in m["content"]]
        assert reference, f"{question!r} was sent to the model with no reference notes"
        body = next(t["body"] for t in help_chat.HELP_TOPICS if t["id"] == expected)
        assert body[:40] in reference[0], f"{question!r} was grounded in the wrong topic"


def test_the_sources_named_for_a_surface_question_are_that_surface(
    ai_client, fake_ollama
):
    """The screenshot's real tell: the answer named Notes and What it
    remembers under a question about reminders. Those are `TAB_TOPICS`
    filling an empty match, which is correct behaviour for "how does this
    work?" and wrong for a question that names its own subject."""
    fake_ollama.librarian_reply = "The Reminders tab."
    response = ai_client.post(
        "/help/ask", json={"question": "Where do reminders live?", "tab": "notes"}
    )
    assert response.status_code == 200
    assert response.json()["sources"] == ["Reminders"]


def test_a_plural_question_finds_what_the_singular_finds():
    for singular, plural in (
        ("how do I set a reminder?", "where do reminders live?"),
        ("open a document", "where do my documents live?"),
        #: Was ("write a note", "where are my notes?"): two different
        #: questions, not one in two numbers; the second is a search.
        ("make a note", "how do I make notes?"),
        ("make a backup", "where are my backups?"),
        ("what is a space?", "how do spaces work?"),
    ):
        one = [t["id"] for t in help_chat._matching_topics(singular)]
        many = [t["id"] for t in help_chat._matching_topics(plural)]
        assert one, f"{singular!r} matched nothing, so the pair proves nothing"
        assert one[0] in many, f"{plural!r} reached {many}, the singular reached {one}"


def _atlas_questions() -> list[str]:
    """Every question the app itself offers to ask Atlas: the three starters
    under the transcript, and the line at the foot of a help popover."""
    app = app_js_text()
    starters = app[app.index("const ATLAS_STARTERS = [") :]
    starters = starters[: starters.index("\n];")]
    per_tab = app[app.index("const ATLAS_TAB_STARTERS = {") :]
    per_tab = per_tab[: per_tab.index("\n};")]
    prompts = app[app.index("const ATLAS_PROMPTS = {") :]
    prompts = prompts[: prompts.index("\n};")]
    return (
        re.findall(r'"([^"]+)"', starters)
        + re.findall(r'"([^"]+)"', per_tab)
        + re.findall(r'": "([^"]+)"', prompts)
    )


def test_every_question_the_app_offers_to_ask_atlas_is_answerable():
    """A suggested question the corpus cannot answer is a promise the guide
    breaks on the first tap, and "Where do reminders live?" was the first
    starter in the panel. Held here rather than by care: the table is in
    `frontend/js/app.js` and the corpus is in Python, so nothing else sees both.
    """
    questions = _atlas_questions()
    assert len(questions) >= 25, questions
    unanswerable = [q for q in questions if not help_chat.topics_for(q)]
    assert not unanswerable, f"Atlas offers questions it cannot answer: {unanswerable}"


def test_a_keyword_still_does_not_match_inside_a_longer_word():
    """The inflection fix must not turn the whole-word rule back into a
    substring one: "ask" may reach "asks" and "asked", never "basket"."""
    assert help_chat._matching_topics("where's the picnic basket for our task?") == []
    assert help_chat._matching_topics("the weather is nice today") == []


def test_the_panel_does_not_promise_a_model_it_may_not_use():
    """INBOX 274, 288 and 304 are the same report three times: "it doesnt use
    my utility model". Measured at the provider in `test_feature_models.py`,
    the code is right and the copy was wrong: a guide turn takes the utility
    model with smart model routing on, the chat model with it off, and the
    guide's own row in the per-feature table over both. Three lines of copy
    promised the first of those three as though it were the only one, which
    is why the report keeps coming back from a reader who is in one of the
    other two.

    The '?' popover carries the whole rule, in place of the promise.
    """
    index = (
        Path(__file__).resolve().parents[1] / "frontend" / "index.html"
    ).read_text(encoding="utf-8")
    assert "from your utility model" not in index
    popover = index[index.index('id="help-chat-help"') :][:900]
    assert "smart model routing is on" in popover
    assert "on the chat model while it is off" in popover


def test_the_composer_is_not_gated_on_a_model_the_guide_does_not_need(client):
    """`offline_answer` is the whole point: with no model, `/help/ask` hands
    back the app's own help text for what was asked and says so. Measured in
    a browser with no model running, the field and Send carried
    `data-needs-model` and were disabled, so the reply nobody needed a model
    for could not be asked for. INBOX 203's own inventory says a control that
    degrades without a model is not gated; this one degrades exactly that way.
    """
    index = (
        Path(__file__).resolve().parents[1] / "frontend" / "index.html"
    ).read_text(encoding="utf-8")
    composer = index[index.index('id="help-chat-form"') :]
    composer = composer[: composer.index("</form>")]
    assert "data-needs-model" not in composer
    #: And the route it posts to really does answer without one.
    body = client.post("/help/ask", json={"question": "Where do reminders live?"}).json()
    assert "Overdue" in body["content"]
    assert body["sources"] == ["Reminders"]
