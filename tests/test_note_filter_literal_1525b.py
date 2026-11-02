"""The Notes list's word filter is literal text, on the server and in the rows (INBOX 1525 review).

The list holds each note's first 300 characters and asks the server
(`/search?ids_only`, `engine.match_ids`) for the bodies. That server path read
the box as a question: "today" and "the" named nothing and came back null,
which the list took as "no filter"; "roadmap yesterday" became a date filter;
words matched as prefixes, so "oadmap" missed "roadmap" and "zeta150" missed
"zeta1500"; and private notes, never indexed, were hidden by any word.
"""

from __future__ import annotations

import json
import re
import shutil
import subprocess
from pathlib import Path

import pytest

from tessellate.core import vault
from tests._app_js import with_pieces


def _note(client, text, **extra):
    return client.post("/entries", json={"content": text, "defer_filing": True, **extra}).json()["id"]


def _ids(client, q):
    return client.get("/search", params={"q": q, "kind": "note", "ids_only": "true"}).json()["ids"]


def test_time_words_stop_words_and_symbols_are_words(client):
    today = _note(client, "Plan for today and tomorrow")
    the = _note(client, "the end")
    cpp = _note(client, "Notes on c++ templates")
    other = _note(client, "Something else entirely")
    assert _ids(client, "today") == [today]
    assert _ids(client, "the") == [the]
    assert _ids(client, "c++") == [cpp]
    assert _ids(client, "yesterday") == []
    assert other not in (_ids(client, "today") + _ids(client, "the"))


def test_a_date_word_or_a_scope_word_is_not_a_filter(client):
    both = _note(client, "Roadmap review in March, held yesterday")
    one = _note(client, "Roadmap draft")
    assert _ids(client, "roadmap yesterday") == [both]
    assert _ids(client, "roadmap in review") == [both]  # "in" is a word, not a scope
    assert one in _ids(client, "roadmap")


def test_a_word_matches_inside_a_word_and_digits_too(client):
    road = _note(client, "The roadmap for spring")
    zeta = _note(client, "Build zeta1500 shipped")
    assert _ids(client, "oadmap") == [road]
    assert _ids(client, "zeta150") == [zeta]
    assert _ids(client, "ROADMAP") == [road]


def test_percent_and_underscore_are_literal(client):
    pct = _note(client, "Grew 50% this year")
    snake = _note(client, "call my_function here")
    _note(client, "Grew 500 this year, myxfunction")
    assert _ids(client, "50%") == [pct]
    assert _ids(client, "my_function") == [snake]


def test_a_word_deep_in_a_long_note_and_a_tag(client):
    deep = _note(client, "Start. " + "filler words here. " * 200 + "the zanzibar clove harvest")
    tagged = _note(client, "short", tags=["kilimanjaro"])
    assert _ids(client, "zanzibar") == [deep]
    assert _ids(client, "kilimanjaro") == [tagged]
    assert _ids(client, "-zanzibar").count(deep) == 0


@pytest.fixture
def open_vault(session):
    vault.close()
    vault.create(session, "test-passphrase")
    session.commit()
    yield
    vault.close()


def test_a_private_note_is_sent_whole_to_the_list_so_the_list_can_match_it(client, open_vault):
    secret = _note(client, "Diary. " + "words to fill. " * 60 + "the marmalade recipe")
    marked = client.post(f"/entries/{secret}/privacy", json={"private": True})
    assert marked.status_code == 200, marked.text
    rows = client.get("/entries", params={"preview": "300"}).json()
    row = next(r for r in rows if r["id"] == secret)
    assert not row["content_truncated"] and row["content"].endswith("marmalade recipe")
    assert secret not in _ids(client, "marmalade")  # never read by the server: the list matches it


# --- the list ---------------------------------------------------------------


JS = Path(__file__).resolve().parent.parent / "frontend" / "js"
_PIECES = ["parseNoteQuery", "noteQueryIsEmpty", "matchesSearch"]
_CONSTS = ["LIVE_QUERY_RE", "ENGINE_QUERY_RE", "TAG_COUNT_RE"]


def _list_source() -> str:
    text = with_pieces("notes-list.js")
    out = []
    for name in _CONSTS:
        m = re.search(rf"^const {name} =.*?;\n", text, re.M | re.S)
        assert m, name
        out.append(m.group(0))
    for name in _PIECES:
        m = re.search(rf"^function {name}\(.*?^\}}\n", text, re.M | re.S)
        assert m, name
        out.append(m.group(0))
    return "\n".join(out)


def _matches(rows: list[dict], q: str, served) -> list[int]:
    """The ids `matchesSearch` keeps for `q`, the server answering `served` (a list, or None for asking or failed)."""
    script = f"""
let noteSearch = {json.dumps(q)};
const NOTE_FLAGS = [];
const served = {json.dumps(served)};
const noteEngine = {{ bodyIds: () => (served === null ? null : new Set(served)) }};
const noteSemanticLoaded = () => false;
const noteSortName = (e) => e.title || "";
{_list_source()}
process.stdout.write(JSON.stringify({json.dumps(rows)}.filter(matchesSearch).map((e) => e.id)));
"""
    done = subprocess.run(["node", "-e", script], capture_output=True, text=True, timeout=30)
    assert done.returncode == 0, done.stderr
    return json.loads(done.stdout)


ROWS = [
    {"id": 1, "content": "Roadmap for spring", "tags": [], "content_truncated": False},
    {"id": 2, "content": "A long note whose start says nothing", "tags": [], "content_truncated": True},
    {"id": 3, "content": "Private diary, the roadmap", "tags": [], "is_private": True, "content_truncated": False},
    {"id": 4, "content": "Unrelated", "tags": [], "content_truncated": False},
    {"id": 5, "content": "Roadmap kept short, rest clipped", "tags": [], "content_truncated": True},
]

needs_node = pytest.mark.skipif(not shutil.which("node"), reason="needs node")


@needs_node
def test_a_note_is_in_when_the_server_or_the_row_finds_it():
    # The server finds 2 (past its preview) and 1 and 5; 3 is private, only the row finds it.
    assert _matches(ROWS, "roadmap", [1, 2, 5]) == [1, 2, 3, 5]
    # "oadmap" is inside a word: the row's own substring match finds it too.
    assert _matches(ROWS, "oadmap", [1, 2, 5]) == [1, 2, 3, 5]


@needs_node
def test_a_server_still_asking_or_failed_leaves_the_rows_answer_never_every_note():
    assert _matches(ROWS, "roadmap", None) == [1, 3, 5]
    assert _matches(ROWS, "today", None) == []


@needs_node
def test_an_exclusion_past_a_clipped_preview_is_the_servers_call():
    # 5 is clipped and the server saw "-spring"... absent from 5's preview: the server's answer stands.
    assert _matches(ROWS, "roadmap -secret", [1]) == [1, 3]
    # A whole row is decided by its own text.
    assert _matches(ROWS, "roadmap -spring", [5]) == [3, 5]


def test_a_null_answer_is_no_answer_not_every_note():
    text = with_pieces("notes-list.js")
    body = text[text.index("  bodyIds(query) {") :][:600]
    assert "ids: r.ids && new Set(r.ids)" in body and "new Set(r.ids) : true" not in body
