"""H3: behaviour tiers by model size (AGENT_SKILLS_REFORM, "Harness
robustness", phase H3).

Before: one boolean (`is_small_model`, under 8B) decided the toolbox, the
schema length, the round cap and the forced first call, and a 1.5B and a 7B
got the same treatment. Measured on Qwen2.5-1.5B: one "Make a note" turn ran
948 s to the 2,048-token reply cap, writing the note out in prose, and made no
call. Now one table (`agent.SIZE_TIERS`) holds every size decision, a small
model's tool rounds have a reply cap of their own, and prompt bookkeeping the
model echoes ("similarity 0.54", "note id 3") comes off the answer.
"""

from __future__ import annotations

import re
from pathlib import Path

import pytest

from tessellate.ai import agent
from tessellate.ai.answer_trim import strip_prompt_metadata, trim_assistant_padding


@pytest.mark.parametrize(
    ("name", "tier"),
    [
        ("qwen2.5-1.5b-instruct", "tiny"),
        ("granite4.1:2b", "tiny"),
        ("llama-3.2-3b-instruct", "small"),
        ("qwen3.5:4b", "small"),
        ("qwen3:8b", "large"),
        ("llama3.1:70b", "large"),
        ("llama3.2", "unsized"),
    ],
)
def test_a_model_s_name_picks_its_tier(name, tier):
    assert agent.size_tier(name).name == tier


def test_the_table_is_the_only_place_a_size_decision_lives():
    source = Path(agent.__file__).read_text(encoding="utf-8")
    head, tail = source.split("def size_tier", 1)
    body, rest = tail.split("\n\n\n", 1)
    assert "parameter_count(" in body
    for text in (head, rest):
        assert "is_small_model(" not in text and "parameter_count(" not in text
    assert "small_model" not in source.split("def _prepare_turn", 1)[1].split("def run_agent", 1)[0]


def test_the_tiers_differ_where_the_sizes_do():
    tiny, small, large, unsized = (agent.SIZE_TIERS[n] for n in ("tiny", "small", "large", "unsized"))
    assert tiny.reply_chars < small.reply_chars and large.reply_chars is None
    assert tiny.narrow_toolbox and small.narrow_toolbox and not large.narrow_toolbox
    assert tiny.force_first_call and not large.force_first_call
    assert tiny.max_rounds == agent.SMALL_MODEL_MAX_ROUNDS and large.max_rounds is None
    #: A name that says nothing is treated as large: narrowing a capable model
    #: on a guess is the worse mistake (`is_small_model`'s None).
    assert unsized._replace(name="large") == large


class _Session:
    def rollback(self):
        return None

    def commit(self):
        return None


class _Named:
    def __init__(self, name):
        self.name = name

    def chat_model(self):
        return self.name


class _Rambler:
    """Writes a note out in prose for ever, with tools offered: the measured
    1.5B failure. Records whether the stream was closed early."""

    def __init__(self):
        self.closed = False
        self.sent = 0

    def chat_tools_stream(self, model, messages, offered, mode=None):
        if not offered:
            yield {"final": {"content": "", "tool_calls": []}}
            return
        try:
            for _ in range(400):
                self.sent += 50
                yield {"content_delta": "Buy oat milk and remember the list. " + "x" * 14}
            yield {"final": {"content": "…", "tool_calls": [], "streamed": True}}
        finally:
            self.closed = True


def _ramble(monkeypatch, model):
    fake = _Rambler()
    monkeypatch.setattr(agent.tools, "execute_tool", lambda *a, **k: {})
    events = list(agent.run_agent(_Session(), "what is on my list", [], _Named(model), fake))
    text = "".join(e.get("delta", "") for e in events if e.get("type") == "answer")
    return fake, text


