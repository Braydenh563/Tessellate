"""L98: "on my birthday" reads a birthday the person stored in Settings.

The notes' own "my birthday is ..." line stays the fallback (row 459); a
stored one wins, because a person typed it for exactly this."""

from __future__ import annotations

from datetime import datetime

from tessellate.ai import personal
from tessellate.core import deps

NOW = datetime(2026, 11, 12, 10, 0)
NOTE = [{"id": 1, "content": "My birthday is 3 December."}]


def test_the_birthday_preference_roundtrips_as_typed_and_clears(client):
    fresh = client.get("/preferences").json()
    saved = client.put("/preferences", json={"birthday": "20 November"}).json()
    stored = deps.get_config().get_preference("birthday")
    cleared = client.put("/preferences", json={"birthday": ""}).json()
    assert fresh["birthday"] == ""
    assert saved["birthday"] == stored == "20 November"
    assert cleared["birthday"] == ""


def test_a_birthday_that_is_no_day_is_refused(client):
    for bad in ("banana", "March", "31 February", "<b>3 May</b>"):
        refused = client.put("/preferences", json={"birthday": bad})
        assert refused.status_code == 422, bad


def test_the_stored_birthday_is_a_year_free_day():
    assert personal.stored_birthday("20 November", NOW) == "2000-11-20"
    assert personal.stored_birthday("", NOW) is None
    assert personal.stored_birthday("nonsense", NOW) is None


def test_read_prefers_the_stored_birthday_over_the_notes(client, session):
    from tessellate.entry import manager

    manager.create_entry(session, "My birthday is 3 December.")
    session.commit()
    token = client.post("/auth/setup", json={"password": "first-pass"}).json()["token"]
    headers = {"X-Auth-Token": token}
    ask = {"q": "call Sam on my birthday", "surface": "reminder", "now": "2026-10-07T10:00:00+00:00"}
    first = client.get("/read", params=ask, headers=headers).json()
    assert "2026-12-03" in str(first)
    stored = client.put("/preferences", json={"birthday": "20 November"}, headers=headers)
    assert stored.status_code == 200
    second = client.get("/read", params=ask, headers=headers).json()
    assert "2026-11-20" in str(second)


def test_the_settings_row_and_the_help_topic_name_it():
    from tests._help_text import help_more_text

    assert "Your birthday" in help_more_text()
