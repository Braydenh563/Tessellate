"""The agent harness, judged by a real model (AGENT_SKILLS_REFORM, "Harness
robustness, 2026-10-04", INBOX 527).

Same seam as `test_skills_evals.py`: TESSELLATE_EVALS_URL and
TESSELLATE_EVALS_MODEL, read at import; without them every test here is
skipped and the module still collects (the last test needs no model).

What is asserted is what the harness guarantees whatever the model says: a
turn always ends with words, a failed call always comes back with a
`what_to_do`, no turn repeats an identical failed call. What a 1.5B model
manages (tool choice, valid arguments, a picture placed) is printed as a
number for the plan, with a floor low enough that only a harness regression
crosses it: run with `-s` to read the numbers.
"""

from __future__ import annotations

import json
import os
import time

import pytest

EVALS_URL = os.environ.get("TESSELLATE_EVALS_URL", "").strip()
EVALS_MODEL = os.environ.get("TESSELLATE_EVALS_MODEL", "").strip()

needs_a_model = pytest.mark.skipif(
    not (EVALS_URL and EVALS_MODEL),
    reason="no real model: export TESSELLATE_EVALS_URL and TESSELLATE_EVALS_MODEL",
)

#: (request, the tools any one of which is the right first move, the tool
#: that finishes the job). Phrased the way people type, not the way a schema
#: reads.
CASES = [
    ("How many notes do I have?", {"count_notes"}, "count_notes"),
    ("Make a note: buy oat milk and eggs", {"create_note"}, "create_note"),
    ("Remind me tomorrow at 9am to call the dentist", {"set_reminder"}, "set_reminder"),
    ("Remind me in 20 minutes to take the bread out", {"set_reminder"}, "set_reminder"),
    ("What categories do I have?", {"list_categories"}, "list_categories"),
    ("What tags am I using?", {"list_tags"}, "list_tags"),
    ("Tag my plumber note with urgent", {"search_notes", "tag_note"}, "tag_note"),
    ("Pin my dentist note", {"search_notes", "pin_note"}, "pin_note"),
    ("Show me the whole Snowdon trip note", {"search_notes", "get_note"}, "get_note"),
    ("Add 'bring a rain jacket' to my Snowdon trip note", {"search_notes", "get_note", "edit_note"}, "edit_note"),
]

NOTES = [
    ("Chase up the invoice from the plumber, he still has not sent it", "Work"),
    ("Dentist appointment needs booking, the practice on King Street", "Health"),
    ("Snowdon trip: carry the new boots, start at Pen-y-Pass at 7am", "Travel"),
    ("Planning meeting whiteboard ![whiteboard sketch](/media/wb.png)", "Work"),
]


@pytest.fixture()
def notebook(app_state, fake_embeddings):
    from fastapi.testclient import TestClient

    from tessellate.ai.openai_client import OpenAICompatClient
    from tessellate.api.app import create_app
    from tessellate.core import deps
    from tessellate.entry import manager

    client = OpenAICompatClient(base_url=EVALS_URL)
    if not client.is_running():
        pytest.fail(f"TESSELLATE_EVALS_URL is {EVALS_URL} and nothing is answering there")
    deps.override_ai(ollama=client)
    config = deps.get_config()
    config.set_preference("llm_provider", "openai")
    config.set_preference("llm_base_url", EVALS_URL)
    config.set_preference("chat_model", EVALS_MODEL)
    media = config.data_dir / "media"
    media.mkdir(parents=True, exist_ok=True)
    # A 1x1 PNG is enough: the prompt counts pictures, it does not look.
    (media / "wb.png").write_bytes(bytes.fromhex(
        "89504e470d0a1a0a0000000d4948445200000001000000010806000000"
        "1f15c4890000000d49444154789c6360000002000154a24f5d0000000049454e44ae426082"
    ))
    with deps.get_db().session() as session:
        for text, category in NOTES:
            manager.create_entry(session, text, category, [])
    return TestClient(create_app())


