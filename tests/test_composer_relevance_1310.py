"""INBOX 1310 (the owner, 2026-10-19): with no model, "What have I saved
about hobbies?" listed every note with no frame of reference: how related
each shown record is, why it was shown, how the shown notes link; and the
grammar and the date words were rough ("One weeks on, by 27 July, **Gym
Routine Overview**. Go to the gym ...")."""

from __future__ import annotations

import json
import re
from datetime import date, datetime

from tessellate.ai import composer_digest, composer_frame
from tessellate.entry import manager

TODAY = date(2026, 10, 19)

HOBBIES = [
    ("Hobbies: thinking of buying the Logitech G Pro gaming mouse, it is $129 right now", "Hobbies", ["gaming", "shopping"], "2026-07-20T18:00:00"),
    ("Gym Routine Overview\nPull: rows, pull-ups\nPush: bench, dips\nLegs: squats, lunges\nRest Day\nPull: deadlifts\nPush: overhead press\nRest Day", "Hobbies", ["gym", "fitness"], "2026-07-27T09:00:00"),
    ("Go to the gym at 9pm on Tuesday, legs day", "Hobbies", ["gym", "fitness"], "2026-08-03T12:00:00"),
    ("League of Legends: my mains are Ahri and Jinx, playing ranked with Sam", "Hobbies", ["gaming"], "2026-08-09T20:00:00"),
    ("Movie review: Dune Part Two was stunning, the sound design was huge", "Hobbies", ["movies"], "2026-08-30T21:00:00"),
    ("Pokemon image: my favourite Charizard card scan", "Hobbies", ["pokemon", "gaming"], "2026-09-14T15:00:00"),
    ("Golf practice after work, hit a bucket of balls at the range", "Hobbies", ["golf"], "2026-10-12T17:00:00"),
    ("Study notes: biology cell structure, mitochondria and ribosomes", "Study", ["biology"], "2026-10-05T10:00:00"),
    ("A joke: why did the scarecrow win an award? He was outstanding in his field", "Fun", ["jokes"], "2026-09-20T10:00:00"),
    ("Pickup lines: are you a parking ticket? Because you have fine written all over you", "Fun", ["pickup lines"], "2026-09-21T10:00:00"),
]


def _ask(client, question: str) -> dict:
    events: dict[str, list] = {}
    with client.stream("POST", "/chat/stream", json={"question": question, "answer_from": "notes", "notes_only": True, "use_tools": False}) as response:
        assert response.status_code == 200
        for line in response.iter_lines():
            if line.strip():
                event = json.loads(line)
                events.setdefault(event["type"], []).append(event)
    events["text"] = "".join(e["delta"] for e in events.get("answer", []))
    return events


def _seed(session) -> list[int]:
    ids = []
    for content, category, tags, when in HOBBIES:
        entry = manager.create_entry(session, content, category, tags)
        entry.created_at = datetime.fromisoformat(when)
        ids.append(entry.id)
    session.commit()
    return ids


def _notes(links: dict[int, list[int]] | None = None, score: dict[int, float] | None = None) -> list[dict]:
    out = []
    for n, (content, category, tags, when) in enumerate(HOBBIES, start=1):
        info = {"type": "semantic", "score": (score or {}).get(n, 0.7)}
        out.append({"id": n, "content": content, "category": category, "tags": tags, "created_at": when,
                    "match_info": info, "linked_to": (links or {}).get(n, [])})
    return out


def _hobbies(notes: list[dict] | None = None) -> str:
    #: The owner's search: the seven hobbies notes matched (and cited).
    notes = (notes or _notes())[:7]
    return composer_digest.answer("What have I saved about hobbies?", notes, today=TODAY)["text"]


def test_the_answer_groups_its_notes_by_theme_and_says_why_each_group_answers():
    text = _hobbies()
    paragraphs = text.split("\n\n")
    gym = next(i for i, p in enumerate(paragraphs) if "gym notes go together" in p.lower())
    gaming = next(i for i, p in enumerate(paragraphs) if "gaming notes" in p.lower() and "#gaming" in p)
    loose = next(i for i, p in enumerate(paragraphs) if "loosely" in p.lower())
    #: Equal scores: the bigger theme first; the loose notes last.
    assert gaming < gym < loose, text
    #: Each group's line says why it answers: what joins it, and its notes.
    assert "#gym" in paragraphs[gym] and "Gym Routine Overview" in paragraphs[gym], paragraphs[gym]
    assert "movie review" in paragraphs[loose].lower() and "golf" in paragraphs[loose].lower(), paragraphs[loose]
    #: The gym notes are told together, under their line, not by date order.
    legs = next(i for i, p in enumerate(paragraphs) if "9pm on Tuesday, legs" in p)
    assert gym < legs < loose, text


