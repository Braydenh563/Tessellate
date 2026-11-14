"""CHAT_PLAN Phase 6, the deterministic engine (Brief 39): the executable spec.

Strict-xfail until an Opus session builds each step (the contract of
tests/test_events.py and tests/test_learned_spec.py). Every test here fails
today, for the reason in its marker; when a step lands, its tests XPASS, which
strict mode turns into a failure, and the session removes that marker, and
only that marker, once the test passes on its own.

Modules that do not exist yet (`ai.factgraph`, `ai.realise`, `ai.commands`)
are imported inside the test body, so the test xfails with ImportError today
and the file always collects. Names below are the contract; a session that
needs a different shape changes the test in the same commit, with the reason.
Shared notes live in tests/fixtures/composer/phase6_seed.json (today is
2026-10-06, a Tuesday).
"""

from __future__ import annotations

import json
from datetime import date, datetime
from pathlib import Path

import pytest

from tessellate.ai import composer
from tessellate.ai import composer_smalltalk

SEED = json.loads((Path(__file__).parent / "fixtures" / "composer" / "phase6_seed.json").read_text(encoding="utf-8"))
TODAY = date.fromisoformat(SEED["today"])
NOW = datetime(TODAY.year, TODAY.month, TODAY.day, 12, 0)
NOTES = SEED["notes"]


def _spec(reason: str):
    return pytest.mark.xfail(strict=True, reason=reason)


def _notes(*ids: int) -> list[dict]:
    return [n for n in NOTES if n["id"] in ids]


def _ask(question: str, notes=None, **kwargs) -> dict:
    return composer.compose(question, NOTES if notes is None else notes, today=TODAY, **kwargs)


def _text(result: dict) -> str:
    return str(result.get("text") or "")


# --- First tests for Brief 39 ---------------------------------------------------


def test_arithmetic_answers_a_computed_sentence():
    result = _ask("what is 12 * 7")
    assert "84" in _text(result)
    assert "Nothing in the notes" not in _text(result)
    assert any(p[0] == "computed" for p in result["parts"])


def test_the_time_question_answers_a_computed_sentence():
    result = _ask("what time is it")
    assert "Nothing in the notes" not in _text(result)
    assert any(p[0] == "computed" for p in result["parts"])


@pytest.mark.parametrize("question", ["what do I need to buy", "how to cook rice"])
def test_to_word_is_not_translate(question):
    assert composer.classify(question) != "translate"


def test_summarise_returns_a_brief_without_raising():
    result = _ask("summarise my gym notes", _notes(1, 2))
    assert "Nothing in the notes" not in _text(result)
    assert result["grounding"]


def test_last_friday_is_in_the_past():
    from tessellate.ai import when

    got = when.resolve("last friday", NOW)
    assert got is not None and got < NOW
    assert got.date() == date(2026, 10, 2)


@pytest.mark.parametrize("phrase", ["since March", "the week before last"])
def test_unread_time_phrases_resolve_to_windows(phrase):
    from tessellate.ai import when

    window = when.window(phrase, NOW)
    assert window is not None
    start, end = window
    assert start < end <= NOW
    if phrase == "since March":
        assert start.date() == date(2026, 3, 1)
    else:
        assert (start.date(), end.date()) == (date(2026, 9, 21), date(2026, 9, 27))


_HISTORY = [{"question": "What did I do at the gym?", "answer": "You wrote **Gym log**. Next: **Gym plan**."}]


@pytest.mark.parametrize(
    ("question", "kind"),
    [
        ("and last week?", "window"),
        ("what about running?", "subject"),
        ("and Sam?", "entity"),
        ("why?", "why"),
        ("shorter", "length"),
        ("no, the gym one", "correction"),
    ],
)
def test_follow_on_resolves_the_terse_turns(question, kind):
    follow = composer.follow_on(question, _HISTORY)
    assert follow is not None
    assert follow.kind == kind
    assert follow.previous == "What did I do at the gym?"


# --- Decision 30: the fact layer --------------------------------------------------

_FACT_NOTE = {
    "id": 900,
    "created_at": "2026-10-01",
    "content": (
        "I met Sam on Friday at the Lakeside cafe.\n"
        "I ran 5 km in 28 minutes.\n"
        "The budget is $1,200 for the listing.\n"
        "Launch is on 14 November 2026.\n"
        "- [x] Book flights\n"
        "We decided to go with the strength programme.\n"
        "I prefer mornings.\n"
        "Why does sync drop edits?\n"
        'Sam wrote: "I am not sure we should ship it."\n'
    ),
}


