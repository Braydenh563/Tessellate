"""CHAT_PLAN Phase 4's evals (Brief 13's done-when), against a real model.

Two measurements, both `evals` and skipped without one:

* **The loose-ends fixture**: seventy notes with eight planted loose ends
  (`tests/fixtures/chat/loose_ends.json`), "Find loose ends" run as the app
  runs it, and every planted one named in the answer, by its id or its
  anchor word.
* **Zero invalid calls over the built-in skills**: every built-in run under
  small-model mode; at least 80% finish with no step stalled or failed, and
  no run makes a call the harness refused for its arguments or its name.
  `TESSELLATE_EVALS_SKILLS` (comma separated names) narrows the set, for a
  machine where a full pass takes hours.

A fake transport calls whatever its script says, so either number measured
against one would be a measurement of the script (Brief 13, "Left" 1): these
need `TESSELLATE_EVALS_URL` and `TESSELLATE_EVALS_MODEL`, read here at import
exactly as `tests/test_skills_evals.py` reads them. The fixture's own shape
is checked without a model, so the module always collects a test.
"""

from __future__ import annotations

import json
import os
import re
from pathlib import Path

import pytest

EVALS_URL = os.environ.get("TESSELLATE_EVALS_URL", "").strip()
EVALS_MODEL = os.environ.get("TESSELLATE_EVALS_MODEL", "").strip()
FIXTURE = json.loads(
    (Path(__file__).parent / "fixtures" / "chat" / "loose_ends.json").read_text(encoding="utf-8")
)

needs_a_model = pytest.mark.skipif(
    not (EVALS_URL and EVALS_MODEL),
    reason="no real model: export TESSELLATE_EVALS_URL and TESSELLATE_EVALS_MODEL to run these",
)

#: Brief 13's done-when.
COMPLETION_GATE = 0.80

#: The refusals that mean the model wrote a call the harness could not run:
#: a missing or mistyped argument (`tools.check_arguments`) or a tool that
#: does not exist. A precondition refusal (`tools/contracts.py`) is the
#: notebook saying no to a well-formed call, and is not counted.
_INVALID = re.compile(r"\b(missing|wrong type|Unknown tool|is not a note id)\b")


def test_the_fixture_is_seventy_notes_with_eight_planted_loose_ends():
    notes = FIXTURE["notes"]
    assert len(notes) == 70
    planted = [n for n in notes if n["loose_end"]]
    assert len(planted) == 8
    cue = re.compile(r"\b(need to|waiting on|must|chase up|follow up|todo|should)\b", re.IGNORECASE)
    for note in planted:
        assert cue.search(note["content"]), note
        others = [m for m in notes if m is not note and note["anchor"].lower() in m["content"].lower()]
        assert not others, f"anchor {note['anchor']!r} is not unique"
    # The skill is the one the fixture is for, and still pages the notebook.
    from tessellate.ai import skills

    skill = next(s for s in skills.BUILTIN_SKILLS if s["name"] == "Find loose ends")
    assert "list_notes" in json.dumps(skill["steps"])


@pytest.fixture()
def real_model(app_state, fake_embeddings):
    from tessellate.ai.openai_client import OpenAICompatClient
    from tessellate.core import deps

    client = OpenAICompatClient(base_url=EVALS_URL)
    if not client.is_running():
        pytest.fail(f"TESSELLATE_EVALS_URL is {EVALS_URL} and nothing is answering there.")
    deps.override_ai(ollama=client)
    config = deps.get_config()
    config.set_preference("llm_provider", "openai")
    config.set_preference("llm_base_url", EVALS_URL)
    config.set_preference("chat_model", EVALS_MODEL)
    config.set_preference("small_model_mode", "on")
    return client


def _client(notes: list[dict]):
    from fastapi.testclient import TestClient

    from tessellate.api.app import create_app
    from tessellate.core import deps
    from tessellate.entry import manager

    ids = {}
    with deps.get_db().session() as session:
        for note in notes:
            entry = manager.create_entry(session, note["content"], "General", [])
            ids[note["id"]] = entry.id
    return TestClient(create_app()), ids


#: What a person would type into a skill's required boxes. The route answers
#: 422 for a missing one (`_resolve_skill`), which this harness used to send,
#: so every skill with an input failed before the model saw it (B69).
SAMPLE_INPUTS = {"topic": "the dentist", "tag": "work", "to": "Priya", "about": "the lease"}


def _inputs_for(skill: str) -> dict[str, str]:
    from tessellate.ai import skills

    found = next((s for s in skills.BUILTIN_SKILLS if s["name"] == skill), None)
    return {
        item["name"]: SAMPLE_INPUTS.get(item["name"], "my notes")
        for item in (found or {}).get("inputs") or []
        if item.get("required")
    }


def _run(client, skill: str) -> list[dict]:
    body = {"question": skill, "skill": skill, "skill_inputs": _inputs_for(skill)}
    with client.stream("POST", "/chat/stream", json=body) as response:
        assert response.status_code == 200
        return [json.loads(line) for line in response.iter_lines() if line]


def _answer(events: list[dict]) -> str:
    finals = [e.get("text", "") for e in events if e.get("type") == "answer_final"]
    return finals[-1] if finals else "".join(e.get("delta", "") for e in events if e.get("type") == "answer")


@pytest.mark.evals
@needs_a_model
def test_find_loose_ends_names_all_eight(real_model):
    client, ids = _client(FIXTURE["notes"])
    events = _run(client, "Find loose ends")
    answer = _answer(events)
    missed = [
        note["anchor"]
        for note in FIXTURE["notes"]
        if note["loose_end"]
        and note["anchor"].lower() not in answer.lower()
        and not re.search(rf"#\s*{ids[note['id']]}\b|\bid\s*{ids[note['id']]}\b", answer)
    ]
    assert not missed, f"{EVALS_MODEL} missed {len(missed)} of 8: {missed}\n\n{answer[:1500]}"


def _invalid_calls(events: list[dict]) -> list[str]:
    return [
        f"{e.get('tool')}: {(e.get('error') or '')[:120]}"
        for e in events
        if e.get("type") == "tool" and e.get("ok") is False and _INVALID.search(e.get("error") or "")
    ]


def _finished(events: list[dict]) -> bool:
    last: dict[int, str] = {}
    for event in events:
        if event.get("type") == "step":
            last[event["index"]] = event.get("status") or event.get("state") or ""
    return bool(last) and all(state == "done" for state in last.values())


@pytest.mark.evals
@needs_a_model
def test_the_built_in_skills_finish_with_no_invalid_call(real_model):
    from tessellate.ai import skills

    wanted = {s.strip() for s in os.environ.get("TESSELLATE_EVALS_SKILLS", "").split(",") if s.strip()}
    chosen = [s["name"] for s in skills.BUILTIN_SKILLS if not wanted or s["name"] in wanted]
    client, _ids = _client([n for n in FIXTURE["notes"]][:20])
    finished, invalid = 0, []
    for name in chosen:
        events = _run(client, name)
        finished += _finished(events)
        invalid += [f"{name}: {row}" for row in _invalid_calls(events)]
    rate = finished / len(chosen)
    assert not invalid, f"{EVALS_MODEL}: invalid calls:\n" + "\n".join(invalid)
    assert rate >= COMPLETION_GATE, f"{EVALS_MODEL}: {finished} of {len(chosen)} finished ({100 * rate:.0f}%)"