def test_a_tiny_model_s_tool_round_is_cut_at_its_reply_cap(monkeypatch, app_state):
    fake, text = _ramble(monkeypatch, "qwen2.5-1.5b-instruct")
    cap = agent.SIZE_TIERS["tiny"].reply_chars
    assert fake.sent <= cap + 100, fake.sent
    assert fake.closed
    assert agent.REPLY_CAP_NOTE.strip() in text


def test_a_large_model_is_never_cut(monkeypatch, app_state):
    fake, text = _ramble(monkeypatch, "qwen3:14b")
    assert fake.sent == 400 * 50
    assert agent.REPLY_CAP_NOTE.strip() not in text


@pytest.mark.parametrize(
    ("leaked", "clean"),
    [
        ("Your dentist note (note id 3) says Tuesday.", "Your dentist note says Tuesday."),
        ("Your dentist note (similarity: 0.54) says Tuesday.", "Your dentist note says Tuesday."),
        ("In note id 3, you wrote about boots.", "In the note, you wrote about boots."),
        ("The plumber note, with a similarity of 0.54, says Tuesday.", "The plumber note says Tuesday."),
        ("Your gym note (matched: gym, membership) is the one.", "Your gym note is the one."),
        ("1. (note id 7) [Work] Budget review", "1. Budget review"),
    ],
)
def test_prompt_bookkeeping_comes_off_the_answer(leaked, clean):
    assert strip_prompt_metadata(leaked) == clean
    assert trim_assistant_padding(leaked) == clean


@pytest.mark.parametrize(
    "kept",
    [
        "The similarity between the two plans is striking.",
        "Your note says the boiler code is 4471 (id badge in the drawer).",
        "Work has 20 notes.",
        "[Work] is the category I moved it to.",
    ],
)
def test_ordinary_words_are_left_alone(kept):
    assert strip_prompt_metadata(kept) == kept


def test_no_leaked_number_survives_the_patterns():
    assert not re.search(r"similarity|note id", strip_prompt_metadata("note id 3 (similarity 0.9)"))


# --- the found-not-fixed: a picture question read a whiteboard -------------------


class _Offered:
    def __init__(self):
        self.offered: list[list] = []

    def usable_context(self, model):
        return 32_768

    def chat_tools_stream(self, model, messages, offered, mode=None):
        self.offered.append([t["function"]["name"] for t in offered])
        yield {"final": {"content": "Here it is: [picture 1]", "tool_calls": []}}


_SKETCH_NOTE = {
    "id": 4,
    "title": "Planning meeting",
    "content": "Planning meeting whiteboard ![whiteboard sketch](/media/wb.png)",
    "category": "Work",
    "tags": [],
    "pictures": 1,
}


def _offered_for(monkeypatch, notes, question="Show me the whiteboard sketch from the planning meeting"):
    fake = _Offered()
    monkeypatch.setattr(agent.tools, "execute_tool", lambda *a, **k: {})
    list(agent.run_agent(_Session(), question, notes, _Named("qwen2.5-1.5b-instruct"), fake))
    return fake.offered[0]


def test_a_picture_already_in_hand_is_not_looked_for_on_a_board(monkeypatch, app_state):
    """Measured on Qwen2.5-1.5B (INBOX 527's eval): "Show me the whiteboard
    sketch" cued the board tools, and the model read a whiteboard instead of
    showing the note's picture, which was already in its prompt."""
    offered = _offered_for(monkeypatch, [_SKETCH_NOTE])
    assert not {"read_whiteboard", "search_whiteboard", "read_mindmap"} & set(offered), offered


def test_without_that_picture_the_board_is_still_offered(monkeypatch, app_state):
    offered = _offered_for(monkeypatch, [{**_SKETCH_NOTE, "pictures": 0}])
    assert "read_whiteboard" in offered


def test_a_picture_note_on_another_subject_leaves_the_board(monkeypatch, app_state):
    other = {**_SKETCH_NOTE, "title": "Garden", "content": "Garden beds ![beds](/media/g.png)"}
    offered = _offered_for(monkeypatch, [other])
    assert "read_whiteboard" in offered


