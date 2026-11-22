"""Stop reaches the night shift and resurfacing between their steps (L658; embeddings backfill and maintenance already had one)."""

from __future__ import annotations

import pytest

from tessellate.ai import facts, resurface
from tessellate.core import jobruns, passes
from tessellate.entry import manager


@pytest.fixture(autouse=True)
def _clean():
    jobruns.stop_asked.clear()
    yield
    jobruns.stop_asked.clear()


def test_the_stoppable_set_names_every_pass_that_reads_its_flag():
    assert {"night-shift", "resurface", "embeddings-backfill", "maintenance"} <= passes.STOPPABLE


def test_a_stop_asked_ends_the_night_shift_at_the_next_note(ai_client, fake_ollama):
    for i in range(6):
        ai_client.post("/entries", json={"content": f"Note {i}. The deployment window should always be a Tuesday morning."})
    jobruns.stop_asked.add("night-shift")
    reply = ai_client.post("/night/run", json={"budget": facts.TOKENS_PER_NOTE * 50}).json()
    assert reply["stopped_reason"] == "stopped" and reply["scanned"] == 0


def test_a_stop_asked_ends_resurfacing_part_way_and_keeps_what_it_scored(session):
    for i in range(120):
        manager.create_entry(session, f"note number {i} about gardening", tags=[])
    session.commit()
    jobruns.stop_asked.add("resurface")
    written = resurface.compute_scores(session)
    assert 0 < written < 120