def test_facts_yield_the_listed_kinds_with_spans():
    from tessellate.ai import factgraph

    facts = factgraph.facts(_FACT_NOTE)
    content = _FACT_NOTE["content"]
    kinds = {f.kind for f in facts}
    assert {"event", "quantity", "money", "date", "check_item", "decision", "preference", "question", "entity"} <= kinds
    for f in facts:
        assert 0 <= f.start < f.end <= len(content)
        assert content[f.start : f.end] == f.text
    money = next(f for f in facts if f.kind == "money")
    assert (money.attrs["value"], money.attrs["currency"]) == (1200, "USD")
    check = next(f for f in facts if f.kind == "check_item")
    assert check.attrs["done"] is True
    sentence = "I am not sure we should ship it."
    assert any(f.mode == "quoted" and sentence in f.text for f in facts)
    assert not any(f.kind == "event" and f.mode == "quoted" for f in facts)


# --- Decision 31: the query plan ----------------------------------------------------


def test_plan_reads_recall_by_time_and_a_window():
    plan = composer.plan("what did I do last week", today=TODAY)
    assert plan.kind == "recall"
    assert (plan.window[0], plan.window[1]) == (date(2026, 9, 28), date(2026, 10, 4))


def test_plan_reads_a_tag_constraint():
    plan = composer.plan("notes tagged gym", today=TODAY)
    assert plan.constraints["tags"] == ["gym"]


def test_plan_reads_a_source_kind():
    plan = composer.plan("which boards mention Harbor", today=TODAY)
    assert plan.source_kind == "board"
    assert "harbor" in [t.lower() for t in plan.terms]


# --- Decision 32: insights ----------------------------------------------------------


def _measures(result: dict) -> list[str]:
    return [p[1] for p in result["parts"] if p[0] == "measure"]


def test_an_insight_closes_a_broad_answer_over_four_notes_in_five_weeks():
    result = _ask("tell me about golf", _notes(3, 4, 5, 6))
    insight = [m for m in _measures(result) if "hobby forming" in m or "keeps coming up" in m]
    assert insight, _measures(result)
    #: The count is said once (decision 52): by the lead, or by the line.
    assert "four" in _measures(result) or "four times" in insight[0]


def test_no_insight_on_two_notes():
    # A negative control first: the rule must fire on four notes, or "no
    # insight on two" would pass vacuously before the rule exists.
    hedged = ("hobby forming", "keeps coming up")
    assert [m for m in _measures(_ask("tell me about golf", _notes(3, 4, 5, 6))) if any(h in m for h in hedged)]
    result = _ask("tell me about golf", _notes(3, 4))
    assert not [m for m in _measures(result) if any(h in m for h in hedged)]


# Owner decided 2026-11-12 (L783): keep all six insight rules. One spec case each
# (the rules' fixed phrases and thresholds, a fixed TODAY); no behaviour change.


def _day_note(i: int, content: str, day: str) -> dict:
    return {"id": i, "content": content, "created_at": day, "tags": []}


def test_insight_rule_streak_needs_three_consecutive_weeks_ending_now():
    from tessellate.ai import insights

    weekly = [_day_note(i, "# Run\n\nA run by the river.", d) for i, d in ((1, "2026-09-21"), (2, "2026-09-28"), (3, "2026-10-05"))]
    assert insights.streak("run", weekly, TODAY).text == "You have written about run 3 weeks running."
    assert insights.streak("run", weekly[:2], TODAY) is None


def test_insight_rule_drift_is_a_plan_over_thirty_days_old_with_no_later_note():
    from tessellate.ai import insights

    plan = _day_note(1, "# Fence\n\nI plan to repaint the shed fence.", "2026-08-01")
    found = insights.drift([plan], TODAY)
    assert [i.rule for i in found] == ["drift"] and found[0].slots["since"] == "1 August"
    assert not insights.drift([_day_note(1, plan["content"], "2026-09-30")], TODAY)


def test_insight_rule_contrast_is_a_preference_then_the_other_way():
    from tessellate.ai import insights

    notes = [_day_note(1, "# Desk\n\nI like the standing desk.", "2026-08-01"),
             _day_note(2, "# Desk again\n\nI don't like the standing desk any more.", "2026-09-30")]
    found = insights.contrast(notes, TODAY)
    assert [i.rule for i in found] == ["contrast"] and found[0].slots["first"] == "1 August" and found[0].slots["last"] == "30 September"
    assert not insights.contrast(notes[:1], TODAY)


