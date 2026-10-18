"""A recording is found by what it is called and by what was said in it
(ledger libr-1011 row 1218: "search does not find recordings").

The kind is `recording`, its words are the title plus the transcript lines, and
a take still being made or sitting in the bin is out of the index, the same
rule a binned document follows."""

from __future__ import annotations

import json
import re
from pathlib import Path

from tessellate.core import deps
from tessellate.core.database import Recording
from tessellate.search import index

ROOT = Path(__file__).resolve().parents[1]
WEBM_HEAD = b"\x1a\x45\xdf\xa3" + b"\x00" * 60


def _saved(title: str, lines: list[str], **extra) -> int:
    segments = [{"start": i * 2000, "end": i * 2000 + 1800, "text": text, "speaker": ""} for i, text in enumerate(lines)]
    with deps.get_db().session() as session:
        row = Recording(
            title=title,
            mime="audio/webm",
            filename="x.webm",
            duration_ms=60_000,
            state=extra.pop("state", "saved"),
            segments=json.dumps(segments),
            **extra,
        )
        session.add(row)
        session.commit()
        return row.id


def _hits(client, query: str) -> list[dict]:
    return client.get("/search", params={"q": query, "limit": 50, "hybrid": "false"}).json()["hits"]


def test_recording_is_a_kind_with_a_source():
    assert "recording" in index.KINDS
    assert index.source_for("recordings").kind == "recording"


def test_a_title_word_and_a_spoken_word_both_find_it(client):
    rid = _saved("Quarterly planning call", ["we agreed the zeppelin budget", "ship on friday"])
    by_title = [h for h in _hits(client, "quarterly") if h["kind"] == "recording"]
    by_speech = [h for h in _hits(client, "zeppelin") if h["kind"] == "recording"]
    assert [h["id"] for h in by_title] == [rid]
    assert [h["id"] for h in by_speech] == [rid]
    assert by_speech[0]["source"] == "recordings"


def test_the_kind_operator_asks_for_recordings_alone(client):
    rid = _saved("Budget review", ["the budget is fine"])
    client.post("/entries", json={"content": "a note about the budget"})
    both = {h["kind"] for h in _hits(client, "budget")}
    only = _hits(client, "kind:recording budget")
    assert {"note", "recording"} <= both
    assert [(h["kind"], h["id"]) for h in only] == [("recording", rid)]


def test_a_take_in_progress_is_not_indexed(client):
    _saved("Live take", ["marmalade"], state="recording")
    assert not [h for h in _hits(client, "marmalade") if h["kind"] == "recording"]


def test_a_binned_recording_leaves_and_a_restored_one_returns(client):
    rid = _saved("Binned call", ["quokka"])
    assert [h for h in _hits(client, "quokka") if h["kind"] == "recording"]
    binned = client.delete(f"/recordings/{rid}")
    assert binned.status_code == 200
    assert not [h for h in _hits(client, "quokka") if h["kind"] == "recording"]
    restored = client.post(f"/recordings/{rid}/restore")
    assert restored.status_code == 200
    assert [h for h in _hits(client, "quokka") if h["kind"] == "recording"]


def test_a_transcript_written_later_is_found(client):
    rid = _saved("Voice memo", [])
    assert not [h for h in _hits(client, "walrus") if h["kind"] == "recording"]
    with deps.get_db().session() as session:
        session.get(Recording, rid).segments = json.dumps([{"start": 0, "end": 900, "text": "the walrus spoke", "speaker": ""}])
        session.commit()
    assert [h["id"] for h in _hits(client, "walrus") if h["kind"] == "recording"] == [rid]


def test_an_older_notebook_is_filled_once_by_the_late_source_pass(client):
    rid = _saved("Old call", ["pangolin"])
    with deps.get_db().session() as session:
        connection = session.connection()
        source = index.source_for("recordings")
        connection.exec_driver_sql(
            "DELETE FROM search_index WHERE rowid >= ? AND rowid < ?",
            (source.slot * index.SLOT_STRIDE, (source.slot + 1) * index.SLOT_STRIDE),
        )
        session.commit()
    assert not [h for h in _hits(client, "pangolin") if h["kind"] == "recording"]
    with deps.get_db().session() as session:
        assert index.reconcile_sources(session) is True
        session.commit()
        assert index.reconcile_sources(session) is False
    assert [h["id"] for h in _hits(client, "pangolin") if h["kind"] == "recording"] == [rid]


def test_the_finder_has_a_chip_and_opens_the_recordings_list():
    source = (ROOT / "frontend/js/search.js").read_text(encoding="utf-8")
    assert 'key: "recording"' in source
    assert re.search(r"\brecording: \(hit\) => .*openRecordings\(hit\.id\)", source)


def test_a_mark_comment_finds_the_recording(client):
    rid = _saved("Standup", ["nothing notable"], markers=json.dumps([{"at": 4000, "note": "ask about the pelican budget"}]))
    found = [h for h in _hits(client, "pelican") if h["kind"] == "recording"]
    assert [h["id"] for h in found] == [rid]