def test_a_link_between_two_shown_notes_is_said_in_one_line():
    text = _hobbies(_notes(links={4: [6], 6: [4]}))
    assert re.search(r"you linked (?:your|the) League of Legends .* to (?:your|the) Pokemon image", text, re.I) or "linked" in text.lower(), text
    groups = composer_frame.themes(_notes(links={5: [7]})[:7])
    joined = next(g for g in groups if 5 in g.ids)
    assert 7 in joined.ids and "linked" in joined.joined_by, joined


def test_the_closest_group_leads_when_scores_differ():
    text = _hobbies(_notes(score={1: 0.5, 2: 0.82, 3: 0.8, 4: 0.5, 5: 0.3, 6: 0.5, 7: 0.31}))
    first = next(p for p in text.split("\n\n")[1:])
    assert "closest" in first.lower() and "gym" in first.lower(), text


def test_each_record_carries_a_reason_in_words():
    notes = _notes(links={2: [3], 3: [2]})
    why = composer_frame.reasons("What have I saved about hobbies?", notes)
    assert set(why) == {str(n["id"]) for n in notes}
    assert all(w and w[0].isupper() and not w.endswith(".") for w in why.values()), why
    assert "by meaning" in why["1"] and "hobbies" in why["1"], why["1"]
    assert "Gym Routine Overview" in why["3"] and "linked" in why["3"].lower(), why["3"]
    assert "#gaming" in why["6"], why["6"]
    keyword = composer_frame.reasons("hobbies", [{"id": 9, "content": "Golf", "category": "Hobbies", "tags": [], "match_info": {"type": "keyword", "terms": ["hobbies"]}}])
    assert "Hobbies" in keyword["9"] or "hobbies" in keyword["9"], keyword
    linked = composer_frame.reasons("x", [{"id": 1, "content": "Gym Routine Overview", "tags": []}, {"id": 2, "content": "Legs", "tags": [], "match_info": {"type": "connected", "reason": "same plan"}, "linked_to": [1]}])
    assert "Gym Routine Overview" in linked["2"], linked


def test_the_owners_grammar_and_dates(monkeypatch):
    text = _hobbies()
    plain = re.sub(r"\*\*", "", text)
    assert "One weeks" not in plain and "one weeks" not in plain, plain
    assert "gym Routine" not in plain and "league of Legends" not in plain, plain
    #: A title is said as what was saved, never dropped in as a fragment.
    assert not re.search(r", Gym Routine Overview\.", plain), plain
    assert "you saved your Gym Routine Overview" in plain, plain
    #: A repeated schedule is said as its shape, each day once.
    assert "a Pull, Push, Legs split with rest days" in plain, plain
    assert "Pull, Push, Legs, Rest Day, Pull" not in plain and "Your pull note" not in plain.lower(), plain
    #: A label that only repeats the category is not a note's name.
    assert "hobbies note" not in plain.lower() and "note your" not in plain.lower(), plain
    assert "you were thinking of buying" in plain, plain
    #: Time openers vary, and a recent day is said as a person says it.
    openers = re.findall(r"(?:^|\n\n)((?:A|An|About|After|Two|Three|One)[^,]*?(?:later|on|after \w+ \w+)),", plain)
    assert len(openers) == len(set(o.split()[-1] for o in openers)), openers
    assert "A week ago, on 12 October, you" in plain, plain
    assert "stunning, and the sound design was huge" in plain, plain


def test_gap_words_agree():
    assert composer_digest._gap(10) == "a week"
    assert all("one weeks" not in composer_digest._gap(d) for d in range(1, 400))


def test_the_route_sends_a_reason_on_every_matching_record(ai_client, session):
    _seed(session)
    events = _ask(ai_client, "What have I saved about hobbies?")
    meta = events["meta"][0]
    shown = [r["id"] for r in meta["raw_results"]]
    assert shown, meta
    for i in shown:
        assert (meta["match_info"].get(str(i)) or {}).get("why"), (i, meta["match_info"])
