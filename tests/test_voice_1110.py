"""The composer sounds like a person, not a table (INBOX 1730; fable-composer-1110 F7, F10, F11).

Twenty-five scripted dialogues (`fixtures/composer/voice_1110.json`, the audit's
own, over its 36-note notebook) are asked through `/chat/stream` with no model,
at the fixed clock Tuesday 10 November 2026 09:00, and every answer is checked
for the marks the owner called robotic: the phrase-table openers and tails, the
stat lines, the bracketed `[**Title**]` citation (decision D25), a count that
does not agree with its noun, and a title-less note named any way but one.
"""

from __future__ import annotations

import json
import re
from datetime import datetime
from pathlib import Path

import pytest

from tessellate.ai import composer_frame
from tessellate.api import chat_said, chat_turn, routes_chat
from tessellate.entry import manager
from tests.test_composer_route_688 import _ask

FIXTURE = json.loads((Path(__file__).parent / "fixtures" / "composer" / "voice_1110.json").read_text(encoding="utf-8"))
NOW = datetime.fromisoformat(FIXTURE["now"])


@pytest.fixture(autouse=True)
def _fixed_now(monkeypatch):
    for module in (routes_chat, chat_said, chat_turn):
        monkeypatch.setattr(module, "user_now", lambda _config: NOW)


def _seed(session) -> None:
    for made, category, tags, content in FIXTURE["notes"]:
        entry = manager.create_entry(session, content, category_name=category, tags=tags)
        entry.created_at = entry.updated_at = datetime.fromisoformat(made)
    session.commit()


def _chips(events: dict) -> list[str]:
    def asks(offer: dict) -> list[str]:
        own = list(offer.get("asks") or []) if offer.get("kind") == "ask" else []
        return own + [a for other in offer.get("also") or [] for a in asks(other)]

    return [a for e in events.get("offer", []) for a in asks(e["offer"])] + [n for e in events.get("grounding", []) for n in e.get("next") or []]


def _run(client, dialogue: dict) -> list[tuple[str, str]]:
    history: list[dict] = []
    seen: list[tuple[str, str]] = []
    chips: list[str] = []
    for ask in dialogue["turns"]:
        if ask in ("<chip>", "<chip2>"):
            index = 0 if ask == "<chip>" else 1
            if len(chips) <= index:
                continue
            ask = chips[index]
        events = _ask(client, ask, history=list(history[-4:]))
        chips = _chips(events)
        history.append({"question": ask, "answer": events["text"]})
        seen.append((ask, events["text"]))
    return seen


#: What F7 named, by the rule that made it: the paraphrase tables, the verb rotation, the stat lines and the tails.
BANNED = {
    "bracketed citation (D25)": r"\[\*\*[^\]\n]+\*\*\](?!\()",
    "next-step paraphrase": r"Need any further clarification|Should we explore|Would it help to see more notes|continue searching for|check for other mentions|dig up more on|dive deeper|keep digging|always check for more|Tell me if you need anything else|run another search|pull up everything you have|gather all other mentions|anything else about “",
    "missing-word tail": r"None of these (?:records|notes) (?:discuss|mention|say)|notes omit|No note found brings up|notes do not talk about|I don't see any mention of",
    "verb rotation": r"You noted down “|You put down “",
    "opener table": r"Here is your exact note|This is how you put it|Your own words:|This is what you saved|According to your notes|Looking through your notes|closest record|In a different spot|On another note|Separately:|Across your other entries|In another entry|You previously noted",
    "stat line": r"Only one note has those words|The app has a tool for that too|So far this is your only|That keeps coming up",
    "article or number": r"\ba (?:three|two|four|five|goals)\b|Here are your 1 |\b1 dated items?\b|\b0 reminders",
}


def _all_answers(client, session) -> list[tuple[str, str, str]]:
    _seed(session)
    out = []
    for dialogue in FIXTURE["dialogues"]:
        out += [(dialogue["name"], q, a) for q, a in _run(client, dialogue)]
    return out


def test_no_answer_sounds_generated(client, session):
    found = []
    for name, question, answer in _all_answers(client, session):
        for rule, pattern in BANNED.items():
            for match in re.finditer(pattern, answer):
                found.append(f"{rule}: {name} / {question!r}: ...{answer[max(0, match.start() - 40):match.end() + 30]!r}")
    assert not found, "\n".join(found)


def test_no_answer_repeats_its_opener_in_a_row(client, session):
    """Never the same opening words twice running in one chat (voice section, point 5). A whole answer
    repeated is a follow-on bug (F1, F3: `composer_dialogue`), not a wording one, and is left to its own tests."""
    _seed(session)
    for dialogue in FIXTURE["dialogues"]:
        answers = [a.strip() for _q, a in _run(client, dialogue)]
        for before, after in zip(answers, answers[1:]):
            if before == after:
                continue
            opening = lambda text: " ".join(re.sub(r"[“”\"*]", "", text).split()[:3]).lower()  # noqa: E731
            if len(opening(before)) > 12 and re.match(r"(?:you wrote|here is|this is|according|looking|from your|your notes)", opening(before)):
                assert opening(before) != opening(after), (dialogue["name"], before[:60], after[:60])


#: A title-less note is named once: its first clause, about six words, quoted, with an ellipsis when cut (owner 2026-11-10).
UNTITLED = {
    "feeling pretty tired today, slept badly. need to prep for the stats exam this week": "“feeling pretty tired today, slept badly”",
    "landlord called back, plumber is coming thursday between 8 and 10": "“landlord called back, plumber is coming…”",
    "idea: an app that reminds you to water plants based on the weather forecast": "“idea: an app that reminds you…”",
    "harbor standup: Mia says the android build is flaky, retry friday. Priya is waiting on legal": "“harbor standup: Mia says the android…”",
}


@pytest.mark.parametrize(("content", "name"), list(UNTITLED.items()))
def test_a_titleless_note_has_one_name(content, name):
    assert composer_frame.name_of({"content": content}) == name


def test_every_surface_names_a_titleless_note_the_same_way(client, session):
    """Lists, compare and prose: never bare link text, a whole line, three dots, or "Your Harbor standup note"."""
    _seed(session)
    bare = re.compile(r"\[(?:feeling pretty|landlord called|harbor standup|idea: an app)[^\]]*\]\(#/notes/\d+\)", re.I)
    #: A row that is the whole first line and a date ("- idea: an app that reminds you to water plants..., 5 November"): the name is cut.
    whole = re.compile(r"(?:^|\n)- (?:feeling pretty tired|landlord called back|harbor standup:|idea: an app)[^\n(]*, \d{1,2} \w+(?:\n|$)", re.I)
    for ask in ("what's on today", "what did I write this week", "what have I written about harbor", "what have I written about water", "nothing on tennis at all?", "what did I write yesterday"):
        text = _ask(client, ask, history=[])["text"]
        assert not bare.search(text), (ask, text)
        assert not whole.search(text), (ask, text)
        assert "..." not in text, (ask, text)
        assert not re.search(r"[Yy]our [Hh]arbor standup note", text), (ask, text)
