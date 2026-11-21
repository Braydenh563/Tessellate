"""The validators (CHAT_PLAN decisions 52 to 54, Brief 67): the maxims lint
over the eval answers is 0, each rule catches the shape it names, the
computed-sentence rule holds for every utility, and a model's answer is
checked like the engine's."""

from __future__ import annotations

import pytest

from tessellate.ai import composer, validate
from tests import _composer_eval as E


@pytest.fixture(scope="module")
def eval_rows():
    data = E.load()
    notes = data["notes"] + E.untitled_notes(E.load_voice(), E.today(data))
    return [(row, notes) for row in E.run() + E.run_voice()]


def test_the_maxims_lint_is_zero_over_the_eval_answers(eval_rows):
    """115 answers (the 25 showcase and the 90 voice questions): measured 17
    findings before Brief 67 (12 values said twice, 4 capitals after a comma
    that were titles, 1 number in a joining phrase), 0 after."""
    found = [
        (row["question"], f.as_dict())
        for row, notes in eval_rows
        for f in validate.maxims(row["result"], row["question"], notes) + validate.computed_rule(row["result"], row["question"])
    ]
    assert len(eval_rows) == 115
    assert found == []


def _answer(parts, shape="what", grounding=None):
    return {"parts": parts, "text": "".join(str(p[1]) for p in parts), "shape": shape, "grounding": grounding or []}


@pytest.mark.parametrize(
    ("parts", "maxim", "rule"),
    [
        ([("quote", "The boiler is 12 years old.", 1), ("template", " "), ("quote", "The boiler is 12 years old.", 1)], "quantity", "quote said twice"),
        ([("measure", "three"), ("template", " notes. "), ("measure", "You wrote it 3 times.")], "quantity", "measured value said twice"),
        ([("template", "Two of them: "), ("quote", "Fine.", 1)], "quality", "number in the app's own words"),
        ([("template", "Separately, "), ("quote", "The hills are steep.", 2)], "manner", "capital after a joining comma"),
        ([("template", "Great news! "), ("quote", "Done.", 1)], "manner", "exclamation or Oops"),
        ([("template", "Here  it is: "), ("quote", "Done.", 1)], "manner", "doubled space or stop"),
    ],
)
def test_each_maxim_catches_its_shape(parts, maxim, rule):
    rows = [{"note_id": 1}, {"note_id": 2}]
    found = {(f.maxim, f.rule) for f in validate.maxims(_answer(parts, grounding=rows))}
    assert (maxim, rule) in found


def test_relation_catches_a_quote_from_a_note_not_cited():
    found = validate.maxims(_answer([("quote", "The roof leaks.", 7)], grounding=[{"note_id": 1}]))
    assert [(f.maxim, f.rule) for f in found] == [("relation", "quote with no grounding row")]


def test_a_title_cut_through_a_word_is_caught():
    notes = [{"id": 3, "content": "# Harbor onboarding rewrite\n\nbody"}]
    cut = _answer([("title", "Harbor onboard…", 3)])
    whole = _answer([("title", "Harbor…", 3)])
    assert [f.rule for f in validate.maxims(cut, notes=notes)] == ["title cut through a word"]
    assert validate.maxims(whole, notes=notes) == []


def test_a_title_after_a_comma_keeps_its_capital():
    assert validate.maxims(_answer([("template", "Separately, "), ("title", "The Mom Test", 1)], grounding=[{"note_id": 1}])) == []
    assert validate.maxims(_answer([("template", "Also, "), ("quote", "The Mom Test is next.", 1)], grounding=[{"note_id": 1}])) == []


@pytest.mark.parametrize(
    "question",
    ["what time is it", "what year is it", "what is today", "flip a coin", "roll a die", "what is 12 * 7",
     "convert 5 miles to km", "how many days until christmas", "pick a number from 1 to 10", "100 usd in eur"],
)
def test_every_utility_answer_says_how_it_read_the_question(question):
    result = composer.compose(question, [])
    assert result["shape"] == "utility", question
    assert validate.computed_rule(result, question) == []


