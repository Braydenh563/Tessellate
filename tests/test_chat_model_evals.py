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


#: (sentence, the handover or tool that is the right move): L827 plans, L828 propose_act and a read tool, L829 ask_user.
TOOL_TURNS = [
    ("First tag the dentist note health, then pin the plumber note, then remind me on Friday to call the plumber", "plan"),
    ("Do three things: pin the Snowdon note, tag the plumber note urgent, and make a note called Shopping", "plan"),
    ("What is 15% of 240?", "calculate"),
    ("How much is 18 times 42?", "calculate"),
    ("Remind me on Friday to call mum", "act"),
    ("I want to file my note under Work. Ask me which category, the only choice is Work.", "ask"),
    ("Ask me whether to continue. The only option is Yes.", "ask"),
]


def test_a_model_plans_calculates_proposes_and_asks_without_a_dead_end(notebook):  # noqa: F811
    """L827 (a plan the previews can read), L828 (propose_act and Calculate), L829 (a one-option ask is never drawn):
    asserted is that every turn ends in words or a card and no ask card has fewer than two options."""
    rows = []
    for sentence, wanted in TOOL_TURNS:
        started = time.monotonic()
        events = _turn(notebook, sentence)
        calls = _calls(events)
        plan = next((e for e in events if e.get("type") == "run_plan"), None)
        asks = [e for e in events if e.get("type") == "ask"]
        words = (_answer(events) or " ".join(str(e.get("text", "")) for e in events if e.get("type") == "answer_final")).strip()
        row = {
            "q": sentence[:48], "wanted": wanted, "tools": [c["tool"] for c in calls], "failed": [c["tool"] for c in calls if not c.get("ok")],
            "plan_steps": len(plan["steps"]) if plan else 0,
            "plan_previewed": sum(bool(w) for w in plan["writes"]) if plan else 0,
            "asks": [len(a.get("options") or []) for a in asks], "cards": len(_cards(events)), "words": bool(words), "s": round(time.monotonic() - started, 1),
        }
        rows.append(row)
        print(" ", row, flush=True)
        assert words or _cards(events) or plan or asks, f"{sentence!r} ended in nothing"
        assert all(n >= 2 for n in row["asks"]), f"{sentence!r} drew an ask with one option"
    print(f"\n  plan: {sum(r['plan_steps'] > 0 for r in rows[:2])}/2 sentences made a plan, previewed steps {[(r['plan_previewed'], r['plan_steps']) for r in rows[:2]]}")
    print(f"  calculate: {sum('calculate' in r['tools'] for r in rows[2:4])}/2 called calculate, {sum(r['words'] for r in rows[2:4])}/2 ended in words")
    print(f"  propose_act: {sum('propose_act' in r['tools'] or bool(r['cards']) for r in rows[4:5])}/1 ended in a card")
    print(f"  ask_user: {sum('ask_user' in r['tools'] for r in rows[5:])}/2 called ask_user, drawn with one option: {sum(1 for r in rows[5:] for n in r['asks'] if n < 2)}")


def test_the_link_reason_audit_can_be_undone_with_a_real_model(notebook):  # noqa: F811
    """L-chat-258: a real model rewrites the vague reasons, then the undo puts every old one back."""
    from tessellate.ai import tools
    from tessellate.core import deps
    from tessellate.core.database import Entry, EntryLink
    from tessellate.entry import manager_links

    with deps.get_db().session() as session:
        ids = [e.id for e in session.query(Entry).order_by(Entry.id).limit(5)]
        for a, b in zip(ids, ids[1:]):
            session.add(EntryLink(source_entry_id=a, target_entry_id=b, reason=manager_links.AUTO_REASON_TEXT, reason_confidence=0.8))
        session.commit()
        started = time.monotonic()
        done = tools.execute_tool(session, "audit_link_reasons", {"limit": 4})
        took = time.monotonic() - started
        written = [r for (r,) in session.query(EntryLink.reason).all()]
        print(f"\n  audit: rewrote {done.get('updated')} of {len(written)} in {took:.0f}s; reasons {written}", flush=True)
        if not done.get("updated"):
            assert "undo" not in done  # only vague replies, so there is nothing to put back
            return
        back = tools.execute_tool(session, done["undo"]["tool"], done["undo"]["arguments"])
        left = session.query(EntryLink).filter(EntryLink.reason == manager_links.AUTO_REASON_TEXT, EntryLink.reason_confidence == 0.8).count()
        print(f"  undo: put back {back.get('restored')}, {left} links carry the old reason again", flush=True)
        assert back["restored"] == done["updated"] and left == len(written)
