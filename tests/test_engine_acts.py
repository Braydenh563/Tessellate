"""Acts on the route with no model (CHAT_PLAN Phase 6 step 7, decision 38):
the card says the exact change, a delete waits for Confirm, a reminder runs
at once, Undo takes it back, and a look-alike question is never an act."""

from __future__ import annotations

from tessellate.ai import commands, intent
from tessellate.entry import manager
from tests.test_composer_route_688 import _ask


def _seed(session):
    ids = {}
    for key, content in (
        ("boiler", "# Boiler service\n\nDue in March. The engineer said the valve was worn."),
        ("gym", "# Gym log\n\nSquats on Monday, five sets of five."),
        ("running", "# Running\n\nRan 5 km on Saturday."),
    ):
        ids[key] = manager.create_entry(session, content).id
    session.commit()
    return ids


def test_the_router_reads_acts_and_not_questions_about_them():
    assert intent.classify("delete the boiler note") == intent.ACT
    assert intent.classify("remind me tomorrow to call the plumber") == intent.ACT
    assert intent.classify("open settings") == intent.ACT
    assert intent.classify("how do I delete a note?") != intent.ACT
    assert intent.classify("summarise my gym notes") == intent.NOTES


def test_a_delete_waits_for_confirm_and_names_the_note(client, session):
    ids = _seed(session)
    out = _ask(client, "delete the boiler note", use_tools=False)
    card = out["act"][0]
    assert card["label"] == "Move the note “Boiler service” to the bin"
    assert card["steps"] == [{"name": "delete_note", "arguments": {"note_id": ids["boiler"]}}]
    assert not card.get("done")
    assert manager.get_entry(session, ids["boiler"]).is_deleted is False
    done = client.post("/chat/command/run", json={"steps": card["steps"]}).json()
    assert done["ok"] and done["summary"].startswith("Done:") and "ph:" not in done["summary"]
    session.expire_all()
    assert manager.get_entry(session, ids["boiler"]).is_deleted is True
    undone = client.post("/chat/command/run", json={"steps": done["undo"]}).json()
    assert undone["ok"]
    session.expire_all()
    assert manager.get_entry(session, ids["boiler"]).is_deleted is False


def test_a_reminder_runs_at_once_with_its_undo(client, session):
    _seed(session)
    out = _ask(client, "remind me to call the plumber tomorrow at 5pm", use_tools=False)
    card = out["act"][0]
    assert card["done"] is True and "remind you tomorrow at 5pm: call the plumber" in out["text"]  # composed (CHAT_PLAN 1353)
    reminders = client.get("/reminders").json()
    assert reminders
    assert card["undo"] == [{"name": "bin_reminder", "arguments": {"reminder_id": card["undo"][0]["arguments"]["reminder_id"]}}]
    undone = client.post("/chat/command/run", json={"steps": card["undo"]}).json()
    assert undone["ok"]


def test_an_object_that_is_not_one_note_is_asked_about(client, session):
    _seed(session)
    out = _ask(client, "delete the plumbing note", use_tools=False)
    assert "act" not in out
    # The wording is one of the voice's variants, so any of them is the answer.
    from tessellate.ai.composer_replies import WHICH_NOTE

    assert out["text"] in {line.format(about="plumbing") for lines in WHICH_NOTE.values() for line in lines}


def test_link_and_its_undo(client, session):
    ids = _seed(session)
    out = _ask(client, "link the gym note to the running note", use_tools=False)
    card = out["act"][0]
    assert card["steps"][0] == {"name": "link_notes", "arguments": {"note_id": ids["gym"], "other_note_id": ids["running"]}}
    done = client.post("/chat/command/run", json={"steps": card["steps"]}).json()
    assert done["undo"] == [{"name": "unlink_notes", "arguments": {"note_id": ids["gym"], "other_note_id": ids["running"]}}]


def test_navigation_is_an_event_not_a_change(client, session):
    out = _ask(client, "open settings", use_tools=False)
    assert out["navigate"][0]["surface"] == "settings"


def test_the_run_route_refuses_a_step_it_does_not_run(client, session):
    response = client.post("/chat/command/run", json={"steps": [{"name": "delete_category", "arguments": {"name": "Work"}}]})
    assert response.status_code == 404


def test_the_ask_box_says_where_acts_are_done(client, session):
    out = _ask(client, "delete the boiler note", notes_only=True, use_tools=False)
    #: The act registry names the act Ask read (decision 53).
    assert out["text"] == "That is something to do (delete a note) rather than to look up: say it in Chat and it is done there, with Undo."


def test_with_a_model_in_agent_mode_the_agent_takes_the_act(ai_client, fake_ollama, session):
    _seed(session)
    out = _ask(ai_client, "delete the boiler note", use_tools=True)
    assert "act" not in out


def test_the_capability_line_names_only_what_runs():
    for verb in ("set a reminder", "tag notes", "pin, link, rename or delete a note"):
        assert verb in commands.CAPABILITY_LINE
    assert "archive" not in commands.CAPABILITY_LINE


def test_delete_all_notes_about_names_every_match(client, session):
    """"delete all notes about gym" bins every match, and says how many,
    rather than quietly reducing "all" to the best one (audit 1028 E66)."""
    ids = _seed(session)
    second = manager.create_entry(session, "# Gym plan\n\nGym three times a week.").id
    session.commit()
    card = _ask(client, "delete all notes about gym", use_tools=False)["act"][0]
    assert card["label"] == "Move the 2 notes about “gym” to the bin"
    assert sorted(s["arguments"]["note_id"] for s in card["steps"]) == sorted([ids["gym"], second])
    assert all(s["name"] == "delete_note" for s in card["steps"]) and not card.get("done")
    manager.soft_delete_entry(session, manager.get_entry(session, second))
    session.commit()
    card = _ask(client, "delete all notes about gym", use_tools=False)["act"][0]
    assert card["label"] == "Move the only note about “gym”, “Gym log”, to the bin"
