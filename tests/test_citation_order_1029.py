"""Citation numbers run in the order the answer first cites its notes (audit
1029 rank 49, C49, INBOX 1420: markers read 3, 2, 1, 1, 4, 5).

The failure class: a number was a note's place in a list ranked by relevance,
so the prose met them in any order and a screen reader heard 3 before 1.
Every surface that draws a marker, a chip or a row takes the same list from
`chatSourcesFrom`, which now puts the cited notes first, in first-mention
order. Three kinds of check:

- the ordering function itself, run in node over the shapes of the class
  (rank order against text order, a repeated note, a note cited twice with
  others between, a web page that keeps its place, uncited notes after, a
  sentence naming two notes, no sentences at all);
- every call site that numbers anything passes the grounded sentences, so a
  surface cannot fall back to relevance order;
- the backend sends grounding rows in the order their sentences sit in the
  answer, which is what "first mention" is read from (composed, Ask and Chat).
"""

from __future__ import annotations

import datetime as dt
import json
import re
import shutil
import subprocess
from pathlib import Path

import pytest

from tessellate.api import routes_chat
from tessellate.core import config
from tessellate.entry import manager
from tests.test_composer_frames_1029 import FAMILIES, _notes, _questions
from tests.test_composer_route_688 import _ask

ROOT = Path(__file__).resolve().parents[1]
JS = ROOT / "frontend" / "js"
NOW = dt.datetime(2026, 10, 29, 10, 0, 0)


def _fn(text: str, name: str) -> str:
    start = text.index(f"function {name}(")
    return text[start : text.index("\n}\n", start) + 2]


def _run(cases: list[dict]) -> list:
    agent = (JS / "chat-agent.js").read_text(encoding="utf-8")
    ask = (JS / "capture-ask.js").read_text(encoding="utf-8")
    script = (
        _fn(agent, "sourcesByFirstMention")
        + _fn(ask, "citationNumbers")
        + f"""
const cases = {json.dumps(cases)};
console.log(JSON.stringify(cases.map((c) => {{
  const ordered = sourcesByFirstMention(c.sources, c.sentences);
  const numbers = citationNumbers(c.sentences, ordered);
  return {{ order: ordered.map((s) => s.id), marks: c.sentences.map((g) => numbers.get(g.note_id)) }};
}})));"""
    )
    out = subprocess.run(["node", "-e", script], capture_output=True, text=True, check=True).stdout
    return json.loads(out)


def _notes_list(*ids):
    return [{"kind": "note", "id": i} for i in ids]


def _rows(*ids):
    return [{"note_id": i, "sentence": f"sentence number {n} of the answer"} for n, i in enumerate(ids)]


@pytest.mark.skipif(not shutil.which("node"), reason="needs node")
def test_markers_read_one_two_three_whatever_the_relevance_rank():
    cases = [
        # the audit's own run: ranks 3, 2, 1, 1, 4, 5 in text order
        {"sources": _notes_list(1, 2, 3, 4, 5), "sentences": _rows(3, 2, 1, 1, 4, 5)},
        {"sources": _notes_list(1, 2, 3, 4, 5, 6), "sentences": _rows(3, 2, 4, 1, 1, 1)},
        # already in order stays in order
        {"sources": _notes_list(1, 2, 3), "sentences": _rows(1, 2, 3)},
        # a note met again after others keeps its first number
        {"sources": _notes_list(7, 8, 9), "sentences": _rows(9, 8, 9, 7, 8)},
        # nothing cited: the panel order is untouched
        {"sources": _notes_list(4, 5), "sentences": []},
        # cited notes the panel does not list are numbered after the listed ones
        {"sources": _notes_list(1, 2), "sentences": _rows(2, 99, 1)},
    ]
    got = _run(cases)
    assert [g["marks"] for g in got][:4] == [[1, 2, 3, 3, 4, 5], [1, 2, 3, 4, 4, 4], [1, 2, 3], [1, 2, 1, 3, 2]]
    assert got[4]["order"] == [4, 5]
    #: Uncited notes follow the cited ones, in their old order.
    assert got[1]["order"] == [3, 2, 4, 1, 5, 6]
    assert got[0]["order"] == [3, 2, 1, 4, 5]
    #: 99 is not in the panel: after the listed notes, as before.
    assert got[5]["marks"] == [1, 3, 2]