def test_showing_a_picture_in_hand_is_offered_no_board_writes_either(monkeypatch, app_state):
    """H4, Qwen2.5-3B: with the reads gone, "Show me the whiteboard sketch"
    called `add_whiteboard_card` for the note and then tried to link cards: a
    write nobody asked for. Showing is not placing."""
    offered = _offered_for(monkeypatch, [_SKETCH_NOTE])
    assert not set(offered) & agent._CANVAS_TOOLS, offered


def test_placing_a_picture_on_a_board_still_offers_the_board(monkeypatch, app_state):
    offered = _offered_for(
        monkeypatch, [_SKETCH_NOTE], question="Add the whiteboard sketch from the planning meeting to my board"
    )
    assert "add_whiteboard_card" in offered


class _CreateWithTags:
    def __init__(self):
        self.n = 0

    def chat_tools_stream(self, model, messages, offered, mode=None):
        self.n += 1
        if self.n == 1:
            call = {"name": "create_note", "arguments": {"content": "buy oat milk", "tags": ["todo"]}}
            yield {"final": {"content": "", "tool_calls": [call], "raw_tool_calls": []}}
            return
        yield {"final": {"content": "I've created the note and tagged it todo.", "tool_calls": []}}


class _ThenCopies:
    """Qwen2.5-3B, H4: a successful write, then `create_note` holding the
    note it just changed (once with the prompt's fence markers in it)."""

    def __init__(self, first, copy):
        self.calls = [first, copy]

    def chat_tools_stream(self, model, messages, offered, mode=None):
        if self.calls:
            yield {"final": {"content": "", "tool_calls": [self.calls.pop(0)], "raw_tool_calls": []}}
            return
        yield {"final": {"content": "Done.", "tool_calls": []}}


_SNOWDON = "Snowdon trip: carry the new boots, start at Pen-y-Pass at 7am"


def _copy_turn(monkeypatch, first, copy):
    ran = []

    def execute(session, name, arguments, **kwargs):
        ran.append((name, arguments))
        return {"id": 3, "title": "Snowdon trip", "content": _SNOWDON}

    monkeypatch.setattr(agent.tools, "execute_tool", execute)
    list(agent.run_agent(_Session(), "q", [{"id": 3, "title": "Snowdon trip", "content": _SNOWDON, "category": "Travel", "tags": []}], _Named("qwen2.5-3b"), _ThenCopies(first, copy)))
    return [name for name, _ in ran]


def test_a_copy_of_the_note_just_changed_is_not_made(monkeypatch, app_state):
    ran = _copy_turn(
        monkeypatch,
        {"name": "edit_note", "arguments": {"note_id": 3, "content": f"{_SNOWDON}\nbring a rain jacket"}},
        {"name": "create_note", "arguments": {"content": f"{_SNOWDON}\nbring a rain jacket"}},
    )
    #: The edit parks for a Confirm card now (audit 1029 H2), so it has not run,
    #: and the copy is still not made behind it: that is the guard's point.
    assert ran == []


def test_a_note_holding_the_prompt_s_fence_is_not_made(monkeypatch, app_state):
    ran = _copy_turn(
        monkeypatch,
        {"name": "pin_note", "arguments": {"note_id": 3, "pinned": True}},
        {"name": "create_note", "arguments": {"content": f"<<<data note>>>\n{_SNOWDON}\n<<<end data>>>"}},
    )
    assert ran == ["pin_note"]


def test_a_new_note_after_a_write_is_still_made(monkeypatch, app_state):
    ran = _copy_turn(
        monkeypatch,
        {"name": "pin_note", "arguments": {"note_id": 3, "pinned": True}},
        {"name": "create_note", "arguments": {"content": "Buy oat milk and eggs for the trip"}},
    )
    assert ran == ["pin_note", "create_note"]