def test_insight_rule_load_is_a_week_with_twice_the_median_and_four_notes():
    from tessellate.ai import insights

    quiet = [_day_note(i, "# Day\n\nA quiet day.", d) for i, d in ((1, "2026-09-07"), (2, "2026-09-14"), (3, "2026-09-21"))]
    busy = [_day_note(10 + i, "# Busy\n\nA busy day.", "2026-09-29") for i in range(5)]
    found = insights.load(quiet + busy, TODAY)
    assert found.rule == "load" and found.slots["count"] == 5 and found.slots["usual"] == 1
    assert insights.load(quiet + busy[:3], TODAY) is None  # under four notes: silence


def test_insight_rule_time_of_day_needs_three_notes_that_say_after_work():
    from tessellate.ai import insights

    after = [_day_note(i, "# Golf\n\nGolf after work.", d) for i, d in ((1, "2026-09-05"), (2, "2026-09-15"), (3, "2026-09-25"))]
    assert ", three of them after work" in insights.recurrence("golf", after, TODAY).text
    mixed = [after[0], after[1], _day_note(3, "# Golf\n\nGolf on Saturday morning.", "2026-09-25")]
    assert "after work" not in insights.recurrence("golf", mixed, TODAY).text


def test_every_insight_template_slot_is_typed_and_fired_slots_hold_their_kind():
    import string

    from tessellate.ai import composer_tables, insights

    for rule, template in composer_tables.INSIGHT_TEMPLATES.items():
        names = {name for _lit, name, _spec, _conv in string.Formatter().parse(template) if name}
        assert names and names <= set(composer_tables.INSIGHT_SLOTS), rule
    found = insights.streak("run", [_day_note(i, "# Run\n\nA run.", d) for i, d in ((1, "2026-09-21"), (2, "2026-09-28"), (3, "2026-10-05"))], TODAY)
    assert isinstance(found.slots["weeks"], int) and composer_tables.INSIGHT_SLOTS["weeks"] == "count"


# --- Decision 33: the realiser --------------------------------------------------------


@pytest.mark.parametrize(
    ("said", "shifted"),
    [
        ("I am going", "you are going"),
        ("I was late", "you were late"),
        ("I've booked it", "you have booked it"),
        ("my notes", "your notes"),
        ("Sam and I met", "you and Sam met"),
        ("am I late", "are you late"),
    ],
)
def test_shift_person_pairs(said, shifted):
    from tessellate.ai import realise

    assert realise.shift_person(said) == shifted


def test_no_shift_inside_a_quoted_fact():
    from tessellate.ai import realise

    assert realise.shift_person("I am sure", quoted=True) == "I am sure"


@pytest.mark.parametrize(
    ("day", "said"),
    [
        (date(2026, 10, 6), "today"),
        (date(2026, 10, 5), "yesterday"),
        (date(2026, 10, 2), "on Friday"),
        (date(2026, 9, 29), "last week"),
        (date(2026, 9, 22), "two weeks ago"),
        (date(2026, 3, 3), "on 3 March"),
        (date(2025, 3, 3), "on 3 March 2025"),
    ],
)
def test_relative_day(day, said):
    from tessellate.ai import realise

    assert realise.relative_day(day, TODAY) == said


@pytest.mark.parametrize(
    ("text", "due", "said"),
    [
        ("you plan to go on Friday", date(2026, 10, 2), "you planned to go on Friday"),
        ("you are planning to go", date(2026, 10, 2), "you were planning to go"),
        ("you're going to call Sam", date(2026, 10, 5), "you were going to call Sam"),
        ("you want to leave", date(2026, 10, 1), "you wanted to leave"),
        ("you plan to go on Friday", date(2026, 10, 9), "you plan to go on Friday"),
        ("you plan to go today", date(2026, 10, 6), "you plan to go today"),
        ("you plan to go", None, "you plan to go"),
    ],
)
def test_past_plan_table(text, due, said):
    from tessellate.ai import realise

    assert realise.past_plan(text, due, TODAY) == said


@pytest.mark.parametrize(
    ("n", "noun", "article", "said"),
    [
        (1, "note", False, "one note"),
        (2, "note", False, "two notes"),
        (1, "day", True, "a day"),
        (1, "item", True, "an item"),
        (3, "entry", False, "three entries"),
        (2, "day", False, "two days"),
        (2, "person", False, "two people"),
        (2, "key", False, "two keys"),
        (13, "note", False, "13 notes"),
    ],
)
def test_count_noun_table(n, noun, article, said):
    from tessellate.ai import realise

    assert realise.count_noun(n, noun, article=article) == said