def test_a_computed_sentence_is_never_mixed_into_a_claim_about_the_notes():
    mixed = _answer([("quote", "Paid 40.", 1), ("computed", " 40 * 2 is 80.")])
    assert [f.rule for f in validate.computed_rule(mixed)] == ["computed sentence in a claim about the notes"]


def test_a_model_answer_with_an_unsourced_number_is_caught():
    notes = ["The boiler was serviced on 3 March for 120 pounds."]
    good = validate.check_model_answer("The boiler was serviced in March for 120 pounds.", ["when was the boiler serviced", *notes])
    bad = validate.check_model_answer("The boiler was serviced in March for 180 pounds.", ["when was the boiler serviced", *notes])
    assert good["ok"] and good["unbacked"] == []
    assert not bad["ok"] and bad["unbacked"] == ["180"]


def test_slot_completeness_names_what_a_reading_left_empty():
    assert validate.slots_missing({"text": "call Sam", "due_at": None}, ("text", "due_at")) == ["due_at"]
    assert validate.slots_missing({"text": "call Sam", "due_at": "2026-10-12"}, ("text", "due_at")) == []


class _Says:
    """A provider whose model answers with one fixed sentence."""

    def __init__(self, fake, text):
        self.fake, self.text = fake, text

    def __getattr__(self, name):
        return getattr(self.fake, name)

    def chat_stream(self, model, messages, mode=None):  # noqa: ANN001, ARG002
        yield {"content_delta": self.text}


@pytest.mark.parametrize(("said", "flagged"), [("Harbor ships on the 14th of next month.", False), ("Harbor ships on the 28th of next month.", True)])
def test_the_model_path_runs_the_same_validators(ai_client, fake_ollama, session, monkeypatch, said, flagged):
    """Decision 53 on the route: the model's plain answer is checked against
    the notes it was given; a number in none of them is said under it."""
    from datetime import datetime, timezone

    from tessellate.api import routes_chat
    from tessellate.core import deps
    from tessellate.entry import manager
    from tests.test_composer_route_688 import _ask

    manager.create_entry(session, "# Harbor launch plan\n\nShip Harbor to the public on the 14th of next month.")
    session.commit()
    monkeypatch.setattr(deps, "get_ollama", lambda: _Says(fake_ollama, said))
    #: The route passes `user_now(...)` as one of the validator's sources, so
    #: a clock string whose minute matches the answer's number ("16:28" and
    #: the model's unsupported "28th") would falsely back it and the test
    #: would flake. Frozen to a minute that matches no number in the answer.
    frozen = datetime(2026, 10, 13, 16, 27, tzinfo=timezone.utc)
    monkeypatch.setattr(routes_chat, "user_now", lambda _config: frozen)
    out = _ask(ai_client, "When does Harbor ship?", use_tools=False, answer_from="ai")
    assert ("Heads up" in out["text"]) is flagged, out["text"]
    checks = [c for e in out.get("grounding", []) for c in e.get("checks", [])]
    assert bool(checks) is flagged


def test_every_broad_answer_over_several_notes_opens_with_the_topic_and_the_count(eval_rows):
    """INBOX 729: "it just uses one word sentence joints". A broad answer that
    quotes two or more notes says what it is about and how many notes before
    the first quote (the mention lead, or the summary clause when no note
    holds every word asked). "What do my notes say about running?" was not
    read as broad before (its frame was taken off first)."""

    def opens_with_summary(result):
        before = []
        for part in result["parts"]:
            if part[0] in ("quote", "title", "picture", "filed"):
                break
            before.append(part[0])
        return "measure" in before and "asked" in before

    broad = [row for row, _ in eval_rows if row["result"].get("broad") and len({g["note_id"] for g in row["result"]["grounding"]}) >= 2]
    assert len(broad) >= 10
    assert [row["question"] for row in broad if not opens_with_summary(row["result"])] == []
    assert "What do my notes say about running?" in {row["question"] for row in broad}
