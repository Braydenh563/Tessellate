"""Time travel's model half (WORLD_CLASS_PLAN I5, LEDGER L-world-class-26):
the model's judgement over then-and-now claim pairs, with today's word rule
as the fallback when no model is on or its reply is unusable. Fake
transport only; the dates are a fixed clock.
"""

from __future__ import annotations

import json
from datetime import datetime, timedelta, timezone

from tessellate.ai import timetravel
from tessellate.core.database import EntryRevision
from tessellate.entry import manager

T0 = datetime(2026, 3, 1, 9, 0, tzinfo=timezone.utc)

THEN = "The batch size should stay at 32. We train on the March dataset only. Evaluation runs every night."
NOW = "The batch size is 64 after the memory fix. Evaluation runs every night. We add a warmup of 500 steps."


def _note_with_history(session, texts, days):
    entry = manager.create_entry(session, texts[-1], "Work", [])
    entry.created_at = T0 + timedelta(days=days[0])
    for before, edited_on in zip(texts[:-1], days[1:]):
        session.add(EntryRevision(entry_id=entry.id, content=before, tags="[]", created_at=T0 + timedelta(days=edited_on)))
    session.commit()
    return entry


def _judge(verdicts):
    """A judge that answers in order and records what it was shown."""
    seen = []

    def judge(pairs):
        seen.append(list(pairs))
        return verdicts[: len(pairs)]

    judge.seen = seen
    return judge


def test_without_a_model_the_word_rule_stands():
    out = timetravel.then_and_now(THEN, NOW)
    assert sorted(c["kind"] for c in out["changed"]) == ["dropped", "new", "revised"]
    assert out["judged_by"] is None
    assert all("judgement" not in c for c in out["changed"])


def test_the_model_marks_a_pair_that_says_the_opposite():
    judge = _judge(["contradicts"])
    out = timetravel.then_and_now(THEN, NOW, judge=judge, judged_by="fake-model")
    revised = [c for c in out["changed"] if c["kind"] == "revised"]
    assert len(revised) == 1 and revised[0]["judgement"] == "contradicts"
    assert out["judged_by"] == "fake-model"
    assert judge.seen and "32" in judge.seen[0][0][0] and "64" in judge.seen[0][0][1]


def test_the_model_can_say_two_wordings_are_the_same_claim():
    then = "Ship the release on Friday afternoon."
    now = "The release goes out Friday after lunch."
    words_only = timetravel.then_and_now(then, now)
    assert [c["kind"] for c in words_only["changed"]] == ["revised"]
    out = timetravel.then_and_now(then, now, judge=_judge(["same"]), judged_by="fake-model")
    assert out["changed"] == []


def test_the_model_can_pair_what_the_words_missed():
    """A pair sharing one word is below the word rule's bar (dropped plus
    new); the model reads it as one claim changed."""
    then = "Meetings happen on Mondays with the whole design team."
    now = "The design review moves to Thursdays for the leads only."
    assert sorted(c["kind"] for c in timetravel.then_and_now(then, now)["changed"]) == ["dropped", "new"]
    out = timetravel.then_and_now(then, now, judge=_judge(["changed"]), judged_by="fake-model")
    assert [(c["kind"], c["judgement"]) for c in out["changed"]] == [("revised", "changed")]


def test_an_unusable_reply_falls_back_to_the_word_rule():
    out = timetravel.then_and_now(THEN, NOW, judge=lambda pairs: None, judged_by="fake-model")
    assert sorted(c["kind"] for c in out["changed"]) == ["dropped", "new", "revised"]
    assert out["judged_by"] is None


def test_the_model_sees_a_bounded_number_of_pairs():
    then = " ".join(f"Item {k} weighs {k} kilos in the store." for k in range(40))
    now = " ".join(f"Item {k} weighs {k + 1} kilos in the store." for k in range(40))
    judge = _judge(["changed"] * 100)
    timetravel.then_and_now(then, now, judge=judge, judged_by="fake-model")
    assert len(judge.seen[0]) <= timetravel.JUDGE_PAIRS_MAX
    assert all(len(a) <= timetravel.JUDGE_CLAIM_CHARS and len(b) <= timetravel.JUDGE_CLAIM_CHARS for a, b in judge.seen[0])


def test_the_judge_prompt_is_budgeted():
    assert len(timetravel.JUDGE_PROMPT) <= timetravel.JUDGE_PROMPT_CHARS <= 500


def test_the_reply_is_read_leniently_and_by_number():
    assert timetravel.parse_judgement('```json\n{"1": "same", "2": "Contradicts"}\n```', 2) == ["same", "contradicts"]
    assert timetravel.parse_judgement('{"1": "maybe"}', 1) == [None]
    assert timetravel.parse_judgement("no idea", 1) is None


def test_the_route_asks_the_running_model(ai_client, fake_ollama, session):
    entry = _note_with_history(session, [THEN, NOW], [0, 30])
    fake_ollama.librarian_reply = json.dumps({"1": "contradicts"})
    body = ai_client.get(f"/entries/{entry.id}/then-and-now", params={"as_of": (T0 + timedelta(days=10)).date().isoformat()}).json()
    revised = next(c for c in body["changed"] if c["kind"] == "revised")
    assert revised["judgement"] == "contradicts"
    assert body["judged_by"]
    assert any(timetravel.JUDGE_PROMPT in m[0]["content"] for m in fake_ollama.chat_calls)


def test_the_route_with_no_model_keeps_the_word_rule(client, session):
    entry = _note_with_history(session, [THEN, NOW], [0, 30])
    body = client.post(f"/entries/{entry.id}/then-and-now", json={"then": THEN}).json()
    assert sorted(c["kind"] for c in body["changed"]) == ["dropped", "new", "revised"]
    assert body["judged_by"] is None