@pytest.mark.skipif(not shutil.which("node"), reason="needs node")
def test_a_web_page_and_a_file_keep_their_place_and_notes_fill_the_note_places():
    sources = [{"kind": "web", "id": "w"}, {"kind": "note", "id": 1}, {"kind": "file", "id": "f"}, {"kind": "note", "id": 2}, {"kind": "note", "id": 3}]
    got = _run([{"sources": sources, "sentences": _rows(3, 1)}])[0]
    assert got["order"] == ["w", 3, "f", 1, 2]
    #: The number is the place in the list, as the panel draws it.
    assert got["marks"] == [2, 4]


@pytest.mark.skipif(not shutil.which("node"), reason="needs node")
def test_the_ordering_is_prefix_stable_so_a_live_digit_is_the_one_it_keeps():
    sources = _notes_list(1, 2, 3, 4)
    full = _rows(3, 1, 4, 2)
    steps = _run([{"sources": sources, "sentences": full[:k]} for k in (1, 2, 3, 4)])
    for k, step in enumerate(steps, 1):
        assert step["marks"] == [1, 2, 3, 4][:k]


def test_every_surface_numbers_from_the_sentences_it_marks():
    """A surface that omitted `sentences` would fall back to relevance order and
    disagree with the others (the failure this row is)."""
    calls = {
        "chat-attach.js": 2,  # live and final
        "capture-ask.js": 2,  # live and the answer object
        "palette.js": 1,  # the popup's markers
    }
    for name, expected in calls.items():
        text = (JS / name).read_text(encoding="utf-8")
        found = [m.group(0) for m in re.finditer(r"chatSourcesFrom\(\{[^}]*\}\)|chatSourcesFrom\(savedInput\)", text)]
        with_sentences = [c for c in found if "sentences" in c]
        assert len(with_sentences) >= expected, (name, found)
    saved = (JS / "sheets-selects.js").read_text(encoding="utf-8")
    assert "sentences: message.sentence_grounding" in saved
    #: The popup's sources list is numbered from the same rows as its markers.
    assert "sentences: cites });" in (JS / "palette.js").read_text(encoding="utf-8")
    #: The live path recomputes on every event: a list cached at the first
    #: sentence would number later ones by relevance.
    for name in ("chat-attach.js", "capture-ask.js"):
        assert "liveSources ??= chatSourcesFrom" not in (JS / name).read_text(encoding="utf-8")


@pytest.fixture
def composed(client, session, monkeypatch):
    monkeypatch.setattr(config, "user_now", lambda _c: NOW)
    monkeypatch.setattr(routes_chat, "user_now", lambda _c: NOW)

    def build(fam, chat: bool):  # noqa: ANN001
        for text, when in _notes(fam):
            entry = manager.create_entry(session, text, "Personal")
            entry.created_at = entry.updated_at = when
        session.commit()
        kw = {} if chat else {"notes_only": True, "answer_from": "notes"}
        return [(q, _ask(client, q, **kw)) for q in _questions(fam)]

    return build


@pytest.mark.parametrize("chat", [False, True], ids=["ask", "chat"])
@pytest.mark.parametrize("fam", FAMILIES, ids=[f[0] for f in FAMILIES])
def test_grounding_rows_come_in_the_order_their_sentences_sit_in_the_answer(composed, fam, chat):
    bad = []
    seen = 0
    for q, out in composed(fam, chat):
        text = out["text"]
        for event in out.get("grounding", []):
            at = [text.find(row["sentence"]) for row in event["sentences"] if row.get("sentence")]
            at = [a for a in at if a != -1]
            seen += len(at)
            if at != sorted(at):
                bad.append(f"{q}: {at}\n{text}")
    assert seen > 10
    assert not bad, "\n\n".join(bad)