def test_a_small_model_s_toolbox_holds_preferences_only_when_asked(monkeypatch, app_state):
    """H4, Qwen2.5-3B under the forced first call: "Note down: ...", "Save
    this: ..." and "Put ... in my note" called `save_user_preference` (3 of 20)."""
    for question, wanted in (
        ("Note down: call Sam about the van", False),
        ("Save this: the plumber is free on Thursday", False),
        ("Remember that I prefer short answers", True),
        ("From now on call me Bray", True),
    ):
        offered = _offered_for(monkeypatch, [], question=question)
        assert ("save_user_preference" in offered) is wanted, (question, offered)


def test_a_note_made_with_tags_was_tagged(monkeypatch, app_state):
    """H4, Qwen2.5-3B: `create_note` with `tags`, then "tagged as todo", got
    "Heads up: I said I tagged a note, but I didn't actually run the tool"."""
    monkeypatch.setattr(agent.tools, "execute_tool", lambda *a, **k: {"id": 5, "title": "buy oat milk"})
    events = list(agent.run_agent(_Session(), "Make a note: buy oat milk", [], _Named("m"), _CreateWithTags()))
    text = "".join(e.get("delta", "") for e in events if e.get("type") == "answer")
    assert "Heads up" not in text, text


# --- the first round: a forced call acts, a question reads (H4, Qwen2.5-3B) ------


class _Rounds:
    """Records each round's offered tools and whether it was forced; the first
    round calls `search_notes`, the second answers."""

    def __init__(self):
        self.rounds: list[tuple[list, bool]] = []

    def usable_context(self, model):
        return 32_768

    def chat_tools_stream(self, model, messages, offered, mode=None, tool_choice=None):
        self.rounds.append(([t["function"]["name"] for t in offered], tool_choice == "required"))
        if len(self.rounds) == 1:
            call = {"name": "search_notes", "arguments": {"query": "dentist"}}
            yield {"final": {"content": "", "tool_calls": [call], "raw_tool_calls": []}}
            return
        yield {"final": {"content": "Done.", "tool_calls": []}}


def _rounds(monkeypatch, question, model="qwen2.5-3b-instruct", session=None):
    fake = _Rounds()
    monkeypatch.setattr(agent.tools, "execute_tool", lambda *a, **k: {"results": []})
    list(agent.run_agent(session or _Session(), question, [], _Named(model), fake))
    return fake.rounds


_HARMLESS_READS = {"get_current_time", "count_notes", "list_tags", "list_categories", "notebook_overview"}


@pytest.mark.parametrize(
    ("question", "wanted"),
    [
        ("Add 'bring a rain jacket' to my Snowdon trip note", "edit_note"),
        ("File the dentist note under Health", "edit_note"),
        ("Move the plumber note to Home", "edit_note"),
        ("Make a note: buy oat milk and eggs", "create_note"),
        ("Mark the reminder to pay rent as done", "complete_reminder"),
    ],
)
def test_a_forced_first_round_is_offered_the_writes_and_the_finders(monkeypatch, app_state, question, wanted):
    """Qwen2.5-3B, forced: "Add X to my note" called `get_current_time` and
    "File ... under Health" called `count_notes`; a forced round offered a
    harmless read takes it instead of acting."""
    rounds = _rounds(monkeypatch, question)
    first, forced = rounds[0]
    assert forced, question
    assert wanted in first, (question, first)
    assert not _HARMLESS_READS & set(first), (question, first)
    assert set(first) <= agent._WRITE_TOOLS | agent._LOCATING_TOOLS, first


@pytest.mark.parametrize(
    "question",
    ["Put 'buy stamps' in my shopping note", "Add 'bring a rain jacket' to my Snowdon trip note"],
)
def test_a_forced_edit_of_a_named_note_is_not_offered_a_new_note(monkeypatch, app_state, question):
    """Qwen2.5-3B, forced: "Put 'buy stamps' in my shopping note" called
    `create_note` 2 of 2: a new note is the wrong write for a named one."""
    first, forced = _rounds(monkeypatch, question)[0]
    assert forced and "edit_note" in first and "search_notes" in first
    assert "create_note" not in first, first


