"""L-chat-62: Find loose ends is paged and cue-matched by the runner, so every
planted loose end reaches the answer whatever the model does with its turn.

Measured before (2026-11-14, a 1.5B model, the seventy-note fixture): one
list_notes call with invented filters, no paging, two stalls, 2 of 8 named.
The fake here writes an answer that names nobody, the worst a model can do;
the small-model closing paragraph still names all eight by id."""

from __future__ import annotations

import json
import re
from pathlib import Path

from tessellate.ai import skill_scan, skills
from tests._skill_run import run_for_test

FIXTURE = json.loads((Path(__file__).parent / "fixtures" / "chat" / "loose_ends.json").read_text(encoding="utf-8"))


def _seed(session):
    from tessellate.entry import manager

    ids = {}
    for note in FIXTURE["notes"]:
        ids[note["id"]] = manager.create_entry(session, note["content"], "General", []).id
    session.commit()
    return ids


def test_the_cue_match_is_whole_phrase_and_case_blind():
    cue = skill_scan.cue_pattern(["must", "need to"])
    assert cue.search("Must renew the car insurance")
    assert cue.search("I need to ring them")
    assert not cue.search("mustard on the list")


def test_the_spec_carries_scan_and_reads_through_normalise():
    skill = next(s for s in skills.BUILTIN_SKILLS if s["name"] == "Find loose ends")
    specs = skills.step_specs(skills.normalise(skill, known_tools=None))
    assert specs[0]["scan"][:2] == ["todo", "need to"]
    assert specs[1]["reads"] == "candidates"
    assert "scan" not in specs[2] and "reads" not in specs[2]


def test_every_planted_loose_end_is_found_read_and_named(app_state, fake_ollama, fake_embeddings, session):
    ids = _seed(session)
    fake_ollama.tool_script = [[]]  # the answer step: prose naming nobody
    run = run_for_test(fake_ollama, skill="find_loose_ends", small_model=True)
    planted = {ids[n["id"]] for n in FIXTURE["notes"] if n["loose_end"]}
    assert set(run.state["candidates"]) == planted
    assert len(run.state["seen_ids"]) == 70
    reads = [e for e in run.events if e.get("type") == "tool" and e.get("tool") == "get_note"]
    assert {e["arguments"]["note_id"] for e in reads} == planted
    said = "".join(e.get("delta", "") for e in run.events if e.get("type") == "answer")
    assert {int(m) for m in re.findall(r"#(\d+)", said)} >= planted
    assert [s.state for s in run.steps] == ["done", "done", "done"]
    assert run.verification.ok


def test_a_larger_model_keeps_its_own_judgment(app_state, fake_ollama, fake_embeddings, session):
    """No closing paragraph outside small-model mode: the answer step may drop
    a candidate it read as closed off."""
    _seed(session)
    fake_ollama.tool_script = [[]]
    run = run_for_test(fake_ollama, skill="find_loose_ends", small_model=False)
    said = "".join(e.get("delta", "") for e in run.events if e.get("type") == "answer")
    assert "from the scan" not in said
