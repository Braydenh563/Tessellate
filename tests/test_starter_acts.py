"""The popup agent with no model is not dead (AGENT_SKILLS_REFORM "Deepened
2026-10-10" row 1): each of the fourteen starters on the dashboard is
answered by the engine, never by "Nothing I found mentions", and every write
arrives as an act card whose steps the registry runs and undoes.
"""

from __future__ import annotations

import json
import re
from datetime import datetime
from pathlib import Path

import pytest

from tessellate.ai import starter_acts
from tessellate.ai import composer_phrases

ROOT = Path(__file__).resolve().parents[1]
FIXTURE = json.loads((ROOT / "tests" / "fixtures" / "composer" / "agent_starters_1010.json").read_text("utf-8"))
STARTERS = FIXTURE["starters"]
#: Every wording of nothing found, in both voices (`composer_replies.NOTHING_FAMILIES`).
FALLBACK = re.compile(
    "|".join(f"^{re.escape(lead)}" for key in ("none_found", "nothing") for lead in composer_phrases.phrase_options(key))
    + r"|^I could not find|^The model wrote nothing"
)


def _events(client, question, **body):
    with client.stream("POST", "/chat/stream", json={"question": question, "use_tools": True, **body}) as r:
        assert r.status_code == 200
        return [json.loads(line) for line in r.iter_lines() if line.strip()]


@pytest.fixture()
def notebook(client):
    topics = ["harbor survey", "boiler pressure", "budget review", "reading list"]
    ids = []
    for i in range(12):
        topic = topics[i % 4]
        body = {"content": f"# {topic.title()} {i}\n\nNotes on the {topic}. Met Sam about the {topic} and the next step.",
                "tags": [topic.split()[0]] if i < 10 else []}
        ids.append(client.post("/entries", json=body).json()["id"])
    client.post("/reminders", json={"text": "Follow up the harbor survey", "due_at": datetime.now().isoformat()})
    return ids


def _body(starter: dict, ids: list[int]) -> dict:
    body = {}
    if starter.get("open_note"):
        body["note_ids"] = [ids[0]]
    if starter.get("history"):
        body["history"] = [{"question": "What is due?", "answer": "One reminder due today."}]
    return body


def _outcome(events: list[dict]) -> str:
    if any(e.get("type") == "act" and e.get("done") for e in events):
        return "done"
    if any(e.get("type") == "act" for e in events):
        return "card"
    if any(e.get("type") == "tool" for e in events):
        return "tool"
    return "answer"


def test_the_fixture_is_the_palettes_starters():
    """The fixture is the set the palette offers, so it cannot drift."""
    js = (ROOT / "frontend" / "js" / "palette.js").read_text("utf-8")
    offered = re.findall(r'label: "([^"]+)", text: "([^"]+)"', js)
    labels = {label for label, _ in offered}
    assert len(STARTERS) == 14
    assert {s["label"] for s in STARTERS} <= labels


@pytest.mark.parametrize("starter", STARTERS, ids=[s["label"] for s in STARTERS])
def test_each_starter_runs_with_no_model(client, notebook, starter):
    events = _events(client, starter["text"], **_body(starter, notebook))
    answer = "".join(e.get("delta", "") for e in events if e.get("type") == "answer").strip()
    assert answer and not FALLBACK.search(answer), answer
    assert _outcome(events) == starter["expect"], (starter["text"], answer)


def test_the_starters_are_at_one(client, notebook):
    """The row's number: 14 of 14 answered by the engine."""
    good = 0
    for starter in STARTERS:
        events = _events(client, starter["text"], **_body(starter, notebook))
        answer = "".join(e.get("delta", "") for e in events if e.get("type") == "answer")
        good += bool(answer.strip()) and not FALLBACK.search(answer.strip()) and _outcome(events) == starter["expect"]
    assert good / len(STARTERS) == 1.0


def test_a_card_runs_through_the_registry_and_undoes(client, notebook):
    """Confirm runs the card's steps (`/chat/command/run`), and its undo
    steps put the notebook back."""
    card = next(e for e in _events(client, "Link notes that belong together.") if e.get("type") == "act")
    first = card["steps"][0]["arguments"]["note_id"]
    links = lambda: len(client.get(f"/entries/{first}").json()["links"])  # noqa: E731
    before = links()
    done = client.post("/chat/command/run", json={"steps": card["steps"]}).json()
    assert done["ok"] and done["undo"]
    assert links() == before + 1
    client.post("/chat/command/run", json={"steps": done["undo"]})
    assert links() == before


def test_with_a_model_the_starter_is_the_agents(ai_client):
    """The engine answers only when no model can: with one, nothing here runs."""
    assert starter_acts.read("What is due?") == ("due", {})
    events = _events(ai_client, "What is due?")
    assert not any("Nothing is due" in e.get("delta", "") for e in events if e.get("type") == "answer")


def test_a_question_that_is_no_starter_is_not_read():
    for text in ("what did I write about pasta", "tag the knife note with kitchen", "summarise my notes about the boiler"):
        assert starter_acts.read(text) is None


def test_every_note_is_read_as_many_notes():
    """The sweep's typed request (deepen72b.js) was answered with quotes:
    "every note" was not a head the grammar knew."""
    from tessellate.ai import commands

    read = commands.read("tag every note about the harbor survey with harbor", datetime.now())
    assert read == {"intent": "tag", "about": "harbor survey", "single": False, "tags": ["harbor"]}
