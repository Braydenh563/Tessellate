"""Suggested tags made when a note is filed, kept on it to take or discard
(INBOX 440: "pre suggested tags that are made and kept when filing for the
user to easily choose or discard"), with no AI from the notebook's own tags.
"""

from __future__ import annotations

import time

from tessellate.ai import tagging


def _settled(client, entry_id, timeout=10.0):
    """Until the whole filing job is done (embed and Tidy included), so no
    test tears down under a running job."""
    from tessellate.core import jobs

    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        state = client.get(f"/entries/{entry_id}/filing").json()["filing_state"]
        if state != "pending" and not jobs.in_flight(("file-entry", entry_id)):
            return
        time.sleep(0.05)
    raise AssertionError(f"filing of note {entry_id} did not finish in {timeout}s")


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


def test_the_suggestions_are_on_the_note_when_its_state_settles(client, monkeypatch):
    """The reader's race (CI py3.11, 2026-11-14; review of PR 240): a poller
    stops on the first settled `filing_state`, and the suggestions must be
    there by then. Slow suggestions make it certain; the wait is on the
    state alone, as the composer's poller waits."""
    from tessellate.api import routes_entries

    keep = routes_entries._keep_suggestions

    def slow_keep(*args, **kwargs):
        time.sleep(0.5)
        return keep(*args, **kwargs)

    monkeypatch.setattr(routes_entries, "_keep_suggestions", slow_keep)
    _seed(client)
    note_id = client.post(
        "/entries", json={"content": "Front squats today, legs wrecked", "defer_filing": True}
    ).json()["id"]
    deadline = time.monotonic() + 10
    while client.get(f"/entries/{note_id}/filing").json()["filing_state"] == "pending":
        assert time.monotonic() < deadline, "filing never settled"
        time.sleep(0.05)
    assert "gym" in client.get(f"/entries/{note_id}").json()["suggested_tags"]
    _settled(client, note_id)


def test_no_key_is_never_in_flight():
    from tessellate.core import jobs

    assert jobs.in_flight(None) is False


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


def test_tidy_runs_only_from_the_background_filing_job():
    # PR 224 review: `_embed_and_tidy` runs Tidy's automatic reviews inline, which is only safe
    # off the request path; its one caller is the filing job (jobstore "file-entry"), a worker thread.
    import inspect

    from tessellate.api import routes_entries as r

    src = inspect.getsource(r)
    calls = [line for line in src.splitlines() if "_embed_and_tidy(" in line and "def _embed_and_tidy" not in line]
    assert len(calls) == 1, calls
    assert "_embed_and_tidy(session" in inspect.getsource(r._file_entry_in_background)
    assert '"file-entry": "tessellate.api.routes_entries:_file_entry_in_background"' in inspect.getsource(
        __import__("tessellate.core.jobstore", fromlist=["x"])
    )


def _filed_by_the_model(monkeypatch):
    """The filing as if the model answered: the real category, `filed_by`
    "llm", so `_keep_suggestions` takes the model path."""
    from tessellate.api import routes_entries

    real = routes_entries._file_entry_now

    def as_model(*args, **kwargs):
        category, confidence, _ = real(*args, **kwargs)
        return category, confidence, "llm"

    monkeypatch.setattr(routes_entries, "_file_entry_now", as_model)


def test_the_state_settles_before_the_models_tags_come_back(client, monkeypatch):
    """PR 242 review 6008792697 (1): the model's tag call sat ahead of the
    settle commit, so the card said "Filing…" for a whole model round-trip
    after the category was known (the 0.3.31 delay). The state is committed,
    with the notebook's own suggestions, before the model is asked; the
    model's tags land in a second commit. What another reader sees while the
    model is asked is read on a connection of its own."""
    from tessellate.ai import librarian
    from tessellate.core import deps
    from tessellate.core.database import Entry

    seen = []

    def model_reading_the_committed_state(content, have, *args, **kwargs):
        with deps.get_db().session() as other:
            row = other.query(Entry).filter(Entry.content == content).one()
            seen.append((row.filing_state, row.suggested_tags))
        return ["wrecked"]

    _filed_by_the_model(monkeypatch)
    monkeypatch.setattr(librarian, "suggest_tags", model_reading_the_committed_state)
    _seed(client)
    note_id = client.post(
        "/entries", json={"content": "Front squats today, legs wrecked", "defer_filing": True}
    ).json()["id"]
    _settled(client, note_id)
    assert seen, "the model was never asked"
    state, kept = seen[-1]
    assert state != "pending", "the state waited on the model's tags"
    assert "gym" in kept
    assert "wrecked" in client.get(f"/entries/{note_id}").json()["suggested_tags"]


def test_a_failed_suggestion_does_not_fail_the_filing(client, monkeypatch):
    """PR 242 review 6008792697 (2): a database error inside the suggestions
    (a failed flush) left the session's transaction broken, so the settle
    commit raised and the whole filing was marked failed. The suggestions run
    in a savepoint; only they are lost."""
    from tessellate.api import routes_entries
    from tessellate.core.database import Entry

    def broken_keep(session, entry, filed_by):
        session.add(Entry(content=None))
        session.flush()

    monkeypatch.setattr(routes_entries, "_keep_suggestions", broken_keep)
    note_id = client.post(
        "/entries", json={"content": "Front squats today, legs wrecked", "defer_filing": True}
    ).json()["id"]
    _settled(client, note_id)
    state = client.get(f"/entries/{note_id}/filing").json()["filing_state"]
    assert state not in ("pending", "failed"), state
