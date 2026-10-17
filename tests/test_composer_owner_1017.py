"""The owner's 2026-10-17 composer reports (INBOX 904), each reproduced first
through `/chat/stream` with no model, as the owner met it."""

from __future__ import annotations

import json

from tessellate.ai import composer
from tessellate.entry import manager


def _ask(client, question: str, **body) -> dict:
    events: dict[str, list] = {}
    with client.stream("POST", "/chat/stream", json={"question": question, "answer_from": "notes", **body}) as response:
        assert response.status_code == 200
        for line in response.iter_lines():
            if line.strip():
                event = json.loads(line)
                events.setdefault(event["type"], []).append(event)
    events["text"] = "".join(e["delta"] for e in events.get("answer", []))
    return events


def _seed(session) -> None:
    manager.create_entry(session, "Grocery list: milk and eggs for Friday")
    manager.create_entry(session, "Golf practice after work, hit some balls")
    session.commit()


def test_saved_recently_lists_the_newest_notes_not_the_word_saved(ai_client, session):
    """B30 (screenshot): "What have I saved recently?" answered 'I found no
    mention of "saved"'. Retrieval already read it as a recency ask; the
    composer threw that away because "saved" survived as a subject word."""
    _seed(session)
    text = _ask(ai_client, "What have I saved recently?", notes_only=True, use_tools=False)["text"]
    assert "no mention" not in text.lower(), text
    assert "Grocery list" in text and "Golf practice" in text, text


def test_a_key_mash_is_a_mash_not_a_name_for_the_assistant(ai_client, session):
    """B08: "asdkjhfgs" was answered "Asdkjhfgs, reporting in", as if it were a
    nickname. Keys pressed at random are said to be that, and the reply offers
    what the app can do."""
    from tessellate.ai import intent

    for mash in ("asdkjhfgs", "jkjkjkjk", "xzxzxz", "hhhhhhh", "asdf asdf", "kjhgf lkjh", "sdfsdfsdf"):
        assert intent.is_mash(mash), mash
    for word in ("test", "brotatockiibidyrizzler", "rhythms", "strengths", "dentist", "hello there", "Tessellate"):
        assert not intent.is_mash(word), word
    _seed(session)
    text = _ask(ai_client, "asdkjhfgs", notes_only=True, use_tools=False)["text"]
    assert "reporting in" not in text.lower() and "asdkjhfgs" not in text.lower(), text
    from tessellate.ai import composer

    assert any(text.startswith(line.split("{")[0]) for line in composer.SOCIAL["unclear"]), text


def test_a_test_message_is_acknowledged_as_a_test(ai_client, session):
    """B08: "test" got 'I found no mention of "test"'. A test message gets a
    reply that says the test arrived and what to try next, in any of the ways
    people type one."""
    _seed(session)
    for message in ("test", "testing", "Test 123", "testing testing", "is this thing on?", "hello world"):
        text = _ask(ai_client, message, notes_only=True, use_tools=False)["text"]
        assert "no mention" not in text.lower() and "nothing in your notes" not in text.lower(), (message, text)
        #: The family's line, and (O5) perhaps an ask about the newest note.
        assert any(text.startswith(line) for line in composer.SOCIAL["test"] + composer.SOCIAL_PROFESSIONAL["test"]), (message, text)


def test_the_capability_rundown_is_composed_and_sized_to_the_request():
    """B10: the rundown was one stored answer and called itself Atlas. It is
    now composed: it names itself Atlas's assistant, says how to reach Atlas
    (connect a model), varies, and is shorter or longer as asked."""
    from tessellate.ai import capability

    medium = {capability.overview("what can you do", seed=str(i)) for i in range(12)}
    assert len(medium) > 4, "the same words every time"
    for text in medium:
        assert "assistant" in text.lower() and "Atlas" in text
        assert "connect a model" in text.lower() or "add one" in text.lower(), text
        assert text.count("**") == 6, text
    short = capability.overview("what can you do, briefly?", seed="a")
    long = capability.overview("tell me everything you can do", seed="a")
    assert len(short) < 200 < len(long), (len(short), len(long))
    assert long.count("**") == 12
    on = capability.overview("what can you do", model_running=True, seed="a")
    assert "connect a model" not in on.lower() and "connected" in on.lower(), on
    pro = capability.overview("what can you do", voice="professional", seed="a")
    assert "I'm" not in pro.split("\n")[0], pro


