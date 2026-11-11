"""The owner (INBOX 1746): "why are there dimmed notes and then there are
brighter ones below them??" Matching records 12 to 14 were link-only notes and
sat above direct matches 15 and 16. The search already sends direct matches
first (`direct_before_linked`); the cards were then numbered, and sorted, by
the order the answer first cites them (`sourcesByFirstMention`), so a link-only
note the answer met early took a low number and the card list put it above a
direct match cited later. Numbers now run first-mention within a tier: direct
matches, then notes one link away, then two. Nothing is cited out of a tier's
own order, so the audit 1029 rule (a screen reader hears 1 before 2) holds
inside each."""

from __future__ import annotations

import json
import shutil
import subprocess

import pytest

from tests._app_js import with_pieces


def _fn(text: str, name: str) -> str:
    start = text.index(f"function {name}(")
    return text[start : text.index("\n}\n", start) + 2]


def _run(cases: list[dict]) -> list:
    agent = with_pieces("chat-agent.js")
    script = (
        _fn(agent, "sourcesByFirstMention")
        + _fn(agent, "citeKey")
        + f"""
const cases = {json.dumps(cases)};
console.log(JSON.stringify(cases.map((c) => sourcesByFirstMention(c.sources, c.sentences).map((s) => s.id))));"""
    )
    return json.loads(subprocess.run(["node", "-e", script], capture_output=True, text=True, check=True).stdout)


def _src(i, tier=0):
    return {"kind": "note", "id": i, "tier": tier}


def _rows(*ids):
    return [{"note_id": i, "sentence": f"sentence number {n} of the answer"} for n, i in enumerate(ids)]


@pytest.mark.skipif(not shutil.which("node"), reason="needs node")
def test_a_linked_note_cited_early_never_takes_a_place_above_a_direct_match():
    sources = [_src(15), _src(16), _src(12, 1), _src(13, 1), _src(14, 2)]
    got = _run([{"sources": sources, "sentences": _rows(12, 13, 14, 15, 16)}])[0]
    assert got == [15, 16, 12, 13, 14], "direct first, one step before two"


@pytest.mark.skipif(not shutil.which("node"), reason="needs node")
def test_first_mention_still_orders_each_tier_and_uncited_follow_their_tier():
    sources = [_src(1), _src(2), _src(3), _src(4, 1), _src(5, 1), _src(6)]
    got = _run([{"sources": sources, "sentences": _rows(5, 3, 4, 1)}])[0]
    assert got == [3, 1, 2, 6, 5, 4], "cited direct (3, 1), uncited direct (2, 6), then linked (5, 4 by mention)"


@pytest.mark.skipif(not shutil.which("node"), reason="needs node")
def test_with_no_linked_notes_the_order_is_the_old_one():
    sources = [_src(1), _src(2), _src(3)]
    assert _run([{"sources": sources, "sentences": _rows(3, 1)}])[0] == [3, 1, 2]


def test_a_source_card_knows_how_far_its_note_is():
    body = _fn(with_pieces("chat-agent.js"), "chatSourcesFrom")
    assert "connected_ids" in body and "connected_2hop" in body and "tier" in body
