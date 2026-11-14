"""Suggested tags made when a note is filed, kept on it to take or discard
(INBOX 440: "pre suggested tags that are made and kept when filing for the
user to easily choose or discard"), with no AI from the notebook's own tags.
"""

from __future__ import annotations

import time

from tessellate.ai import tagging


def _settled(client, entry_id, timeout=10.0):
    deadline = time.time() + timeout
    while time.time() < deadline:
        if client.get(f"/entries/{entry_id}/filing").json()["filing_state"] != "pending":
            return
        time.sleep(0.05)


def _seed(client):
    for content, tags in (
        ("Leg day: squats 5x5 at 80kg, deadlifts after", ["gym", "legs"]),
        ("Rowing machine 2k in 8 minutes, then squats", ["gym", "cardio"]),
        ("Squats and lunges, legs are sore", ["gym", "legs"]),
        ("Pasta with garlic, chilli and lemon", ["recipe"]),
    ):
        client.post("/entries", json={"content": content, "tags": tags})


def test_the_nearest_notes_tags_are_suggested(client, session):
    _seed(client)
    tags = tagging.suggest(session, "Front squats today, legs wrecked", have=[])
    assert tags[:2] == ["gym", "legs"] or set(tags[:2]) == {"gym", "legs"}
    assert "recipe" not in tags


def test_a_tag_already_on_the_note_is_not_suggested(client, session):
    _seed(client)
    tags = tagging.suggest(session, "Front squats today, legs wrecked", have=["Gym"])
    assert "gym" not in [t.lower() for t in tags]


def test_a_vocabulary_tag_the_note_names_is_suggested(client, session):
    _seed(client)
    assert "cardio" in tagging.suggest(session, "Some cardio after work", have=[])


def test_filing_keeps_the_suggestions_on_the_note(client):
    _seed(client)
    created = client.post(
        "/entries", json={"content": "Front squats today, legs wrecked", "defer_filing": True}
    ).json()
    _settled(client, created["id"])
    note = client.get(f"/entries/{created['id']}").json()
    assert "gym" in note["suggested_tags"]


def test_taking_and_discarding_a_suggestion(client):
    _seed(client)
    created = client.post(
        "/entries", json={"content": "Front squats today, legs wrecked", "defer_filing": True}
    ).json()
    _settled(client, created["id"])
    note_id = created["id"]
    kept = client.post(f"/entries/{note_id}/suggested-tags", json={"take": ["gym"], "discard": ["legs"]}).json()
    assert "gym" in kept["tags"]
    assert "gym" not in kept["suggested_tags"] and "legs" not in kept["suggested_tags"]
    #: A discarded suggestion is not offered again on the next filing pass.
    again = client.get(f"/entries/{note_id}").json()
    assert "legs" not in again["suggested_tags"]


def test_the_card_offers_them_and_shows_the_confidence():
    from tests._app_js import app_js_text

    js = app_js_text()
    assert 'setLabel(take, `ph:plus ${tag}`);' in js and 'const group = chip("", "tag suggested-tag");' in js
    assert "answerTags(entry, { discard: [tag] })" in js
    assert '"item-fact filing-sure"' in js


def test_the_note_line_is_spaced_in_groups():
    """INBOX 447: "there's no spacing between note metadata". An id rule set
    the Notes list's line to 6.4px and the chips' hover bleed overlapped
    them; one rule now spaces every note line, 16px between groups."""
    from pathlib import Path

    css = (Path(__file__).resolve().parent.parent / "frontend" / "css" / "03-dashboard-widgets.css").read_text(encoding="utf-8")
    assert ":is(#entry-list, #raw-results, .timeline-feed, body) .entry-meta.note-meta {\n  column-gap: var(--space-6);" in css
