"""Audit 1028 K32: the page's minute look is a stamp, and the list is fetched only when it moved."""

from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
STATUS = (ROOT / "frontend" / "js" / "status.js").read_text(encoding="utf-8")


def _make(client, text, due="2099-01-01T09:00:00"):
    return client.post("/reminders", json={"text": text, "due_at": due}).json()


def test_an_empty_notebook_answers_nothing_open(client):
    body = client.get("/reminders/due").json()
    assert (body["open"], body["next_due_at"]) == (0, None)


def test_the_stamp_moves_when_the_open_list_does_and_not_otherwise(client):
    first = _make(client, "water the plants")
    one = client.get("/reminders/due").json()
    assert client.get("/reminders/due").json() == one, "asking twice changes nothing"
    assert one["open"] == 1 and one["next_due_at"].startswith("2099-01-01")

    _make(client, "call the dentist", "2098-06-01T09:00:00")
    two = client.get("/reminders/due").json()
    assert two["open"] == 2 and two["stamp"] != one["stamp"]
    assert two["next_due_at"].startswith("2098-06-01"), "the soonest one leads"

    client.put(f"/reminders/{first['id']}", json={"text": "water the ferns"})
    three = client.get("/reminders/due").json()
    assert three["stamp"] != two["stamp"], "a reworded reminder is a changed list"

    client.post(f"/reminders/{first['id']}/complete")
    four = client.get("/reminders/due").json()
    assert four["open"] == 1 and four["stamp"] != three["stamp"], "ticking one off removes it"


def test_the_look_is_small(client):
    for n in range(30):
        _make(client, f"item {n}", f"2099-01-{n % 28 + 1:02d}T09:00:00")
    assert len(client.get("/reminders/due").content) < 200


def test_the_page_fetches_the_list_only_when_the_stamp_moved():
    poll = STATUS.split("async function checkDueReminders() {", 1)[1].split("\n}\n", 1)[0]
    assert poll.index('"/reminders/due"') < poll.index('"/reminders?include_done=false"')
    assert "look.stamp === cache.stamp" in poll
    assert "const same = " in poll and "if (!same) reminderChannel?.postMessage(all)" in poll
    # The cache hangs off the function: no new name in the shared scope (ratchet).
    assert "checkDueReminders.cache" in poll