def test_the_round_after_a_forced_one_has_the_whole_toolbox_again(monkeypatch, app_state):
    rounds = _rounds(monkeypatch, "File the dentist note under Health")
    second, forced = rounds[1]
    assert not forced
    assert "get_current_time" in second and "list_categories" in second


@pytest.mark.parametrize(
    "question",
    [
        "What tags and what categories am I using?",
        "Which of my notes are pinned?",
        "Do I have anything tagged urgent",
        "How many notes are in my Health category?",
        "Is there a note about the dentist?",
    ],
)
def test_a_question_s_first_round_is_offered_no_write(monkeypatch, app_state, question):
    """Qwen2.5-3B, unforced: "What tags and what categories am I using?"
    called `tag_note` first; the word "tags" had cued the tag group."""
    rounds = _rounds(monkeypatch, question)
    first, forced = rounds[0]
    assert not forced
    assert not agent._WRITE_TOOLS & set(first), (question, first)
    assert {"search_notes", "list_tags"} <= set(first)


def test_a_question_that_becomes_a_job_gets_its_writes_after_reading(monkeypatch, app_state):
    rounds = _rounds(monkeypatch, "Which note is about my dentist? Pin it")
    assert "pin_note" not in rounds[0][0]
    assert "pin_note" in rounds[1][0]


def test_a_request_said_as_a_question_keeps_its_writes(monkeypatch, app_state):
    first, forced = _rounds(monkeypatch, "can you pin my dentist note?")[0]
    assert not forced
    assert "pin_note" in first


def test_a_large_model_s_first_round_is_not_narrowed(monkeypatch, app_state):
    for question in ("What tags and what categories am I using?", "Pin my dentist note"):
        rounds = _rounds(monkeypatch, question, model="qwen3:14b")
        assert rounds[0][0] == rounds[1][0], question
        assert not rounds[0][1]


def test_filing_a_note_under_a_category_that_exists_is_not_offered_a_new_category(monkeypatch, app_state, session):
    """Qwen2.5-3B, forced: "File the dentist note under Health" opened once
    with `create_category`. Where "Health" is already a category the round
    offers the note edit, not the category's creation."""
    from tessellate.entry import manager

    manager.get_or_create_category(session, "Health")
    session.commit()
    first, forced = _rounds(monkeypatch, "File the dentist note under Health", session=session)[0]
    assert forced
    assert "edit_note" in first and "search_notes" in first
    assert "create_category" not in first, first


def test_filing_under_a_category_that_exists_is_offered_no_category_tool(monkeypatch, app_state, session):
    """Qwen2.5-3B, forced, 2026-10-05 (`harness_probe.py`): the same request
    opened once with `rename_category {"old": "note 2", "new": "Health"}`.
    Filing is an edit of the note; no tool that reshapes the category tree
    is the right first call when the category is already there."""
    from tessellate.entry import manager

    manager.get_or_create_category(session, "Health")
    session.commit()
    first, forced = _rounds(monkeypatch, "File the dentist note under Health", session=session)[0]
    assert forced and "edit_note" in first
    assert not {"create_category", "rename_category", "merge_categories", "delete_category"} & set(first), first


def test_filing_under_a_category_that_does_not_exist_may_still_create_it(monkeypatch, app_state, session):
    first, forced = _rounds(monkeypatch, "File the dentist note under Health", session=session)[0]
    assert forced and "edit_note" in first
    assert "create_category" in first, first


def test_the_category_is_offered_again_on_the_round_after(monkeypatch, app_state, session):
    from tessellate.entry import manager

    manager.get_or_create_category(session, "Health")
    session.commit()
    second, forced = _rounds(monkeypatch, "File the dentist note under Health", session=session)[1]
    assert not forced and "create_category" in second
