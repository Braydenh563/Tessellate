"""Help and the Guide from the registry (CHAT_PLAN section 2, the help row):
the probe's Guide table at 1.0 (the phone, two computers, encryption,
deleting your data, sharing a note, filing; `archive/agent-remaining/engine-probe-1010.md`),
and the palette's act rows and help lines generated from `ai/acts.py`."""

from __future__ import annotations

from pathlib import Path

import pytest

from tessellate.ai import acts, help_chat

ROOT = Path(__file__).resolve().parents[1]

#: The probe's table, each question with the topic it must open on.
PROBE = [
    ("phone", "phone"),
    ("can I use it on my phone", "phone"),
    ("can I use it on two computers", "two-computers"),
    ("how do I move to a new computer", "two-computers"),
    ("is my data encrypted", "encryption"),
    ("how do I delete my data", "delete-data"),
    ("how do I share a note", "share-note"),
    ("what is filing", "filing"),
]


@pytest.mark.parametrize("question,topic", PROBE)
def test_the_probes_guide_table_at_one(question, topic):
    found = help_chat.topics_for(question)
    assert found and found[0]["id"] == topic, [t["id"] for t in found[:3]]


def test_every_palette_act_row_is_the_registrys():
    rows = acts.palette_rows()
    assert [r["intent"] for r in rows] == list(acts.ACTS)
    assert all(r["help"].endswith(".") for r in rows) and sum(bool(r["stem"]) for r in rows) >= 8
    assert {r["intent"] for r in rows} <= set(acts.ACTS)
    assert all(acts.ACTS[r["intent"]].help in r["help"] for r in rows)


def test_the_palette_draws_them_from_the_route(client):
    got = client.get("/read/acts").json()
    assert got["rows"] == acts.palette_rows() and got["capability"] == acts.capability_line()
    palette = (ROOT / "frontend/js/palette.js").read_text(encoding="utf-8")
    assert '"/read/acts"' in palette and "agentActStarters()" in palette