@pytest.mark.parametrize(
    ("items", "said"),
    [
        ([], ""),
        (["bread"], "bread"),
        (["bread", "salt"], "bread and salt"),
        (["bread", "salt", "fish"], "bread, salt and fish"),
        (["bread", "salt", "fish and chips"], "bread, salt, and fish and chips"),
        (["bread", "", "fish"], "bread and fish"),
    ],
)
def test_join_items_table(items, said):
    from tessellate.ai import realise

    assert realise.join_items(items) == said


@pytest.mark.parametrize(
    ("text", "said"),
    [
        ("The dentist is on Friday", "the dentist is on Friday"),
        ("It rained", "it rained"),
        ("Sara called", "Sara called"),
        ("I am late", "I am late"),
        ("Friday is the dentist", "Friday is the dentist"),
        ("", ""),
    ],
)
def test_after_comma_table(text, said):
    from tessellate.ai import realise

    assert realise.after_comma(text) == said


@pytest.mark.parametrize(
    ("title", "limit", "said"),
    [
        ("Buy milk", 40, "Buy milk"),
        ("Buy   milk", 40, "Buy milk"),
        ("Dentist appointment on 4 November at the clinic", 30, "Dentist appointment on 4\u2026"),
        ("Remember to bring the folder with the old receipts", 24, "Remember to bring the\u2026"),
    ],
)
def test_cut_title_table(title, limit, said):
    from tessellate.ai import realise

    out = realise.cut_title(title, limit)
    assert out == said or (len(out) <= limit + 1 and out.endswith("\u2026") and title.startswith(out[:-1]))
    assert not out.removesuffix("\u2026").endswith((" the", " on", " a", " of", " at"))


# --- Decision 34: session-salted variation ----------------------------------------------


def test_ask_again_varies_the_wording_but_keeps_the_lead():
    notes = _notes(1, 2, 18)
    first = _ask("what have I done for fitness", notes, turn=1, salt="chat-a")
    again = _ask("what have I done for fitness", notes, turn=2, salt="chat-a")
    assert _text(first) != _text(again)
    #: The lead row, not the first "quote" part: a lead said back to its
    #: writer ("you went", decision 33) is a "shifted" part, and whether an
    #: opener promised verbatim words decides which; the sentence is the same.
    lead = lambda r: (r["grounding"][0]["note_id"], r["grounding"][0]["start"])  # noqa: E731
    assert lead(first) == lead(again)


# --- Decision 35: dialogue state --------------------------------------------------------


def test_dialogue_does_not_quote_a_note_twice():
    dialogue = composer.Dialogue()
    seen: list[tuple] = []
    for question in ("tell me about golf", "tell me more", "tell me more"):
        result = _ask(question, _notes(3, 4, 5, 6), dialogue=dialogue)
        quotes = [p[1] for p in result["parts"] if p[0] == "quote"]
        assert not set(quotes) & {q for q in seen}, (question, quotes)
        seen.extend(quotes)
    assert dialogue.quoted_ids


def test_a_correction_reranks():
    dialogue = composer.Dialogue()
    _ask("what did I do on Monday", _notes(1, 10, 18), dialogue=dialogue)
    fixed = _ask("no, the gym one", _notes(1, 10, 18), dialogue=dialogue)
    #: Rows name their note as `note_id` (every grounding row in the app does).
    assert fixed["grounding"][0]["note_id"] == 1


# --- Decision 36: identity --------------------------------------------------------------


def test_who_are_you_answers_as_atlas():
    reply = composer_smalltalk.social("who are you", intent="about_app")
    assert "Atlas" in reply


def test_a_how_to_without_notes_uses_the_help_topics():
    result = _ask("how do I add a reminder to a note", [], voice="help")
    assert "Nothing in the notes" not in _text(result)
    assert any(p[0] == "help" for p in result["parts"])


# --- Decision 37: sources of every kind ---------------------------------------------------


def test_a_board_source_is_cited_as_a_board():
    result = _ask("which boards mention Harbor", _notes(7, 8))
    cited = {g["note_id"]: g for g in result["grounding"]}
    assert cited[8]["kind"] == "board"


