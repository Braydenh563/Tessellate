"""Where is it, with a link that opens it (`ai/find_it.py`; the owner,
2026-10-11: "It should be able to produce nav links if the user can't find
smth"). The gold set is `fixtures/find_it_gold.json`: 40 where-is questions
in people's words and typos, each with the one place it should open, and
questions that name no place and must get no link."""

from __future__ import annotations

import json
import re
from pathlib import Path

from tessellate.ai import find_it
from tests._app_js import with_pieces

ROOT = Path(__file__).resolve().parents[1]
GOLD = json.loads((ROOT / "tests" / "fixtures" / "find_it_gold.json").read_text(encoding="utf-8"))

#: Measured 2026-10-11: 40 of 40 (0 before: no answer carried a link).
FLOOR = 0.95


def _opened(question: str) -> list[str] | None:
    found = find_it.answer(question)
    return found["places"] if found else None


def test_the_gold_where_questions_open_their_place():
    misses = [(q, want, _opened(q)) for q, want, _manual in GOLD["places"] if _opened(q) != [want]]
    hit = 1 - len(misses) / len(GOLD["places"])
    assert len(GOLD["places"]) >= 40
    assert hit >= FLOOR, misses


def test_a_question_that_names_no_place_gets_no_link():
    linked = [(q, _opened(q)) for q in GOLD["none"] if _opened(q)]
    assert not linked, linked


def test_the_manual_paths_are_in_the_gold_set():
    """Every manual path the gold names is one `test_manual_parity.py` keeps."""
    manual = (ROOT / "tests" / "test_manual_parity.py").read_text(encoding="utf-8")
    named = {m for _q, _w, m in GOLD["places"] if m}
    assert len(named) >= 12
    for tool in named:
        assert f'"{tool}":' in manual, tool


def test_every_place_lands_somewhere_real():
    """A reveal key is one `revealFeature` knows; a Settings section is one
    the Settings window has; a tab is a tab."""
    reveal = (ROOT / "frontend" / "js" / "reveal-targets.js").read_text(encoding="utf-8")
    keys = set(re.findall(r'^  "?([a-z0-9-]+)"?: \{', reveal[reveal.index("const REVEAL_TARGETS"):], re.M))
    html = (ROOT / "frontend" / "index.html").read_text(encoding="utf-8")
    sections = set(re.findall(r'data-section="([a-z]+)"', html))
    places = find_it.places()
    assert len(places) >= 140
    for place in places:
        kind, _, rest = place.key.partition(":")
        if kind == "reveal":
            assert rest.split(":")[0] in keys, place.key
        elif kind == "settings" and rest:
            assert rest in sections, place.key
        elif kind == "tab":
            assert f'data-tab="{rest}"' in html, place.key


def test_the_link_is_the_answer_s_last_line():
    """`digestOffer` turns the paragraph that is the offer's label into the
    link, so the label must be a line of its own; a choice is one per line."""
    one = find_it.answer("where is the recycle bin")
    assert one["text"].split("\n\n")[-1] == one["offer"]["label"] == "Show me Bin"
    assert one["offer"]["surface"] == "reveal:recycle-bin"
    assert one["text"].startswith("You'll find Bin in the Library tab.")
    choice = find_it.answer("where do I find export")
    assert choice is not None
    labels = [choice["offer"]["label"], *(o["label"] for o in choice["offer"].get("also", []))]
    assert all(label in choice["text"].split("\n\n") for label in labels)


def test_answers_keep_the_house_style():
    for question, _want, _manual in GOLD["places"]:
        text = find_it.answer(question)["text"]
        assert chr(0x2014) not in text and "!" not in text, question


def test_through_the_route_with_no_model(client):
    body = {"question": "wheres the trash", "history": [], "notes_only": True, "use_tools": False, "answer_from": "notes"}
    with client.stream("POST", "/chat/stream", json=body) as response:
        events = [json.loads(line) for line in response.iter_lines() if line.strip()]
    text = "".join(e.get("delta", "") for e in events if e.get("type") == "answer")
    assert "Library tab" in text
    offer = next(e["offer"] for e in events if e.get("type") == "offer")
    assert offer["surface"] == "reveal:recycle-bin"


def test_the_page_opens_a_reveal_link_and_a_choice():
    js = (ROOT / "frontend" / "js" / "ask-compose.js").read_text(encoding="utf-8")
    body = js[js.index("function digestOffer"):js.index("//: **Wrong fact and Pin as true")]
    assert 'offer.surface.startsWith("reveal:")' in body and "revealFeature(" in body
    assert "offer.also" in body
    chat = with_pieces("chat-attach.js")
    assert "onOffer:" in chat and "digestOffer(" in chat
