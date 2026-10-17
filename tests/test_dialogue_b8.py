"""Dialogue memory over five turns (CHAT_PLAN B8): "and last month?", "the
second one", "when was that?", "what about running?", "tell me more", each
read against the turns before, through the route, with no model.

The row's bar is a 5-turn eval. Each conversation below is five turns; each
turn names words its answer must hold and words it must not (the turn
before's subject leaking into the next, or a follow-up searched as if it
stood alone). Run as one test a conversation so a failure names its turn.
"""

from __future__ import annotations

import json
from datetime import datetime, timedelta

import pytest

from tessellate.core.database import Entry
from tessellate.entry import manager

TODAY = datetime.now().replace(hour=10, minute=0, second=0, microsecond=0)


def _days_ago(n: int) -> datetime:
    return TODAY - timedelta(days=n)


def _day(n: int) -> str:
    d = _days_ago(n)
    return f"{d.day} {d.strftime('%B')}"


#: Filed as the app files them (a tag a topic): "what about running?" finds
#: "Ran 5k" by its tag, since search does not read "ran" as "run" (found,
#: not fixed: `factgraph._IRREGULAR` has the table, search does not use it).
NOTEBOOK = [
    ("Gym: squats at 80 kg, 3 sets of 5.", 50, ["gym"]),
    ("Gym: squats up to 90 kg, bench still 60 kg.", 10, ["gym"]),
    ("Ran 5k in 29 minutes along the river.", 45, ["running"]),
    ("Ran 5k in 27 minutes, felt easy.", 8, ["running"]),
    ("Watched Dune Part Two: 7 out of 10, the sound design was incredible.", 30, ["films"]),
    ("Watched Oppenheimer: 9 out of 10, the score carried it.", 12, ["films"]),
    ("Psych lecture: memory is reconstructive, not a recording.", 20, ["uni", "psych"]),
    ("Data Structures lab: linked lists working, still shaky on big O.", 18, ["uni"]),
]

#: (question, must hold, must not hold) a turn.
CONVERSATIONS = {
    "gym, a window, running and back": [
        #: O11: the 7 October squat is current, the 28 August one is said as earlier.
        ("what have I saved about the gym?", ["90 kg", "earlier note", "80 kg"], []),
        ("what about running?", ["5k", "two notes"], ["squat"]),
        ("when was that?", ["minutes"], ["squat"]),
        ("and the gym?", ["kg"], ["5k"]),
        #: Both gym notes were said by now: it says so and stays on the gym.
        ("tell me more", ["all your notes say on gym", "two notes"], ["5k"]),
    ],
    "films": [
        ("what did I think of Dune?", ["7 out of 10", "Loved"], ["Part Two: 7"]),
        ("when was that?", ["Dune", _day(30)], ["Oppenheimer"]),
        ("and Oppenheimer?", ["9 out of 10", _day(12)], ["7 out of 10"]),
        ("why?", ["score"], ["Dune"]),
        ("what about Dune?", ["7 out of 10"], ["9 out of 10"]),
    ],
    "uni with a correction": [
        ("what have I saved about uni?", ["memory is reconstructive", "linked lists"], []),
        ("no, the data structures one", ["linked lists"], ["reconstructive"]),
        ("shorter", ["linked lists"], ["reconstructive"]),
        ("what about psych?", ["reconstructive"], ["linked lists"]),
        #: Everything was said: it says so, never "nothing answers that".
        ("tell me more", ["all your notes say on psych", "one note"], ["Nothing in the notes"]),
    ],
}


def _seed(session) -> None:
    for content, ago, tags in NOTEBOOK:
        made = manager.create_entry(session, content, tags=tags)
        session.flush()
        entry = session.get(Entry, made.id)
        entry.created_at = entry.updated_at = _days_ago(ago)
    session.commit()


def _turn(client, question: str, history: list[dict]) -> str:
    body = {"question": question, "history": history, "notes_only": True, "use_tools": False, "answer_from": "notes"}
    with client.stream("POST", "/chat/stream", json=body) as response:
        assert response.status_code == 200
        events = [json.loads(line) for line in response.iter_lines() if line.strip()]
    return "".join(e.get("delta", "") for e in events if e.get("type") == "answer")


@pytest.mark.parametrize("name", list(CONVERSATIONS))
def test_five_turns_read_against_the_turns_before(client, session, name):
    _seed(session)
    history: list[dict] = []
    failed = []
    for n, (question, must, never) in enumerate(CONVERSATIONS[name], start=1):
        text = _turn(client, question, history)
        low = text.lower()
        missing = [w for w in must if w.lower() not in low]
        leaked = [w for w in never if w.lower() in low]
        if missing or leaked:
            failed.append(f"turn {n} {question!r}: missing {missing}, leaked {leaked}: {text[:160]!r}")
        history.append({"question": question, "answer": text})
    assert not failed, "\n".join(failed)

