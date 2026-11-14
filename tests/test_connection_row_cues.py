"""Two connected notes with the same title can be told apart.

Found measuring the Notes connections rail (WORLD_CLASS_PLAN D2): a note
linked to two notes both titled "rotate group note" drew two identical rows,
in the rail and in the Connections sheet, with nothing to choose between them
but a guess. The rows now carry a second, quiet cue only when their titles
collide: the category when the two differ, the date written when they do not
(and both when even the date matches, which is rare and still better than
nothing). A row whose title is its own carries no cue, so the column stays as
short as it was.

Two halves: the route says what the cue is made of (a note row's category and
when it was written; a private note's category stays back with its text), and
`connectionRowCues`, the pure function `buildConnectionGroups` draws with, is
run in node against the cases.
"""

from __future__ import annotations

import json
import re
import shutil
import subprocess

import pytest
from tests._app_js import app_js_text

from tessellate.core import vault


def test_a_note_row_carries_its_category_and_its_date(client):
    a = client.post("/entries", json={"content": "Hub", "category": "Work"}).json()
    b = client.post("/entries", json={"content": "Leaf", "category": "Travel"}).json()
    client.post(f"/entries/{a['id']}/links", json={"target_id": b["id"]})
    row = client.get(f"/entries/{a['id']}/connections").json()["outgoing"][0]
    assert row["category"] == "Travel"
    assert row["created_at"]


@pytest.fixture
def open_vault(session):
    """As in test_connections_block.py: a note can be made private only once
    a vault exists, opened by hand and closed again after."""
    vault.close()
    vault.create(session, "test-passphrase")
    session.commit()
    yield
    vault.close()


def test_a_private_note_row_keeps_its_category_back(ai_client, open_vault):
    """The category is a fact about the note's contents (it is what the filer
    read it as), so a private note keeps it back with its text; the date says
    nothing about what it says and stays."""
    a = ai_client.post("/entries", json={"content": "Hub"}).json()
    b = ai_client.post("/entries", json={"content": "Secret", "category": "Health"}).json()
    ai_client.post(f"/entries/{a['id']}/links", json={"target_id": b["id"]})
    marked = ai_client.post(f"/entries/{b['id']}/privacy", json={"private": True})
    assert marked.status_code == 200, marked.text
    row = ai_client.get(f"/entries/{a['id']}/connections").json()["outgoing"][0]
    assert row["is_private"] is True
    assert row["category"] is None
    assert row["created_at"]


def _cues(rows):
    source = app_js_text()
    match = re.search(r"^function connectionRowCues\(rows\) \{.*?^\}", source, re.S | re.M)
    assert match, "connectionRowCues is gone"
    script = (
        "function clockOptions() { return {}; }\n"  # the 12 or 24 hour setting at auto
        + match.group(0)
        + f"\nconst out = connectionRowCues({json.dumps(rows)});"
        + "\nprocess.stdout.write(JSON.stringify([...out.entries()]));"
    )
    result = subprocess.run(["node", "-e", script], capture_output=True, text=True, check=True)
    return dict(json.loads(result.stdout))


@pytest.mark.skipif(not shutil.which("node"), reason="needs node")
def test_only_colliding_titles_get_a_cue_and_it_is_the_category_first():
    cues = _cues([
        {"id": 1, "preview": "Plan", "category": "Work", "created_at": "2026-09-01T10:00:00"},
        {"id": 2, "preview": "Plan", "category": "Travel", "created_at": "2026-09-01T10:00:00"},
        {"id": 3, "preview": "Unique", "category": "Work", "created_at": "2026-09-02T10:00:00"},
    ])
    assert cues == {1: "Work", 2: "Travel"}


@pytest.mark.skipif(not shutil.which("node"), reason="needs node")
def test_the_same_category_falls_back_to_the_date():
    cues = _cues([
        {"id": 1, "preview": "Plan", "category": "Work", "created_at": "2024-09-01T10:00:00"},
        {"id": 2, "preview": "Plan", "category": "Work", "created_at": "2024-08-15T10:00:00"},
    ])
    assert cues[1] != cues[2]
    # A year that is not this one is named; this one's is left off to fit.
    assert "2024" in cues[1] and "Work" not in cues[1]


@pytest.mark.skipif(not shutil.which("node"), reason="needs node")
def test_the_same_day_falls_back_to_the_time_and_then_the_number():
    # Measured on the rail: two "rotate group note"s, both General, both
    # written on the same day, first drew the same cue twice.
    same_day = _cues([
        {"id": 1, "preview": "Plan", "category": "Work", "created_at": "2026-09-01T09:00:00"},
        {"id": 2, "preview": "Plan", "category": "Work", "created_at": "2026-09-01T17:30:00"},
    ])
    assert same_day[1] != same_day[2] and "Work" not in same_day[1]
    same_minute = _cues([
        {"id": 1, "preview": "Plan", "category": "Work", "created_at": "2026-09-01T09:00:00"},
        {"id": 2, "preview": "Plan", "category": "Work", "created_at": "2026-09-01T09:00:00"},
    ])
    assert same_minute[1].endswith("note 1") and same_minute[2].endswith("note 2")


@pytest.mark.skipif(not shutil.which("node"), reason="needs node")
def test_one_note_listed_twice_is_not_a_collision():
    # A note that links to this one and is linked from it is in both groups:
    # the same id twice is the same note, not two to tell apart.
    cues = _cues([
        {"id": 7, "preview": "Plan", "category": "Work", "created_at": "2026-09-01T10:00:00"},
        {"id": 7, "preview": "Plan", "category": "Work", "created_at": "2026-09-01T10:00:00"},
    ])
    assert cues == {}


def test_the_builder_draws_the_cue():
    source = app_js_text()
    body = source.split("function buildConnectionGroups(")[1].split("\n}\n")[0]
    assert "connectionRowCues(" in body and "cue" in body
    #: The cue is the row's subline, drawn by the one row builder (INBOX 784).
    assert "connection-row-cue" in source.split("function connectionRowEl(")[1].split("\n}\n")[0]
