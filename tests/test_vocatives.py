"""What the person calls the assistant (`ai/vocative.py`; the owner,
2026-10-11: "what if I call the composer lil bro, brotato, broski or smth
like that?? can it infer anything I call it is like a name or nickname I
feel like calling it at the time yk??" and "but what if I make up smth random
like brotatockiibidyrizzler yk??").

A name in address position (after a greeting, set off by a comma, at the
start before the question, at the end after it) is taken off before the
question is read: never searched, never a topic, never "corrected". A message
that is only a name, or a greeting and a name, is a call. The gold is
`fixtures/vocatives_gold.json`; its controls are messages where the same
words are what the question is about, and must be left whole."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from tessellate.ai import vocative

GOLD = json.loads((Path(__file__).parent / "fixtures" / "vocatives_gold.json").read_text(encoding="utf-8"))
KNOWN = frozenset(GOLD["known"])

#: Measured 2026-10-11: 38 of 38 addressed and called, 14 of 14 controls whole
#: (before: no message lost its name; every call was searched).
FLOOR = 1.0


def _read(message):
    found = vocative.split(message, known=KNOWN)
    return found.question, found.names, found.call


def test_the_gold_set_is_the_size_asked():
    assert len(GOLD["addressed"]) + len(GOLD["calls"]) >= 30
    assert len(GOLD["controls"]) >= 10
    everywhere = [m for m, *_ in GOLD["addressed"] + GOLD["calls"] if "brotatockiibidyrizzler" in m]
    assert len(everywhere) >= 6
    for word in ("lil bro", "brotato", "broski"):
        assert any(word in m for m, *_ in GOLD["addressed"] + GOLD["calls"]), word


def test_a_name_in_address_position_is_taken_off():
    misses = [(m, want, names, _read(m)) for m, want, names in GOLD["addressed"] if _read(m) != (want, names, False)]
    assert 1 - len(misses) / len(GOLD["addressed"]) >= FLOOR, misses


def test_a_name_alone_is_a_call():
    misses = [(m, _read(m)) for m, names in GOLD["calls"] if _read(m)[1:] != (names, True)]
    assert not misses, misses


def test_the_controls_keep_their_words():
    """The same words as the subject: "what did I say about Bro the dog"."""
    changed = [(m, _read(m)) for m in GOLD["controls"] if _read(m) != (m, [], False)]
    assert not changed, changed


def test_a_nickname_is_never_corrected_or_searched():
    """Taken off before `repair` reads the question, so "brotato" never
    becomes "brother" or "potato" in a question about the dentist."""
    from tessellate.ai import question_noise

    for message in ("brotato what's on today", "hey brotatockiibidyrizzler, what's due this week"):
        read = question_noise.repair(vocative.split(message, known=KNOWN).question)
        assert "bro" not in read and "potato" not in read, read


@pytest.mark.parametrize("message", ["", "   ", "?", "hey", "thanks", "hi there"])
def test_no_name_is_no_change(message):
    found = vocative.split(message)
    assert found.names == [] and not found.call


def test_a_rare_word_the_notes_hold_is_searched():
    """"isekai" alone is a search in a notebook that has it, a call in one
    that does not; "brotatockiibidyrizzler" is a call either way."""
    holds = {"isekai", "dotnet"}.__contains__
    assert not vocative.split("isekai", in_notes=holds).call
    assert not vocative.split("dotnet", in_notes=holds).call
    assert vocative.split("brotatockiibidyrizzler", in_notes=holds).call


def test_a_word_people_say_of_a_thing_is_not_a_name():
    for message in ("how do i find an old chat", "what did we talk about in an earlier chat"):
        assert vocative.split(message).names == [], message


def _stream(client, question, history=()):
    body = {"question": question, "history": list(history), "notes_only": False, "use_tools": False}
    with client.stream("POST", "/chat/stream", json=body) as response:
        events = [json.loads(line) for line in response.iter_lines() if line.strip()]
    text = "".join(e.get("delta", "") for e in events if e.get("type") == "answer")
    return text, [e["offer"] for e in events if e.get("type") == "offer"]


def test_a_call_through_the_route_answers_and_offers_three_asks(client):
    from tessellate.ai import composer, composer_replies

    text, offers = _stream(client, "yo brotatockiibidyrizzler")
    lines = {line.replace("{name}", "Brotatockiibidyrizzler") for line in composer_replies.CALL["natural"]}
    assert text in lines, text
    assert offers and offers[0]["kind"] == "ask" and len(offers[0]["asks"]) == 3
    assert set(offers[0]["asks"]) <= set(composer_replies.CALL_ASKS)
    assert composer.call_asks("x") == composer.call_asks("x")


def test_a_nickname_on_small_talk_is_small_talk(client):
    from tessellate.ai import composer

    text, _offers = _stream(client, "thanks legend")
    assert any(text.startswith(line) for line in composer.SOCIAL["thanks"]), text


def test_the_chips_are_drawn_by_the_follow_up_strip():
    root = Path(__file__).resolve().parents[1] / "frontend" / "js"
    ask = (root / "capture-ask.js").read_text(encoding="utf-8")
    chat = (root / "chat-attach.js").read_text(encoding="utf-8")
    compose = (root / "ask-compose.js").read_text(encoding="utf-8")
    body = compose[compose.index("function digestOffer"):]
    #: In Chat the bubble's own strip, saved later by `offerFollowups` (a save
    #: here raced the turn's own and emptied the reply, INBOX 1300 C42); in
    #: Ask the strip drawn next, which takes the asks it was left.
    assert "renderFollowups(bubble, offer.asks);" in body and "saveFollowups(" not in body.split("\n}\n")[0]
    assert "given = given || askOfferAsks;" in compose
    #: Both are drawn after the offer: the offer first, the strip after.
    assert ask.index("digestOffer(answerBox, answerOffer)") < ask.index("const followups = () => renderAskFollowups")
    assert "digestOffer([...bubble.querySelectorAll" in chat


def test_an_emoticon_is_not_a_name():
    """"hey :D" answered "Ha, D." (owner, 2026-10-12)."""
    for text in ("hey :D", "hey :)", "hello xD", "yo ;P", "hi <3"):
        said = vocative.split(text)
        assert not said.names, (text, said)
