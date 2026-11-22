"""Time travel's open half (WORLD_CLASS_PLAN I5 and H8, LEDGER
L-world-class-26): the model's judgement over then-and-now claim pairs, with
today's word rule as the fallback when no model is on or its reply is
unusable; as-of retrieval by the meaning of past versions; an as-of answer's
cards grouped by month. Fake transport only; the dates are a fixed clock.
"""

from __future__ import annotations

import json
import os
import re
import shutil
import subprocess
import time
from datetime import datetime, timedelta, timezone

import pytest

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


# --- as-of retrieval by the meaning of past texts ------------------------------------


def _sports_then_shopping_now(session):
    """Two notes whose subject changed after day 10: what each said then is
    the other's subject now, so a then-text's own vector is the only way to
    tell them apart by meaning."""
    a = _note_with_history(session, ["We ran the 100m sprint at the carnival.", "Buy milk and eggs today."], [0, 30])
    b = _note_with_history(session, ["Milk, eggs and bread for the week.", "The athletics carnival is next week."], [0, 30])
    return a, b


def test_without_embeddings_a_question_sharing_no_word_keeps_the_engine_order(session):
    a, b = _sports_then_shopping_now(session)
    picked = timetravel.rewind(session, "shopping list", T0 + timedelta(days=10), [a, b])
    assert [t.entry.id for t in picked] == [a.id, b.id]


def test_as_of_retrieval_reads_each_past_text_by_its_meaning(session, fake_embeddings):
    a, b = _sports_then_shopping_now(session)
    timetravel.forget_past_vectors()
    picked = timetravel.rewind(session, "shopping list", T0 + timedelta(days=10), [a, b], embeddings=fake_embeddings)
    assert [t.entry.id for t in picked] == [b.id]
    assert picked[0].text.startswith("Milk, eggs")


def test_past_vectors_are_kept_by_revision_and_bounded_per_question(session, fake_embeddings, monkeypatch):
    timetravel.forget_past_vectors()
    entries = [_note_with_history(session, [f"Milk and eggs, list {k}.", f"Sprint {k} at the carnival."], [0, 30]) for k in range(60)]
    made = []
    real = fake_embeddings.embed_many

    def counting(texts):
        made.append(len(texts))
        return real(texts)

    monkeypatch.setattr(fake_embeddings, "embed_many", counting)
    when = T0 + timedelta(days=10)
    timetravel.rewind(session, "shopping", when, entries, embeddings=fake_embeddings)
    assert made == [timetravel.EMBED_PER_QUERY]
    timetravel.rewind(session, "shopping", when, entries, embeddings=fake_embeddings)
    assert made == [timetravel.EMBED_PER_QUERY, 60 - timetravel.EMBED_PER_QUERY]
    timetravel.rewind(session, "shopping", when, entries, embeddings=fake_embeddings)
    assert len(made) == 2, "every past text is cached by its revision now"


def test_notes_edited_since_the_day_are_candidates(session):
    a, b = _sports_then_shopping_now(session)
    untouched = _note_with_history(session, ["Nothing changed here at all."], [0])
    ids = [e.id for e in timetravel.changed_since(session, T0 + timedelta(days=10))]
    assert set(ids) == {a.id, b.id} and untouched.id not in ids
    assert timetravel.changed_since(session, T0 + timedelta(days=40)) == []


def test_an_as_of_question_finds_a_note_by_what_it_said_then(ai_client, fake_embeddings, session):
    a, b = _sports_then_shopping_now(session)
    timetravel.forget_past_vectors()
    as_of = (T0 + timedelta(days=10)).date().isoformat()
    with ai_client.stream("POST", "/chat/stream", json={"question": "what was on my shopping list?", "as_of": as_of}) as r:
        events = [json.loads(line) for line in r.iter_lines() if line]
    meta = next(e for e in events if e["type"] == "meta")
    ids = [row["id"] for row in meta["raw_results"]]
    assert ids and ids[0] == b.id, meta["raw_results"]