def test_who_are_you_says_it_is_the_assistant_not_atlas(ai_client, session):
    """B10: the composer is Atlas's assistant; Atlas is the model. Asked who it
    is, it says so, and every identity line stays in that voice."""
    for table in (composer.SOCIAL, composer.SOCIAL_PROFESSIONAL):
        for line in table["who"]:
            assert "assistant" in line.lower(), line
        for line in table["who"] + table["about_app"]:
            assert not line.startswith(("I'm Atlas.", "I am Atlas.", "Atlas,", "Atlas ", "Atlas.")), line
    text = _ask(ai_client, "who are you", notes_only=True, use_tools=False)["text"]
    assert "assistant" in text.lower(), text


def test_the_rundown_follows_the_length_the_person_asked_for(ai_client, session):
    short = _ask(ai_client, "what can you do briefly", notes_only=True, use_tools=False)["text"]
    long = _ask(ai_client, "tell me everything you can do", notes_only=True, use_tools=False)["text"]
    assert "no note" not in long.lower() and "**Private:**" in long, long
    assert len(short) < 200 < len(long), (len(short), len(long))


def test_what_do_my_notes_cover_is_answered_about_the_notebook(ai_client, session):
    """B02 (screenshot): "what do my notes cover so far??" said none of the notes
    mention "cover" or "far". It is a question about the whole notebook, so it
    is answered with what the notebook holds: areas, tags and the span."""
    manager.create_entry(session, "Squats 5x5 and bench 3x8 today", "Gym", ["fitness", "legs"])
    manager.create_entry(session, "Rows and pull-ups, felt strong", "Gym", ["fitness"])
    manager.create_entry(session, "Design assignment 2 due next Friday", "Uni", ["design"])
    session.commit()
    for question in (
        "what do my notes cover so far??",
        "what's in my notebook",
        "what have I been writing about",
        "give me an overview of my notes",
        "what topics do I write about",
    ):
        text = _ask(ai_client, question, notes_only=True, use_tools=False)["text"]
        assert "mention" not in text.lower() and "couldn't find" not in text.lower(), (question, text)
        assert "Gym" in text and "Uni" in text and "fitness" in text, (question, text)
        assert "3 notes" in text, (question, text)


def test_the_plain_chat_models_know_the_users_clock(app_state, monkeypatch):
    """B40: the agent prompt carried the date and time, the plain Ask and Chat
    prompts did not, so a model answering "what day is it" or "is it too late
    to call" had to guess. Last in the system message, as the agent's is
    (`test_prompt_prefix_stability.py`)."""
    import datetime as dt

    from tessellate.ai import librarian
    from tessellate.core import config

    when = dt.datetime(2026, 10, 17, 21, 45, 30, tzinfo=dt.timezone.utc)
    monkeypatch.setattr(config, "user_now", lambda cfg: when)
    marker = " The current date and time is 2026-10-17T21:45:00"
    for system in (
        librarian.system_content(),
        librarian.build_conversational_messages("how are you", "smalltalk")[0]["content"],
    ):
        assert "Today is Saturday" in system and marker in system, system[-200:]
        assert system.index(marker) > len(system) * 0.5
        assert system.rstrip().endswith(")."), system[-80:]


def test_a_category_named_for_the_app_is_not_renamed_to_a_generic_topic(session):
    """B31 (screenshot): Tidy offered "Rename About Tessellate to Knowledge
    Management?" (67%). Tessellate is a topic of its own now, so a category
    named for it keeps its name."""
    from tessellate.entry import tidy

    for text in (
        "Tessellate keeps everything on this machine, notes, search, even the AI.",
        "Linking notes together in Tessellate: type [[a note]] and it becomes a real link.",
        "Try the composer in Tessellate: ask a question about your notes.",
        "Tessellate delete these whenever, they only fill the graph.",
        "Magic add in Tessellate turns a sentence into a reminder.",
    ):
        manager.create_entry(session, text, "About Tessellate", ["welcome"])
    session.commit()
    rows = tidy._rows_category_names(session, "standard")
    assert not [r for r in rows if "About Tessellate" in r["title"]], rows


def test_tag_with_atlas_also_offers_other_categories(client):
    """B80: "Tag with Atlas" offered only links: no way to add a tag of one's
    own and no other category to move to. The reply now carries the other
    places the note could go, each with its reason."""
    for text, category in (
        ("Squats 5x5 and bench 3x8 today, legs sore", "Gym"),
        ("Deadlifts and rows, then a long run", "Gym"),
        ("Design assignment due Friday, wireframes first", "Uni"),
        ("Lecture on wireframes and the design brief", "Uni"),
    ):
        client.post("/entries", json={"content": text, "category": category})
    mine = client.post("/entries", json={"content": "Finish the wireframes for the design assignment", "category": "Gym"}).json()
    out = client.post(f"/entries/{mine['id']}/reevaluate").json()
    assert "suggested_categories" in out, sorted(out)
    names = [c["name"] for c in out["suggested_categories"]]
    assert "Uni" in names and mine["category"] not in names, names
    assert all("why" in c for c in out["suggested_categories"])