def test_a_picture_caption_is_quoted_as_content():
    result = _ask("what does the shed roof look like", _notes(14, 15))
    assert any(p[0] == "picture" and "wet wooden roof" in p[1] for p in result["parts"])
    #: Rows name their source as `note_id` (with `kind`), as every row does.
    assert any(g["note_id"] == 15 for g in result["grounding"])


# --- Decisions 38 and 42: acts -------------------------------------------------------------


def test_parse_a_reminder_command():
    from tessellate.ai import commands

    cmd = commands.parse("remind me to call Sam on Friday", NOW)
    assert (cmd.verb, cmd.object) == ("remind", "call Sam")
    assert cmd.when.date() == date(2026, 10, 9)
    assert cmd.confirm is True  # every act waits (owner, 2026-11-10)


def test_delete_requires_confirmation():
    from tessellate.ai import commands

    cmd = commands.parse("delete the gym note", NOW)
    assert cmd.verb == "delete" and cmd.confirm is True


def test_archive_is_not_a_verb():
    from tessellate.ai import commands

    assert "archive" not in commands.VERBS
    assert commands.parse("archive the gym note", NOW) is None


_VERB_SENTENCES = {
    "remind": "remind me to call Sam on Friday",
    "complete": "complete the gym task",
    "cancel": "cancel the dentist reminder",
    "snooze": "snooze the call reminder until tomorrow",
    "tag": "tag the gym note with fitness",
    "untag": "untag fitness from the gym note",
    "file": "file the gym note under Fitness",
    "rename": "rename the gym note to Gym plan",
    "restore": "restore the gym note",
    "pin": "pin the gym note",
    "unpin": "unpin the gym note",
    "link": "link the gym note to the diet note",
    "unlink": "unlink the gym note from the diet note",
    "delete": "delete the gym note",
    "create": "create a note called Ideas",
    "summarise": "summarise the gym note",
    "find": "find notes about gym",
    "open": "open the gym note",
}
_READ_ONLY = {"summarise", "find", "open"}


def test_decision_38_every_verb_is_read_and_every_write_waits_for_confirm():
    """L728: the verbs, kept as decided; a write waits on a confirm card, a read does not."""
    from tessellate.ai import commands

    assert set(_VERB_SENTENCES) == set(commands.VERBS) - {"add"}

    for verb, sentence in _VERB_SENTENCES.items():
        cmd = commands.parse(sentence, NOW)
        assert cmd is not None and cmd.verb == verb, sentence
        assert cmd.confirm is (verb not in _READ_ONLY), sentence


def test_decision_38_every_write_act_has_an_undo():
    from tessellate.ai import acts

    writes = [a for a in acts.ACTS.values() if a.writes]
    assert len(writes) >= 15
    assert all(a.inverse for a in writes), [a.intent for a in writes if not a.inverse]


def test_decision_38_the_web_search_tool_is_offered_only_with_web_on(monkeypatch):
    from tessellate.ai.tools import tool_sets
    from tessellate.core import deps

    class _Cfg:
        def __init__(self, on):
            self.on = on

        def get_preference(self, key, default=None):
            return self.on if key == "web_search_enabled" else default

    monkeypatch.setattr(deps, "peek_config", lambda: _Cfg(False))
    assert not tool_sets.tool_enabled("web_search") and not tool_sets.tool_enabled("read_url")
    monkeypatch.setattr(deps, "peek_config", lambda: _Cfg(True))
    assert tool_sets.tool_enabled("web_search") and tool_sets.tool_enabled("read_url")


# --- Decisions 41 and 43: utilities -----------------------------------------------------------


def test_unit_conversion_is_computed():
    result = _ask("how many km is 5 miles")
    computed = [p[1] for p in result["parts"] if p[0] == "computed"]
    assert computed and "8.0" in computed[0]


def test_currency_answer_names_the_rate_date():
    result = _ask("how much is 100 dollars in euros")
    computed = [p[1] for p in result["parts"] if p[0] == "computed"]
    assert computed and "at the rates from" in computed[0]


# --- Decision 45: ambiguity ----------------------------------------------------------------------


def test_an_ambiguous_question_lists_numbered_readings():
    meetings = [n for n in NOTES if "meeting" in n["content"].lower()]
    assert len(meetings) == 2
    result = _ask("the meeting", meetings)
    readings = result.get("readings")
    assert readings and [r["n"] for r in readings] == [1, 2]
    assert {r["note_id"] for r in readings} == {n["id"] for n in meetings}
