"""WORLD_CLASS_PLAN B4, the rest of the knowledge kernel on an entity page
(LEDGER L-world-class-25): per-claim citations, what changed about it, and
the "computed by <model> at <ts>" stamp.

A claim is a sentence in one of its notes that names it, carrying the note and
the span it came from; a claim the night shift stored carries that row's model
and time. What changed is `timetravel.then_and_now` run over each note's kept
versions, oldest to newest, keeping the changes that name it. The entity row
itself says which model found it (`entities.model`).

Every date is set by hand (a fixed clock), never read from the real one.
"""

from __future__ import annotations

import sqlite3
from datetime import datetime

from tessellate.ai.entities import extract_entities_pass
from tessellate.core.database import DerivedFact, Entity, EntityMention, Entry, EntryRevision
from tests._app_js import app_js_text


def _note(session, text, when, *, private=False):
    entry = Entry(content=text, ai_confidence=0, is_private=private)
    session.add(entry)
    session.flush()
    entry.created_at = entry.updated_at = when
    return entry


def _entity(session, name, *entries, kind=None, aliases=None, model=None):
    entity = Entity(name=name, kind=kind, aliases=aliases, model=model)
    session.add(entity)
    session.flush()
    entity.created_at = datetime(2026, 9, 1, 8)
    for entry in entries:
        session.add(EntityMention(entity_id=entity.id, entry_id=entry.id))
    session.commit()
    return entity.id


def test_each_claim_names_it_and_cites_its_note_and_span(client, session):
    text = "Kiln notes\n\nSam Lee  wired the kiln on Monday. The shelf is cracked.\nSam   prefers cone six firings."
    note = _note(session, text, datetime(2026, 9, 3, 10))
    hidden = _note(session, "Sam Lee owes me money for the clay.", datetime(2026, 9, 4, 10), private=True)
    sam = _entity(session, "Sam Lee", note, hidden, kind="person", aliases=["Sam"])
    claims = client.get(f"/entities/{sam}").json()["claims"]
    assert [c["text"] for c in claims] == ["Sam Lee wired the kiln on Monday.", "Sam prefers cone six firings."]
    for claim in claims:
        assert claim["entry_id"] == note.id and claim["title"].startswith("Kiln notes")
        quoted = text[claim["span_start"] : claim["span_end"]]
        assert " ".join(quoted.split()) == claim["text"]


def test_a_stored_claim_carries_its_model_and_time_and_a_wrong_or_deleted_one_is_left_out(client, session):
    note = _note(session, "Sam Lee runs the studio. Sam Lee hates glaze days. Sam Lee owns two kilns.", datetime(2026, 9, 3, 10))
    session.add(DerivedFact(entry_id=note.id, kind="claim", text="Sam Lee runs the studio.", span_start=0, span_end=24, model="qwen-small", confidence=0.8, computed_at=datetime(2026, 9, 5, 2, 30)))
    session.add(DerivedFact(entry_id=note.id, kind="claim", text="Sam Lee owns two kilns.", model="qwen-small", computed_at=datetime(2026, 9, 5, 2, 30), deleted_at=datetime(2026, 9, 6, 9)))
    sam = _entity(session, "Sam Lee", note, kind="person")
    claims = {c["text"]: c for c in client.get(f"/entities/{sam}").json()["claims"]}
    assert set(claims) == {"Sam Lee runs the studio.", "Sam Lee hates glaze days."}
    stored = claims["Sam Lee runs the studio."]
    assert stored["fact_id"] and stored["model"] == "qwen-small" and stored["computed_at"].startswith("2026-09-05T02:30")
    read = claims["Sam Lee hates glaze days."]
    assert read["fact_id"] is None and read["model"] == "local" and read["computed_at"] is None


def test_what_changed_lists_the_claims_about_it_added_revised_and_dropped(client, session):
    first = "Sam Lee leads the kiln project. The budget is small. Sam Lee works on Fridays."
    second = "Sam Lee leads the glaze project. The budget is small. Sam Lee works on Fridays."
    now = "Sam Lee leads the glaze project. The budget is bigger now. Sam Lee joined the regional pottery guild board in early March."
    note = _note(session, now, datetime(2026, 9, 1, 9))
    session.add(EntryRevision(entry_id=note.id, content=first, created_at=datetime(2026, 9, 10, 9)))
    session.add(EntryRevision(entry_id=note.id, content=second, created_at=datetime(2026, 10, 2, 9)))
    sam = _entity(session, "Sam Lee", note, kind="person")
    changes = client.get(f"/entities/{sam}").json()["changes"]
    got = [(c["kind"], c["then"], c["now"], c["at"][:10]) for c in changes]
    assert got == [
        ("dropped", "Sam Lee works on Fridays.", None, "2026-10-02"),
        ("new", None, "Sam Lee joined the regional pottery guild board in early March.", "2026-10-02"),
        ("revised", "Sam Lee leads the kiln project.", "Sam Lee leads the glaze project.", "2026-09-10"),
    ]
    assert all(c["entry_id"] == note.id and c["title"].startswith("Sam Lee leads") for c in changes)


