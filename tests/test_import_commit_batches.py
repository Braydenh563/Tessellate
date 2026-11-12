"""The app import embeds and commits in batches, and Stop is still honoured (L508, L612).

`routes_import.import_app` called `deps.store_quietly` once per made note, and
that commits: with the writer's own commit every 100 notes, a 5,000-note import
paid about 5,000 + 50 commits (45.9 s measured, WORLD_CLASS_PLAN 26). It now
embeds `EMBED_BATCH_NOTES` notes per call and commits once per batch.

Counted, not timed: a commit count is the same on every machine, so no clock.
"""

from __future__ import annotations

import pytest
from sqlalchemy import event

from tessellate.api import routes_import
from tessellate.core import deps


class _FakeEmbeddings:
    """Stands in for the embedding service: commits like the real one."""

    def __init__(self) -> None:
        self.single = 0
        self.batches: list[int] = []

    @staticmethod
    def _write(entry) -> None:  # noqa: ANN001
        # A real service writes a vector row; a commit with nothing pending is
        # not a commit to SQLite, so the fake has to change something.
        entry.access_count = (entry.access_count or 0) + 1

    def store_for_entry(self, session, entry) -> bool:  # noqa: ANN001
        self.single += 1
        self._write(entry)
        session.commit()
        return True

    def store_for_entries(self, session, entries) -> int:  # noqa: ANN001
        self.batches.append(len(entries))
        for entry in entries:
            self._write(entry)
        session.commit()
        return len(entries)


def _files(count: int) -> list[tuple[str, tuple[str, bytes, str]]]:
    return [("files", (f"Vault/n{i}.md", f"Note {i} of the vault.\n".encode(), "text/markdown")) for i in range(count)]


@pytest.fixture()
def fake(monkeypatch):
    service = _FakeEmbeddings()
    monkeypatch.setattr(deps, "get_embeddings", lambda: service)
    return service


def _commits(client_engine):
    counter = {"n": 0}
    event.listen(client_engine, "commit", lambda _c: counter.__setitem__("n", counter["n"] + 1))
    return counter


def test_notes_are_embedded_in_batches_not_one_commit_each(client, fake):
    counter = _commits(deps.get_db().engine)
    body = client.post("/import/app?source=obsidian", files=_files(250)).json()
    assert body["imported"] == 250
    assert fake.single == 0
    assert sum(fake.batches) == 250 and max(fake.batches) <= routes_import.EMBED_BATCH_NOTES
    # Writer: one per 100 notes plus the end; embeddings: three batches; log line: one.
    print(f"\n250 notes: {counter['n']} commits")
    assert counter["n"] <= 12


def test_stop_between_batches_keeps_what_was_made_and_embeds_no_more(client, fake, monkeypatch):
    from tessellate.core import activity

    calls = {"n": 0}
    real = activity.Job.stopped

    def stopped_after_one_batch(self):  # noqa: ANN001
        return calls["n"] >= 1 or real.fget(self)

    original = fake.store_for_entries

    def counting(session, entries):  # noqa: ANN001
        calls["n"] += 1
        return original(session, entries)

    fake.store_for_entries = counting
    monkeypatch.setattr(activity.Job, "stopped", property(stopped_after_one_batch))
    body = client.post("/import/app?source=obsidian", files=_files(250)).json()
    # The writer saw the stop at once (the property is true after the first batch call, which
    # comes after the writer), so every note was made and only the first batch was embedded.
    assert body["imported"] == 250
    assert len(fake.batches) == 1