def _turn(client, question: str) -> list[dict]:
    with client.stream(
        "POST", "/chat/stream", json={"question": question, "use_tools": True}
    ) as response:
        assert response.status_code == 200
        return [json.loads(line) for line in response.iter_lines() if line]


def _calls(events: list[dict]) -> list[dict]:
    return [e for e in events if e.get("type") == "tool" and e.get("tool")]


def _cards(events: list[dict]) -> list[dict]:
    return [e for e in events if e.get("type") in {"confirm", "act"} and not e.get("cancel") and not e.get("settle")]


def _search_mode(events: list[dict]) -> str:
    return next((str(e.get("search_mode")) for e in events if e.get("type") == "meta"), "")


def _answer(events: list[dict]) -> str:
    return "".join(e.get("delta", "") for e in events if e.get("type") == "answer")


@pytest.mark.evals
@needs_a_model
def test_tool_choice_and_argument_validity(notebook):
    """Per case: the first call is one of the right moves, the finishing tool
    ran without an error, every failed call carried advice, the turn ended in
    words, no identical failed call was repeated."""
    rows = []
    for question, first_ok, finisher in CASES:
        started = time.monotonic()
        events = _turn(notebook, question)
        calls = _calls(events)
        names = [c["tool"] for c in calls]
        failed = [c for c in calls if not c.get("ok")]
        repeated = {
            (c["tool"], json.dumps(c.get("arguments"), sort_keys=True)) for c in failed
        }
        rows.append({
            "q": question,
            "first": names[0] if names else None,
            "chose": bool(names) and names[0] in first_ok,
            #: The engine took the sentence before the agent did (a write parked as a card, or a count answered from
            #: the notebook's own stats): the move was made, by the engine rather than the model's tool call.
            "engine": not names and (bool(_cards(events)) or _search_mode(events) in {"stats", "tool"}),
            "finished": any(c["tool"] == finisher and c.get("ok") for c in calls),
            "calls": len(calls),
            "failed": len(failed),
            "answered": bool(_answer(events).strip()),
            "s": round(time.monotonic() - started, 1),
        })
        print(" ", rows[-1], flush=True)
        assert _answer(events).strip(), f"{question!r} ended with no words"
        assert len(repeated) == len(failed) or not failed, f"{question!r} repeated a failed call"
    total = len(rows)
    chose = sum(r["chose"] for r in rows)
    engine = sum(r["engine"] for r in rows)
    finished = sum(r["finished"] for r in rows)
    calls = sum(r["calls"] for r in rows)
    failed = sum(r["failed"] for r in rows)
    print("\nHARNESS EVAL", EVALS_MODEL.rsplit("/", 1)[-1])
    print(
        f"  tool choice {chose}/{total}, taken by the engine first {engine}/{total}; finished {finished}/{total}; "
        f"argument validity {calls - failed}/{calls} calls"
    )
    #: Intent moved (2026-11-14): the engine answers or parks most of these sentences before the model is asked (a 1.5B
    #: run made 0 tool calls in 10), so the floor counts a move made either way; it is still the harness regression guard.
    assert chose + engine >= total // 3, "tool choice and engine moves fell below a third: a harness regression"


@pytest.mark.evals
@needs_a_model
def test_a_picture_question_places_the_picture(notebook):
    """INBOX 527's question: does the agent know it can show a picture? The
    answer to a picture question carries `[picture N]` for the note that has
    one. Printed, not asserted: placement is the model's choice."""
    placed = 0
    tries = 3
    for _ in range(tries):
        answer = _answer(_turn(notebook, "Show me the whiteboard sketch from the planning meeting"))
        #: Either form shows it: the `[picture N]` token, or the note's own
        #: `![alt](/media/...)`, which the bubble's markdown draws as an image
        #: (Qwen2.5-3B wrote the second, 5 of 5, H4).
        placed += "[picture" in answer.lower() or "](/media/" in answer
    print(f"\n  picture placed {placed}/{tries}")


def test_the_harness_evals_are_marked_and_skippable():
    """Collected without a model, so the module never exits 5 (see the same
    test in test_skills_evals.py for why that matters to the gate)."""
    assert CASES and all(len(case) == 3 for case in CASES)