def test_a_task_line_is_an_open_item_not_a_claim_or_a_change(client, session):
    """Measured in the app (port 8962): "[ ] Ask Sam Lee about wiring" was
    listed as a claim, and paired with a dropped sentence as its revision."""
    note = _note(session, "Sam Lee is glazing.\n- [ ] Ask Sam Lee about the wiring today", datetime(2026, 9, 1, 9))
    session.add(EntryRevision(entry_id=note.id, content="Sam Lee is glazing. Sam Lee works on Fridays.", created_at=datetime(2026, 9, 2, 9)))
    sam = _entity(session, "Sam Lee", note, kind="person")
    page = client.get(f"/entities/{sam}").json()
    assert [c["text"] for c in page["claims"]] == ["Sam Lee is glazing."]
    assert [(c["kind"], c["then"], c["now"]) for c in page["changes"]] == [("dropped", "Sam Lee works on Fridays.", None)]


def test_a_private_notes_history_tells_nothing(client, session):
    shown = _note(session, "Sam Lee is here.", datetime(2026, 9, 1, 9))
    hidden = _note(session, "Sam Lee moved to Leeds.", datetime(2026, 9, 1, 9), private=True)
    session.add(EntryRevision(entry_id=hidden.id, content="Sam Lee lives in York.", created_at=datetime(2026, 9, 2, 9)))
    sam = _entity(session, "Sam Lee", shown, hidden, kind="person")
    assert client.get(f"/entities/{sam}").json()["changes"] == []


def test_the_page_says_which_model_found_the_name_and_when(client, session):
    note = _note(session, "Sam Lee came by.", datetime(2026, 9, 1, 9))
    sam = _entity(session, "Sam Lee", note, kind="person", model="qwen-small")
    old = _entity(session, "Leeds", note, kind="place")
    page = client.get(f"/entities/{sam}").json()
    assert page["found_by"] == {"model": "qwen-small", "at": "2026-09-01T08:00:00+00:00"}
    assert client.get(f"/entities/{old}").json()["found_by"]["model"] is None


class _Models:
    def utility_model(self) -> str:
        return "fake-utility"


class _Ollama:
    def chat(self, model, messages, mode=None):  # noqa: ANN001, ARG002
        return {"content": "Sam Lee|person"}


def test_extraction_stamps_the_model_on_the_entity_it_makes(session):
    session.add(Entry(content="Went over the kiln rota with Sam Lee in Leeds today.", ai_confidence=0))
    session.commit()
    extract_entities_pass(session, _Models(), _Ollama())
    entity = session.query(Entity).one()
    assert (entity.name, entity.model) == ("Sam Lee", "fake-utility")


def test_an_old_database_gets_the_column(tmp_path):
    from tessellate.core.database_manager import DatabaseManager

    path = tmp_path / "old.db"
    raw = sqlite3.connect(path)
    raw.execute("CREATE TABLE entities (id INTEGER PRIMARY KEY, name VARCHAR(200), created_at DATETIME)")
    raw.execute("INSERT INTO entities (name, created_at) VALUES ('Sam', '2026-01-01 00:00:00')")
    raw.commit()
    raw.close()
    db = DatabaseManager(path)
    db._add_missing_columns()
    with sqlite3.connect(path) as raw:
        columns = {row[1] for row in raw.execute('PRAGMA table_info("entities")')}
        assert "model" in columns
        assert raw.execute("SELECT model FROM entities").fetchone() == (None,)
    db.engine.dispose()


def test_the_page_draws_claims_changes_and_the_stamp():
    js = app_js_text()
    page = js[js.index("async function openEntityPage(") :]
    page = page[: page.index("function entitySection(")]
    for words in ('"Claims"', '"What changed"', "entityFoundBy("):
        assert words in page, words
    claim = js[js.index("function entityClaimRow(") :]
    claim = claim[: claim.index("\n}\n")]
    assert "claim.text, sub, claim.text)" in claim and "entityFoundBy(" in claim
    button = js[js.index("function entityNoteButton(") :]
    button = button[: button.index("\n}\n")]
    assert "openNoteAtPassage(id, passage)" in button