def test_the_gate_as_of_retrieval_by_meaning_over_200_candidates_is_under_a_second(session, fake_embeddings):
    timetravel.forget_past_vectors()
    entries = [_note_with_history(session, [f"Groceries {k}: milk and eggs.", f"Race {k} at the carnival."], [0, 30]) for k in range(200)]
    started = time.perf_counter()
    picked = timetravel.rewind(session, "shopping", T0 + timedelta(days=10), entries, limit=5, embeddings=fake_embeddings)
    elapsed = time.perf_counter() - started
    assert len(picked) == 5 and all("milk" in p.text for p in picked)
    assert elapsed < 1.0, f"{elapsed:.3f}s"


# --- an as-of answer's cards by month (H8) ---------------------------------------------


def test_each_version_then_knows_when_it_was_written(session):
    entry = _note_with_history(session, ["v1 of the plan here.", "v2 of the plan here.", "v3 of the plan here."], [0, 30, 60])
    first = timetravel.text_as_of(session, entry, T0 + timedelta(days=10))
    second = timetravel.text_as_of(session, entry, T0 + timedelta(days=45))
    third = timetravel.text_as_of(session, entry, T0 + timedelta(days=90))
    assert first.since.date() == T0.date()
    assert second.since.date() == (T0 + timedelta(days=30)).date()
    assert third.since.date() == (T0 + timedelta(days=60)).date()


def test_the_answer_says_when_each_version_was_written(ai_client, session):
    entry = _note_with_history(session, ["The batch size should stay at 32.", "The batch size goes to 48.", "The batch size is 64."], [0, 30, 60])
    as_of = (T0 + timedelta(days=45)).date().isoformat()
    with ai_client.stream("POST", "/chat/stream", json={"question": "what batch size?", "as_of": as_of}) as r:
        events = [json.loads(line) for line in r.iter_lines() if line]
    meta = next(e for e in events if e["type"] == "meta")
    assert meta["as_of_written"][str(entry.id)].startswith((T0 + timedelta(days=30)).date().isoformat())


def _groups(rows, written):
    from tests._app_js import JS_DIR

    source = (JS_DIR / "ask-compose.js").read_text(encoding="utf-8")
    match = re.search(r"^askAsOf\.monthGroups = \(rows, written\) => \{.*?^\};", source, re.S | re.M)
    assert match, "askAsOf.monthGroups is gone from ask-compose.js"
    script = "const askAsOf = {};\n" + match.group(0) + f"\nprocess.stdout.write(JSON.stringify(askAsOf.monthGroups({json.dumps(rows)}, {json.dumps(written)})));"
    out = subprocess.run(["node", "-e", script], capture_output=True, text=True, check=True, env={**os.environ, "TZ": "UTC"}).stdout
    return json.loads(out)


@pytest.mark.skipif(not shutil.which("node"), reason="needs node")
def test_the_cards_are_grouped_by_month_newest_first_in_search_order():
    rows = [{"id": 1}, {"id": 2}, {"id": 3}, {"id": 4}]
    written = {"1": "2026-01-05T09:00:00+00:00", "2": "2026-03-02T09:00:00+00:00", "3": "2026-01-20T09:00:00+00:00", "4": "2026-03-30T09:00:00+00:00"}
    groups = _groups(rows, written)
    assert [g["key"] for g in groups] == ["2026-03", "2026-01"]
    assert [[r["id"] for r in g["rows"]] for g in groups] == [[2, 4], [1, 3]]
    assert "2026" in groups[0]["label"]


@pytest.mark.skipif(not shutil.which("node"), reason="needs node")
def test_a_row_with_no_date_leaves_the_list_as_the_search_ordered_it():
    assert _groups([{"id": 1}, {"id": 2}], {"1": "2026-01-05T09:00:00+00:00"}) is None
    assert _groups([{"id": 1}], None) is None


def test_the_month_heads_keep_their_rows_when_the_answer_numbers_them():
    from tests._app_js import app_js_text

    js = app_js_text()
    assert 'li.classList.contains("as-of-month")' in js and "runs.forEach(numberMatchingRecords.sortRun)" in js
    assert "askAsOf.monthHead(heads.get(entry.id))" in js
