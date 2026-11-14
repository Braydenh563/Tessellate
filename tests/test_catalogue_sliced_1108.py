"""The companion catalogue is parsed in idle slices, not as one 75 ms task (perfbuddy-1108, P11)."""

from __future__ import annotations

import json

from tests._cat_node import AVATARS, CATALOGUE, run

TEXT = f"const text = require('fs').readFileSync({json.dumps(str(CATALOGUE))}, 'utf8');"


def test_the_sliced_parse_gives_the_same_document_as_one_parse() -> None:
    out = run(
        TEXT
        + "const doc = await new Promise((done, fail) => nmb.cat.slice(text, done, fail));"
        "console.log(JSON.stringify({same: JSON.stringify(doc) === JSON.stringify(JSON.parse(text)), n: doc.entries.length}));"
    )
    assert out == {"same": True, "n": 323}  # intent moved: E3, E5, I21 (int.catch_midair) and L-chat-7 (react.writing_stretch) added entries


def test_the_parse_is_cut_into_slices_of_forty_entries() -> None:
    out = run(
        TEXT
        + "let ticks = 0; const real = setTimeout; globalThis.setTimeout = (f, ms) => { ticks += 1; return real(f, ms); };"
        "const doc = await new Promise((done, fail) => nmb.cat.slice(text, done, fail));"
        "console.log(JSON.stringify({ticks, n: doc.entries.length}));"
    )
    assert out == {"ticks": 8, "n": 323}  # intent moved: E3, E5, I21 (int.catch_midair) and L-chat-7 (react.writing_stretch) added entries


def test_a_text_that_is_not_cut_by_lines_is_parsed_whole() -> None:
    out = run(
        "const doc = await new Promise((done, fail) => nmb.cat.slice('{\"entries\": [{\"id\": 1}]}', done, fail));"
        "console.log(JSON.stringify(doc));"
    )
    assert out == {"entries": [{"id": 1}]}


def test_a_broken_text_fails_and_keeps_the_built_in_tables() -> None:
    out = run(
        "const r = await new Promise((done, fail) => nmb.cat.slice('  \"entries\": [\\nnot json\\n  ]', done, fail)).then(() => 'ok', () => 'failed');"
        "console.log(JSON.stringify(r));"
    )
    assert out == "failed"


def test_the_fetch_waits_for_an_idle_moment_and_reads_text() -> None:
    src = AVATARS.read_text(encoding="utf-8")
    load = src[src.index("    load() {") :][:1500]
    assert "requestIdleCallback(go, { timeout: 3000 })" in load
    assert "answer.text()" in load
