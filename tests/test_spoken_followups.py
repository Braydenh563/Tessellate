"""Conversation (CHAT_PLAN decision 59, step 3; decision 58's context
column; Brief 84): a spoken follow-on ("and delete it", "same for Tuesday",
"same again", "the gym note too", "the other one") is read, with no model,
as the sentence it stands for over the chat's last five turns. The 200
lines are `tests/fixtures/composer/spoken_1010.json`.
"""

from __future__ import annotations

import json
from collections import Counter
from datetime import datetime
from pathlib import Path

from tessellate.ai import reading
from tests._app_js import with_pieces

DATA = json.loads((Path(__file__).parent / "fixtures" / "composer" / "spoken_1010.json").read_text(encoding="utf-8"))
NOW = datetime.fromisoformat(DATA["now"])


def right(row: dict) -> bool:
    got = reading.read(row["text"], now=NOW, context={"turns": row["turns"]})
    if got.intent != row["intent"]:
        return False
    if "about" in row and str(got.slots.get("about") or got.slots.get("subject") or "").lower() != row["about"]:
        return False
    if "due_at" in row and (got.slots.get("due_at") is None or got.slots["due_at"].isoformat() != row["due_at"]):
        return False
    return "since" not in row or str(got.slots.get("since")) == row["since"]


def test_the_corpus_is_200_lines_over_five_turns():
    assert len(DATA["rows"]) == 200
    assert all(1 <= len(row["turns"]) <= reading.FOLLOW_TURNS for row in DATA["rows"])
    assert Counter(row["kind"] for row in DATA["rows"]) == {"pronoun": 60, "date": 50, "again": 30, "subject": 30, "other": 30}


def test_every_spoken_followup_resolves():
    missed = [(row["text"], row["turns"][-1]["text"]) for row in DATA["rows"] if not right(row)]
    assert missed == []


def test_a_resolved_followup_says_what_it_read():
    got = reading.read("and delete it", now=NOW, context={"turns": [{"text": "find my note about the passport"}]})
    assert got.intent == "delete" and got.slots["follows"] == "pronoun"
    assert got.said == "Read as “delete the passport note”." and got.tool == "delete_note"


def test_a_sentence_that_stands_alone_is_not_rewritten():
    turns = [{"text": "pin the dentist note"}]
    assert reading.follow("what did I write about the boiler", turns, NOW) is None
    assert reading.follow("and delete it", [], NOW) is None
    assert reading.read("delete it", now=NOW).slots.get("follows") is None


def test_small_talk_between_is_not_leaned_on():
    turns = [{"text": "what did I write on Monday"}, {"text": "thanks"}]
    assert reading.follow("same again", turns, NOW) == ("what did I write on Monday", "again")


def test_chat_with_no_model_acts_on_a_spoken_followup(ai_client, fake_ollama, session):
    from tessellate.ai import tools

    fake_ollama.running = False
    tools.execute_tool(session, "create_note", {"content": "Passport renewal: forms in the drawer"})
    session.commit()
    history = [{"question": "find my note about the passport", "answer": "One note matches: Passport renewal."}]
    events = []
    with ai_client.stream("POST", "/chat/stream", json={"question": "and delete it", "use_tools": True, "history": history}) as response:
        for line in response.iter_lines():
            if line.strip():
                events.append(json.loads(line))
    card = next(e for e in events if e["type"] == "act")
    assert card["steps"] == [{"name": "delete_note", "arguments": {"note_id": 1}}]
    assert "Passport renewal" in card["label"]


def test_the_other_one_reads_the_titles_chat_sends(ai_client, fake_ollama, session):
    """OPEN row 564: chat-attach.js puts each answer's note titles on its
    history turn, and "the other one" names the title the turn did not."""
    from tessellate.ai import tools

    fake_ollama.running = False
    tools.execute_tool(session, "create_note", {"content": "Passport renewal: forms in the drawer"})
    tools.execute_tool(session, "create_note", {"content": "Budget 2026: the rent goes up in March"})
    session.commit()
    history = [{"question": "find my note about the passport", "answer": "Two notes match.",
                "objects": ["Passport renewal", "Budget 2026"]}]
    events = []
    with ai_client.stream("POST", "/chat/stream", json={"question": "delete the other one", "use_tools": True, "history": history}) as response:
        for line in response.iter_lines():
            if line.strip():
                events.append(json.loads(line))
    card = next(e for e in events if e["type"] == "act")
    assert card["steps"] == [{"name": "delete_note", "arguments": {"note_id": 2}}]


def test_chat_sends_an_answers_note_titles_on_its_turn():
    import subprocess

    js = with_pieces("chat-attach.js")
    start = js.index("function chatTurnObjects")
    fn = js[start:js.index("\n}\n", start) + 2]
    probe = fn + """
console.log(JSON.stringify(chatTurnObjects([
  { kind: "note", label: "Passport renewal: forms in the drawer" },
  { kind: "web", label: "A page" },
  { kind: "note", label: "Budget 2026 and the rent going up in Ma…" },
])));"""
    out = subprocess.run(["node", "-e", probe], capture_output=True, text=True, check=True).stdout
    assert json.loads(out) == ["Passport renewal", "Budget 2026 and the rent going up in Ma"]
    assert "objects: chatTurnObjects(turnSources)" in js
