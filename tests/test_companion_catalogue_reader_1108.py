"""The in-app companion reads the catalogue once and keeps its built-in tables when it cannot (atlascat-1108 A2)."""

from __future__ import annotations

import pytest

from tests._cat_node import AVATARS, run

ACTS = {"look": {"ms": 2600, "w": 3, "cool": 12000, "poses": ["stand"]}, "nap": {"ms": 30000, "w": 0, "cool": 1, "poses": ["stand"]}}
WAIT = "await new Promise((r) => setTimeout(r, 20));"


def test_the_reader_is_wired_to_the_first_idle_decision_and_is_silent() -> None:
    text = AVATARS.read_text(encoding="utf-8")
    assert 'api("/companion-catalogue.json", { silent: true })' in text
    schedule = text[text.index("function nameMarkBuddySchedule()"):][:400]
    assert "nmb.cat.load();" in schedule


def test_it_fetches_once() -> None:
    out = run(
        f"nmb.cat.load(); nmb.cat.load(); {WAIT}"
        "console.log(JSON.stringify({n: calls.length, path: calls[0][0], silent: calls[0][1].silent, entries: nmb.cat.state.doc.entries.length}));"
    )
    assert out == {"n": 1, "path": "/companion-catalogue.json", "silent": True, "entries": 323}  # intent moved: E3, E5, I21 (int.catch_midair) and L-chat-7 (react.writing_stretch) added entries


@pytest.mark.parametrize("answer", ["http", "bad", "down"])
def test_a_failed_fetch_keeps_the_built_in_tables(answer: str) -> None:
    out = run(
        f"const was = JSON.stringify(NAME_MARK_BUDDY_ACTS); nmb.cat.load(); {WAIT}"
        "console.log(JSON.stringify({same: was === JSON.stringify(NAME_MARK_BUDDY_ACTS), doc: nmb.cat.state.doc}));",
        ACTS, answer,
    )
    assert out == {"same": True, "doc": None}


def test_the_catalogue_is_served_by_the_local_server(client) -> None:
    # review of atlascat-1108: the reader fetches it from the server, so it is a static file there; the service worker does not precache it
    # because the shell is never cached either (an app without its server shows the offline page), and a failed fetch keeps the built-in tables
    r = client.get("/companion-catalogue.json")
    assert r.status_code == 200 and len(r.json()["entries"]) == 323  # intent moved: E3, E5, I21 (int.catch_midair) and L-chat-7 (react.writing_stretch) added entries
