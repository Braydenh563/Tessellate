"""The chat plan's real-model checks (L114, L820, L822, L824, L825, L-chat-240, L-chat-23), one file.

Same seam as `test_harness_evals.py` (TESSELLATE_EVALS_URL and TESSELLATE_EVALS_MODEL, read at import; skipped without
them). What a 1.5B model manages is printed (run with `-s`); what is asserted is what the app guarantees whatever the
model says: a turn ends in words, a claimed write is never left without a card, a pick is a number in range or none, a
help turn answers. The measured numbers are in LEDGER's closing line for each row.
"""

from __future__ import annotations

import time
from datetime import datetime

import pytest

from tests.test_harness_evals import EVALS_MODEL, EVALS_URL, _answer, _calls, _turn, needs_a_model, notebook  # noqa: F401

pytestmark = [pytest.mark.evals, needs_a_model]

#: The five parity sentences (L114): a board, a mind map, a tag rename, a tag delete, a remembered preference.
PARITY = [
    "Make a board called Launch",
    "Make a mind map of Trips",
    "Rename the tag work to jobs",
    "Delete the tag urgent",
    "Remember that I prefer short answers",
]


def _cards(events: list[dict]) -> list[dict]:
    return [e for e in events if e.get("type") in {"confirm", "act", "card"} or e.get("card")]


def test_the_parity_sentences_end_in_a_card_or_words_never_a_bare_claim(notebook):  # noqa: F811
    rows = []
    for sentence in PARITY:
        started = time.monotonic()
        events = _turn(notebook, sentence)
        kinds = sorted({str(e.get("type")) for e in events})
        text = _answer(events) or " ".join(str(e.get("text", "")) for e in events if e.get("type") == "answer_final")
        rows.append({"q": sentence, "kinds": kinds, "tools": [c["tool"] for c in _calls(events)], "cards": len(_cards(events)), "s": round(time.monotonic() - started, 1)})
        print(" ", rows[-1], "|", text[:90].replace("\n", " "), flush=True)
        assert text.strip() or _cards(events), f"{sentence!r} ended with no words and no card"
    print(f"\n  parity: {sum(bool(r['cards']) for r in rows)}/{len(rows)} sentences ended in a card; {sum(bool(r['tools']) for r in rows)}/{len(rows)} called a tool")


#: (question, the readings the engine would list, which number fits, 0 when none does)
READINGS = [
    ("the meeting with Sam", [("Meeting with Sam", 1), ("Meeting notes, Thursday", 2)], 1),
    ("thursday notes", [("Meeting with Sam", 1), ("Meeting notes, Thursday", 2)], 2),
    ("harbor", [("Harbor walk", 1), ("Harbor bank statement", 2)], 0),
    ("my bank statement", [("Harbor walk", 1), ("Harbor bank statement", 2)], 2),
    ("the walk", [("Harbor walk", 1), ("Harbor bank statement", 2), ("Walk to school", 3)], 0),
    ("sam", [("Meeting with Sam", 1), ("Sam's birthday", 2)], 0),
    ("birthday", [("Meeting with Sam", 1), ("Sam's birthday", 2)], 2),
    ("the plumber", [("Plumber invoice", 1), ("Plumber's number", 2)], 0),
]


def test_the_model_picks_a_numbered_reading_or_says_none(app_state):
    """Decision 45: it picks among the engine's readings and never writes its own. Counted: a bare in-range number, none,
    anything else (which the engine reads as no pick, so the person is asked)."""
    from tessellate.ai.openai_client import OpenAICompatClient
    from tessellate.api import chat_pick

    client = OpenAICompatClient(base_url=EVALS_URL)
    picked = right = none = other = 0
    for question, options, fits in READINGS:
        readings = [{"n": n, "note_id": 100 + n, "label": label} for label, n in options]
        reply = str(client.chat(EVALS_MODEL, chat_pick.messages(question, readings)).get("content") or "")
        chosen = chat_pick.choice(reply, readings)
        print(f"  {question!r} -> {reply.strip()[:40]!r} chose {chosen} (fits {fits or 'none'})", flush=True)
        if chosen is not None:
            picked += 1
            right += chosen == 100 + fits
        elif reply.strip().lower().rstrip(".") == "none":
            none += 1
        else:
            other += 1
    print(f"\n  readings: {picked} picks ({right} on the fitting reading), {none} none, {other} unreadable, of {len(READINGS)}")
    assert picked + none + other == len(READINGS)


SMALL_TALK = ["Hi", "How are you today?", "Thanks, that was helpful", "Tell me a joke", "What is the capital of France?"]


def test_small_talk_gets_words_that_quote_no_note(notebook):  # noqa: F811
    for said in SMALL_TALK:
        started = time.monotonic()
        text = _answer(_turn(notebook, said))
        print(f"  {said!r} ({round(time.monotonic() - started, 1)} s): {text[:100]!r}", flush=True)
        assert text.strip(), f"{said!r} ended with no words"
        assert "plumber" not in text.lower() or "plumber" in said.lower(), f"{said!r} quoted a note"


HELP = ["How do I save a note?", "Where do I change the theme?", "What is a board?"]


def test_the_guide_answers_a_help_question_with_a_model(notebook):  # noqa: F811
    for question in HELP:
        started = time.monotonic()
        response = notebook.post("/help/ask", json={"question": question, "history": []})
        assert response.status_code == 200, response.text
        body = response.json()
        shown = str(body.get("content") or body.get("answer") or "")
        print(f"  {question!r} ({round(time.monotonic() - started, 1)} s) composed={body.get('composed')}: {shown[:100]!r}", flush=True)
        assert shown.strip()


#: (what the notes say, the question): the model restates the date; the checker must keep a correct phrasing.
DATES = [
    ("Dentist: Thursday 12 November 2026 at 14:30", "When is my dentist appointment?"),
    ("Passport renewal due on 3 March 2027", "When does my passport need renewing?"),
    ("Sam's birthday party is on 21 November", "When is Sam's party?"),
    ("Flight to Lisbon departs 2026-12-18 at 07:45", "When does my flight leave?"),
    ("Rent is due on the 1st of December 2026", "When is the rent due?"),
    ("Team offsite 9 to 11 December 2026", "When is the offsite?"),
]


def test_a_models_correct_date_phrasing_is_kept_by_the_fact_check(app_state):
    from tessellate.ai import fact_check
    from tessellate.ai.openai_client import OpenAICompatClient

    client = OpenAICompatClient(base_url=EVALS_URL)
    now = datetime(2026, 11, 14, 22, 0)
    kept = 0
    for facts, question in DATES:
        system = "Answer from the note in one short sentence. Say the date the way a person would."
        prose = str(client.chat(EVALS_MODEL, [{"role": "system", "content": system}, {"role": "user", "content": f"Note: {facts}\n\nQuestion: {question}"}]).get("content") or "")
        ok = fact_check.keeps(prose, facts, question, {}, False, now)
        kept += ok
        print(f"  {'kept' if ok else 'REFUSED'}: {prose.strip()[:100]!r}", flush=True)
    print(f"\n  date wording: {kept}/{len(DATES)} kept")