def test_the_tag_with_atlas_panel_draws_categories_and_an_own_tag_field():
    from pathlib import Path

    js = (Path(__file__).resolve().parent.parent / "frontend" / "js" / "tag-suggest.js").read_text(encoding="utf-8")
    assert "data.suggested_categories" in js and "Could also go in:" in js
    assert 'aria-label", "Add a tag of your own"' in js and "No tags to suggest for this one." in js


def test_a_time_with_no_note_in_it_is_said_as_that_with_where_the_notes_are(client, session):
    """O1: "What did I write last month?" in a notebook begun this week was
    answered "I couldn't find any saved notes matching that question" (the
    Guide's own suggested asks, measured 2026-10-17)."""
    _seed(session)
    for body in ({"use_tools": False}, {"notes_only": True, "use_tools": False}):
        text = _ask(client, "What did I write last month?", **body)["text"]
        assert "couldn't find" not in text and "last month" in text.lower(), (body, text)
        assert "All your notes are from" in text or "Every entry is dated" in text, text
    for voice in ("natural", "professional"):
        lines = {composer.empty_window("last month", None, None, voice=voice, seed=str(i)) for i in range(60)}
        assert len(lines) >= 8, (voice, lines)
        assert all("!" not in line and chr(0x2014) not in line and line[0].isupper() for line in lines), lines


def test_a_hello_ends_on_an_ask_about_the_newest_note(client, session):
    """O5 (B07: replies vary and feel alive): a stored opener, then an
    invitation built on a word of the newest note, eight wordings a voice,
    never after an opener that already asks or suggests."""
    for voice in ("natural", "professional"):
        lines = composer.INVITES[voice]
        assert len(set(lines)) >= 8 and all("{subject}" in line and "!" not in line and chr(0x2014) not in line for line in lines)
    said = {composer.social("good morning", invite="golf", seed=str(i)) for i in range(40)}
    assert len(said) >= 6 and all("golf" in s or s.endswith("?") for s in said), said
    assert sum("golf" in s for s in said) >= 4, said
    assert "golf" not in composer.social("asdkjhfgs", invite="golf")
    _seed(session)
    texts = [_ask(client, hello, use_tools=False)["text"] for hello in ("hi", "hello", "good morning", "hey there", "morning")]
    assert any("golf" in text for text in texts), texts
    #: The ask it offers is one the notes answer.
    assert "Golf practice" in _ask(client, "what did I write about golf", use_tools=False)["text"]


#: How-tos answered in Chat with no model, with words of the sentence that
#: answers each (O1, BACKLOG "Composer quality outside Ask"): measured
#: 2026-10-17, five of these led with a sentence about something else.
HOW_TOS = (
    ("How do I add a reminder?", "Magic add"),
    ("how do i make a reminder", "Magic add"),
    ("how do I export my notes", "Export your data"),
    ("how do I back up my notes", "Back up now"),
    ("how do I connect a model", "Connect a model"),
    ("how do I hide unlinked notes on the map of notes", "Hide unlinked"),
    ("how do I link two notes together", "typing [["),
)


def test_a_how_to_in_chat_leads_with_the_sentence_that_answers_it(client, session):
    """O1 (BACKLOG "Composer quality outside Ask"): "How do I add a reminder?"
    in Chat answered "The Reminders tab groups items into Overdue / Today /
    Upcoming / Done", and "how do I export my notes" led with Tidy up
    duplicates. The verb asked counts in full even when the topic is named
    for it, and a pair of words the sentence also says counts extra."""
    from tessellate.ai import help_chat, reading

    assert reading.__name__
    for question, said in HOW_TOS:
        line, _ = composer.help_line(question, help_chat.topics_for(question))
        assert said in line, (question, line)
    _seed(session)
    for body in ({"use_tools": False}, {"use_tools": True}, {"notes_only": True, "use_tools": False}):
        text = _ask(client, "How do I add a reminder?", **body)["text"]
        assert "Magic add" in text, (body, text)
        #: Read as a notes question (no app word the router knows), found in
        #: no note, and plainly about the app: the help says it.
        text = _ask(client, "how do I connect a model", **body)["text"]
        assert text.startswith("Connect a model in Settings, Models"), (body, text)
        text = _ask(client, "how do I learn python", **body)["text"]
        assert "Settings" not in text and "python" in text.lower(), (body, text)
