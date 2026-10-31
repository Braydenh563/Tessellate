"""WORLD_CLASS_PLAN I7: the evidence half of the corrections loop has a caller.

`learning.filing_evidence` was built and tested alone with nothing calling it,
the way `excluded_categories` once was (audit ARCH-08). The plan's algorithm
says the filing prompt gets the nearest already-filed notes with their
categories; the janitor's model path builds that prompt, so that is where the
evidence is read.
"""

from __future__ import annotations

import pytest

from tessellate.ai import janitor, learning, librarian
from tessellate.entry import manager


def _filed(session, text, category, *, private=False):
    entry = manager.create_entry(session, text, category, [])
    if private:
        entry.is_private = True
    session.commit()
    return entry


def test_the_filing_prompt_names_the_notes_that_read_like_this_one(app_state, session):
    _filed(session, "fixed the flaky retry in the payments worker", "Work")
    _filed(session, "sourdough starter feeding schedule", "Kitchen")
    prompt = librarian.filing_prompt(
        session, "another fix in the payments worker retry path", ["Work", "Kitchen"]
    )
    assert "payments worker" in prompt.split("Note:")[0]
    assert "is in Work" in prompt
    assert "sourdough" not in prompt
    assert prompt.index("is in Work") < prompt.index("Note: <<<data note>>>\nanother fix")


def test_a_private_note_never_reaches_the_prompt(app_state, session):
    _filed(session, "payments worker retry secret plan", "Work", private=True)
    evidence = learning.filing_evidence(session, "payments worker retry")
    assert [item for item in evidence if item["kind"] == "neighbour"] == []
    prompt = librarian.filing_prompt(session, "payments worker retry", ["Work"])
    assert "secret plan" not in prompt


def test_the_note_being_filed_is_not_its_own_evidence(app_state, session):
    own = _filed(session, "payments worker retry timeout", "Work")
    evidence = learning.filing_evidence(
        session, "payments worker retry timeout", exclude_entry_id=own.id
    )
    assert not [item for item in evidence if item["kind"] == "neighbour"]


def test_a_correction_that_reads_like_the_note_is_in_the_prompt_once(app_state, session):
    entry = _filed(session, "fixed the flaky retry in the payments worker", "Work")
    entry.filing_state = manager.AUTO_FILED
    session.commit()
    manager.update_entry(session, entry, category_name="Projects")
    session.commit()
    prompt = librarian.filing_prompt(
        session, "another fix in the payments worker retry path", ["Work", "Projects"]
    )
    assert prompt.count("flaky retry in the payments worker") == 2  # the correction, and the neighbour
    assert prompt.count("was moved from Work to Projects") == 1


def test_the_switch_that_silences_corrections_silences_the_evidence(app_state, session, monkeypatch):
    _filed(session, "fixed the flaky retry in the payments worker", "Work")
    monkeypatch.setattr("tessellate.ai.facts.runner_enabled", lambda name: False)
    prompt = librarian.filing_prompt(session, "payments worker retry", ["Work"])
    assert "is in Work" not in prompt


def test_the_model_path_passes_the_note_it_is_filing(app_state, session, monkeypatch):
    own = _filed(session, "payments worker retry timeout", "Work")
    seen = {}

    class _Stop(Exception):
        pass

    def fake_prompt(sess, content, categories, exclude_entry_id=None):
        seen["exclude"] = exclude_entry_id
        raise _Stop

    class _Up:
        def is_running(self):
            return True

    monkeypatch.setattr(librarian, "filing_prompt", fake_prompt)
    with pytest.raises(_Stop):
        janitor._ask_llm(session, own.content, object(), _Up(), exclude_entry_id=own.id)
    assert seen["exclude"] == own.id
