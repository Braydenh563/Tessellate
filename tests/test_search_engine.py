"""The retrieval engine, measured (SESSION_BRIEFS Brief 11, WORLD_CLASS_PLAN B3).

`tests/test_search_engine_spec.py` is the contract and stays as written; this
file is where the behaviour around it is pinned: the operators one by one, the
index's write path, the three scores, and the perf gates with the numbers they
were measured at.
"""
from __future__ import annotations

from datetime import date, datetime

import pytest
from sqlalchemy import text as sa_text

from tessellate.search.query import understand


def test_an_ordinary_question_has_no_operators():
    u = understand("what did I write about beans")
    assert u.filters == {"tag": [], "kind": [], "space": [], "has": [], "is": [], "title": []}
    assert not u.has_operators
    assert u.subject == "beans"


def test_operators_are_lifted_out_of_the_subject():
    u = understand("tag:work sourdough starter")
    assert u.filters["tag"] == ["work"]
    assert "tag:work" not in u.subject
    assert "sourdough" in u.subject


def test_a_quoted_value_and_a_comma_list():
    u = understand('tag:"two words" kind:note,document')
    assert u.filters["tag"] == ["two words"]
    assert u.filters["kind"] == ["note", "document"]


def test_aliases_mean_the_same_thing():
    assert understand("type:document").filters["kind"] == ["document"]
    assert understand("space:work").filters["space"] == ["work"]
    assert understand("tags:garden").filters["tag"] == ["garden"]


def test_before_and_after_are_exclusive_bounds():
    u = understand("before:2026-01-01 after:2025-12-01")
    assert u.until == date(2025, 12, 31)
    assert u.since == date(2025, 12, 2)


def test_a_typed_date_beats_a_time_phrase():
    """Both in one query: the stated bound wins rather than being overwritten."""
    u = understand("beans before:2026-01-01 last week", now=date(2026, 6, 1))
    assert u.until == date(2025, 12, 31)


def test_an_unreadable_date_invents_nothing():
    """`before:tuesday` is not an ISO date. No bound is guessed from it, and
    the words stay in the query, so the person sees their own text matching
    nothing rather than the app filtering by a date it made up."""
    u = understand("before:tuesday", now=date(2026, 6, 3))
    assert u.since is None and u.until is None
    assert "tuesday" in u.subject


def test_an_operator_query_is_not_a_time_only_question():
    u = understand("kind:document before:2026-01-01")
    assert not u.time_only


def test_a_url_is_not_an_operator():
    """`https:` must not read as an operator, and the url must survive whole.

    The assertion is on the whole subject rather than on a substring of it:
    CodeQL flagged the substring form (incomplete URL substring
    sanitization), and it is right that "does this text contain
    example.com" is a different question from "is this that url".
    """
    u = understand("https://example.com/thing")
    assert not u.has_operators
    assert u.subject == "https://example.com/thing"


@pytest.mark.parametrize("q", ["", "   ", '"', "-", "tag:"])
def test_a_ragged_query_is_never_an_error(q):
    understand(q)


# --- the index over every kind ------------------------------------------------


def _counts(session):
    from tessellate.search import index

    return index.counts(session)


def test_every_kind_has_a_source_and_an_unknown_one_is_loud():
    from tessellate.search import index

    for kind in index.KINDS:
        assert index.sources_for_kind(kind), f"no index source for kind {kind!r}"
    for source in index.sources():
        assert index.source_for(source.name) is source
    with pytest.raises(index.UnknownSource):
        index.source_for("entries_but_spelled_wrong")


def test_slots_are_unique_because_they_are_baked_into_rowids():
    from tessellate.search import index

    slots = [source.slot for source in index.sources()]
    assert len(set(slots)) == len(slots)


def test_a_note_is_indexed_when_it_is_written(session):
    from tessellate.entry import manager

    manager.create_entry(session, "sourdough starter needs feeding", tags=["bread"])
    session.commit()
    assert _counts(session)["note"] == 1


def test_a_board_is_indexed_as_a_board_not_a_note(session):
    from tessellate.core.database import Entry

    session.add(Entry(content="my map", is_board=True))
    session.commit()
    counts = _counts(session)
    assert counts["board"] == 1 and counts["note"] == 0


def test_a_private_note_is_never_indexed(session):
    from tessellate.core.database import Entry

    session.add(Entry(content="ciphertext here", is_private=True))
    session.commit()
    assert _counts(session)["note"] == 0


def test_an_edit_keeps_the_index_in_step(session):
    """The write the event log does not see (a document edit records no
    event), which is why the index hangs off the flush instead."""
    from tessellate.core.database import Document
    from tessellate.search import index

    doc = Document(title="Roadmap", content="quarterly planning")
    session.add(doc)
    session.commit()
    assert index.counts(session)["document"] == 1
    doc.content = "quarterly planning and the allotment"
    session.commit()
    rows = session.execute(
        sa_text("SELECT body FROM search_index WHERE kind='document'")
    ).all()
    assert len(rows) == 1 and "allotment" in rows[0][0]


def test_deleting_takes_the_row_out(session):
    from tessellate.core.database import Bookmark

    mark = Bookmark(url="https://example.com", title="example")
    session.add(mark)
    session.commit()
    assert _counts(session)["bookmark"] == 1
    session.delete(mark)
    session.commit()
    assert _counts(session)["bookmark"] == 0


def _indexed(session, kind, ref_id) -> bool:
    return bool(
        session.execute(
            sa_text("SELECT count(*) FROM search_index WHERE kind = :k AND ref_id = :r"),
            {"k": kind, "r": ref_id},
        ).scalar()
    )


def test_a_purged_note_leaves_no_row_behind(session):
    """Emptying the bin is a bulk DELETE, which the flush hook never sees: the
    note's row stayed, flagged `deleted`, for ever (`is:deleted` still found
    a note that no longer existed anywhere else)."""
    from tessellate.entry import manager

    entry = manager.create_entry(session, "the old boiler manual", tags=[])
    session.commit()
    manager.soft_delete_entry(session, entry)
    session.commit()
    ref = entry.id
    manager.purge_entries(session, [entry])
    assert not _indexed(session, "note", ref)


def test_deleting_a_space_takes_its_rows_out_of_the_index(client, session):
    """The space delete is all bulk statements, so every note, document and
    reminder in it stayed searchable from All spaces after the space was gone."""
    from tessellate.core.database import Document, Entry, Reminder

    space_id = client.post("/spaces", json={"name": "Doomed"}).json()["id"]
    entry = Entry(content="lighthouse keeper rota", workspace_id=space_id)
    doc = Document(title="lighthouse plans", content="lamp", workspace_id=space_id)
    session.add_all([entry, doc])
    session.flush()
    reminder = Reminder(text="lighthouse oil", due_at=datetime(2026, 9, 30), workspace_id=space_id)
    session.add(reminder)
    session.commit()
    ids = {"note": entry.id, "document": doc.id, "reminder": reminder.id}
    assert all(_indexed(session, kind, ref) for kind, ref in ids.items())
    # The request is made before the assert, not inside it: an assert that
    # performs the deletion would skip it under `python -O` (CodeQL 424).
    deleted = client.delete(f"/spaces/{space_id}")
    assert deleted.status_code == 200
    session.expire_all()
    for kind, ref in ids.items():
        assert not _indexed(session, kind, ref), f"a {kind} outlived its space in the index"


def test_a_bulk_delete_of_an_indexed_model_forgets_its_rows():
    """The lint half: a statement-level DELETE against an indexed model is
    invisible to the flush hook, so a file that issues one must also call
    `forget`. Found by hand twice (the bin and the space delete); this is so a
    third is found by the build."""
    import re
    from pathlib import Path

    from tests._repo_files import repo_files

    indexed = "Entry|Document|Attachment|MediaUpload|Bookmark|Reminder"
    bulk = re.compile(
        rf"delete\((?:{indexed})\)|query\((?:{indexed})\)[^\n]*\.delete\("
    )
    src = Path(__file__).resolve().parents[1] / "src" / "tessellate"
    offenders = []
    for path in repo_files(src, suffixes=(".py",)):
        text = path.read_text(encoding="utf-8")
        if bulk.search(text) and "forget(" not in text:
            offenders.append(str(path.relative_to(src)))
    assert not offenders, f"bulk deletes with no search_index.forget: {offenders}"


def test_forget_is_a_no_op_for_nothing(session):
    from tessellate.core.database import Entry
    from tessellate.search import index

    index.forget(session, Entry, [])  # must not raise or issue a bad IN ()


def test_every_kind_lands_in_one_index(session):
    from tessellate.core.database import (
        Attachment,
        Bookmark,
        Document,
        Entry,
        Reminder,
    )

    session.add(Entry(content="a note about beans"))
    session.add(Entry(content="a board", is_board=True))
    session.add(Document(title="a document", content="beans again"))
    session.add(Bookmark(url="https://example.com/beans", title="beans online"))
    session.add(Reminder(text="buy beans", due_at=datetime(2026, 1, 1)))
    session.flush()
    session.add(
        Attachment(entry_id=1, filename="beans.pdf", stored_name="x1", ocr_text="beans, dried")
    )
    session.commit()
    counts = _counts(session)
    assert counts["note"] == 1
    assert counts["board"] == 1
    assert counts["document"] == 1
    assert counts["bookmark"] == 1
    assert counts["reminder"] == 1
    assert counts["file"] == 1


def test_rebuild_matches_what_the_writes_indexed(session):
    from tessellate.core.database import Document, Entry
    from tessellate.search import index

    session.add(Entry(content="one"))
    session.add(Document(title="two", content="two"))
    session.commit()
    live = index.counts(session)
    index.rebuild(session)
    session.commit()
    assert index.counts(session) == live


# --- the engine ---------------------------------------------------------------


def _note(session, content, **kwargs):
    from tessellate.entry import manager

    entry = manager.create_entry(session, content, tags=kwargs.pop("tags", []))
    for key, value in kwargs.items():
        setattr(entry, key, value)
    session.commit()
    return entry


def test_a_hit_from_every_kind_comes_back_from_one_query(session):

    from tessellate.core.database import Bookmark, Document, Entry, Reminder
    from tessellate.search import engine

    _note(session, "allotment planting plan")
    session.add(Entry(content="allotment board", is_board=True))
    session.add(Document(title="Allotment", content="the allotment beds"))
    session.add(Bookmark(url="https://example.com", title="allotment guide"))
    session.add(Reminder(text="water the allotment", due_at=datetime(2026, 1, 1)))
    session.commit()

    hits = engine.search(session, "allotment", ctx=None)
    assert {hit.kind for hit in hits} == {"note", "board", "document", "bookmark", "reminder"}
    assert all(hit.explain for hit in hits)


def test_a_filter_narrows_the_kinds(session):
    from tessellate.core.database import Document
    from tessellate.search import engine

    _note(session, "beans in the ground")
    session.add(Document(title="Beans", content="beans everywhere"))
    session.commit()

    hits = engine.search(session, "kind:document beans", ctx=None)
    assert [hit.kind for hit in hits] == ["document"]


def test_an_excluded_word_drops_the_hit(session):
    from tessellate.search import engine

    _note(session, "beans and rice")
    _note(session, "beans and bread")
    assert len(engine.search(session, "beans", ctx=None)) == 2
    kept = engine.search(session, "beans -rice", ctx=None)
    assert len(kept) == 1 and "bread" in kept[0].snippet


def test_a_tag_filter_uses_the_indexed_tags(session):
    from tessellate.search import engine

    _note(session, "planting notes", tags=["garden"])
    _note(session, "planting notes for work", tags=["work"])
    hits = engine.search(session, "tag:garden planting", ctx=None)
    assert len(hits) == 1


def _hit_ids(session, q):
    from tessellate.search import engine

    return {(hit.kind, hit.ref_id) for hit in engine.search(session, q, ctx=None, hybrid=False)}


def test_has_image_finds_a_picture_in_the_text_or_attached(session):
    """`has:image` parsed and matched nothing: only `file` had a source."""
    from tessellate.core.database import Attachment

    inline = _note(session, "harbour walk ![the pier](/media/pier.jpg)")
    attached = _note(session, "harbour walk, photo attached")
    plain = _note(session, "harbour walk, no pictures")
    session.add(Attachment(entry_id=attached.id, filename="p.jpg", stored_name="s", mime="image/jpeg"))
    session.add(Attachment(entry_id=plain.id, filename="p.pdf", stored_name="t", mime="application/pdf"))
    session.commit()
    found = _hit_ids(session, "has:image harbour")
    assert ("note", inline.id) in found
    assert ("note", attached.id) in found
    assert ("note", plain.id) not in found


def test_has_link_finds_a_note_connected_to_another(session):
    from tessellate.core.database import EntryLink

    a = _note(session, "tidal times for the bay")
    b = _note(session, "tidal times for the estuary")
    alone = _note(session, "tidal times, unconnected")
    session.add(EntryLink(source_entry_id=a.id, target_entry_id=b.id))
    session.commit()
    found = _hit_ids(session, "has:link tidal")
    assert {("note", a.id), ("note", b.id)} <= found
    assert ("note", alone.id) not in found


def test_has_reminder_finds_a_note_with_one_and_the_reminders_themselves(session):
    from tessellate.core.database import Reminder

    with_one = _note(session, "renew the passport")
    without = _note(session, "passport photos, done")
    session.add(Reminder(text="passport office", due_at=datetime(2026, 10, 1), entry_id=with_one.id))
    session.commit()
    found = _hit_ids(session, "has:reminder passport")
    assert ("note", with_one.id) in found
    assert ("note", without.id) not in found
    assert any(kind == "reminder" for kind, _ in found)


def test_an_unknown_has_word_still_matches_nothing_rather_than_everything(session):
    _note(session, "harbour walk")
    assert _hit_ids(session, "has:unicorn harbour") == set()


def test_the_open_note_lifts_what_is_linked_to_it(session):
    """The graph signal, which is the one no amount of text similarity has."""
    from tessellate.core.database import EntryLink
    from tessellate.search import engine

    open_note = _note(session, "the plan for the season")
    linked = _note(session, "seedlings hardening off")
    _note(session, "seedlings from a different year entirely")
    session.add(EntryLink(source_entry_id=open_note.id, target_entry_id=linked.id))
    session.commit()

    hits = engine.search(session, "seedlings", ctx={"entry_id": open_note.id})
    assert hits[0].ref_id == linked.id
    assert hits[0].scores["graph"] == 0.5  # one hop: 1 / (1 + 1)
    assert "linked to the open note" in hits[0].explain


def test_every_hit_says_which_signal_carried_it(session):
    from tessellate.core.database import Document
    from tessellate.search import engine

    _note(session, "risotto with peas", tags=["recipe"])
    hits = engine.search(session, "risotto", ctx=None)
    assert hits[0].explain[0] == "matched your words"
    assert set(hits[0].scores) == {"bm25", "cosine", "graph"}

    # A title only counts as one when the body does not simply repeat it: a
    # one-line note *is* its own first line, and "matched the title" there is
    # a distinction the reader cannot see.
    session.add(Document(title="Risotto method", content="stir until the rice gives"))
    session.commit()
    titled = engine.search(session, "kind:document risotto", ctx=None)
    assert titled[0].explain[0] == "matched the title"


def test_a_cold_matrix_means_no_similarity_not_a_scan(session, monkeypatch):
    """`related()` returning nothing beats `related()` reading every vector:
    startup warms the matrix, so cold is the first seconds of a process."""
    from tessellate.search import engine

    monkeypatch.setattr(engine, "_matrix", None)
    calls = []
    monkeypatch.setattr(engine, "_load_all_vectors", lambda *a, **k: calls.append(1))
    assert engine.related(session, entry_id=1, k=5) == []
    assert not calls


def test_the_matrix_takes_a_new_vector_without_reloading(session, fake_embeddings):
    from tessellate.search import engine

    entry = _note(session, "a note about bread")
    assert engine.warm_vectors(session) >= 0
    before = len(engine.vectors_by_id(session))
    fake_embeddings.store_for_entry(session, entry)
    assert len(engine.vectors_by_id(session)) == before + 1


def test_the_search_endpoint_answers_with_scores(client):
    client.post("/entries", json={"content": "bubble tea is a drink"})
    body = client.get("/search", params={"q": "bubble tea"}).json()
    assert body["hits"], body
    hit = body["hits"][0]
    assert set(hit["scores"]) == {"bm25", "cosine", "graph"}
    assert hit["explain"]
    assert body["counts"]["note"] == 1


def test_the_search_endpoint_is_behind_the_lock():
    """The one gate this app has: a route that reads the notebook is
    registered with `locked`, and this one reads every kind at once."""
    from pathlib import Path

    source = Path("src/tessellate/api/app.py").read_text(encoding="utf-8")
    assert "app.include_router(routes_search.router, dependencies=locked)" in source


def test_making_a_note_private_takes_its_vector_out_of_the_matrix(
    session, fake_embeddings, monkeypatch
):
    """A vector derived from the text is exactly what the encryption is for.
    The bulk `delete()` in `set_private` never reaches the in-memory array,
    so the array is told directly."""
    from tessellate.entry import manager
    from tessellate.search import engine

    entry = _note(session, "the private thing about bread")
    fake_embeddings.store_for_entry(session, entry)
    engine.warm_vectors(session)
    assert entry.id in engine.vectors_by_id(session)

    monkeypatch.setattr("tessellate.core.vault.key", lambda: b"k" * 32)
    assert manager.set_private(session, entry, True)
    session.commit()
    assert entry.id not in engine.vectors_by_id(session)


def test_forget_vector_is_reachable_on_its_own(session, fake_embeddings):
    from tessellate.search import engine

    entry = _note(session, "a note to forget")
    fake_embeddings.store_for_entry(session, entry)
    engine.warm_vectors(session)
    assert entry.id in engine.vectors_by_id(session)
    engine.forget_vector(entry.id)
    assert entry.id not in engine.vectors_by_id(session)


def _toy_matrix(count: int, width: int = 4):
    import numpy as np

    from tessellate.search import engine

    rng = np.random.default_rng(7)
    rows = rng.normal(size=(count, width)).astype("float32")
    rows /= np.linalg.norm(rows, axis=1, keepdims=True)
    ids = list(range(1, count + 1))
    return engine._Matrix(key="toy", ids=ids, rows=rows, position={i: n for n, i in enumerate(ids)})


def test_a_forgotten_row_is_never_an_answer(monkeypatch):
    """A zeroed row scores 0, which beats every negative cosine: with few live
    vectors all pointing away from the query, `top_k` handed back id -1."""
    import numpy as np

    from tessellate.search import engine

    matrix = engine._Matrix(
        key="toy", ids=[5, 6], rows=np.array([[1.0, 0.0], [0.0, 1.0]], dtype="float32"),
        position={5: 0, 6: 1},
    )
    monkeypatch.setattr(engine, "_matrix", matrix)
    engine._forget(6)
    assert [entry_id for entry_id, _score in matrix.top_k(np.array([-1.0, 0.0]), 2)] == [5]


def test_dead_rows_are_compacted_once_they_are_a_quarter(monkeypatch):
    """Forgetting zeroed a row and kept it for the life of the process. Now
    the array is rebuilt without them once dead rows pass a quarter of it,
    counted, so a long session of privatising and deleting does not carry
    its whole history in memory and in every scan."""
    import numpy as np

    from tessellate.search import engine

    matrix = _toy_matrix(40)
    kept_vector = matrix.rows[39].copy()
    monkeypatch.setattr(engine, "_matrix", matrix)
    for entry_id in range(1, 11):  # 10 of 40: a quarter
        engine.forget_vector(entry_id)
    live = engine._matrix
    assert len(live.ids) == 30 and live.rows.shape[0] == 30
    assert -1 not in live.ids
    assert all(live.ids[position] == entry_id for entry_id, position in live.position.items())
    assert np.allclose(live.rows[live.position[40]], kept_vector)
    assert live.dead == 0


def test_a_few_dead_rows_are_left_until_they_add_up(monkeypatch):
    from tessellate.search import engine

    matrix = _toy_matrix(40)
    monkeypatch.setattr(engine, "_matrix", matrix)
    for entry_id in (1, 2, 3):
        engine.forget_vector(entry_id)
    assert engine._matrix.rows.shape[0] == 40 and engine._matrix.dead == 3


def test_a_query_of_filters_alone_still_answers(session):
    """`kind:document` is a question. An empty page for it would be the app
    refusing the one thing §5.1 promises works with no model running."""
    from tessellate.core.database import Document
    from tessellate.search import engine

    _note(session, "a note")
    session.add(Document(title="First", content="one"))
    session.add(Document(title="Second", content="two"))
    session.commit()

    hits = engine.search(session, "kind:document", ctx=None)
    assert {hit.kind for hit in hits} == {"document"}
    assert len(hits) == 2
    assert hits[0].explain == ["matched your filters"]


def test_a_quoted_phrase_binds_over_the_whole_query(session):
    """FTS5 binds AND tighter than OR, so an unbracketed `a OR b AND "p"`
    makes the phrase optional for half the results."""
    from tessellate.search import engine

    _note(session, "the quick brown fox jumped")
    _note(session, "quick, but no fox at all")
    hits = engine.search(session, 'quick fox "brown fox"', ctx=None)
    assert len(hits) == 1


def test_an_exclusion_binds_over_the_whole_query(session):
    from tessellate.search import engine

    _note(session, "beans with rice")
    _note(session, "peas with bread")
    # Loose enough that the "any" stage runs (no note has both words).
    hits = engine.search(session, "beans peas -rice", ctx=None)
    assert [hit.snippet for hit in hits] == ["peas with bread"]


def test_a_query_that_asks_for_nothing_answers_nothing(session):
    """An empty box, or a query that is only an exclusion, names nothing to
    find. Listing the notebook for it is noise with a scrollbar."""
    from tessellate.search import engine

    _note(session, "beans with rice")
    _note(session, "peas with bread")
    assert engine.search(session, "", ctx=None) == []
    assert engine.search(session, "   ", ctx=None) == []
    assert engine.search(session, "-rice", ctx=None) == []


def test_an_exclusion_narrows_a_filter_only_query(session):
    from tessellate.core.database import Document
    from tessellate.search import engine

    session.add(Document(title="Kept", content="peas"))
    session.add(Document(title="Dropped", content="rice"))
    session.commit()
    hits = engine.search(session, "kind:document -rice", ctx=None)
    assert [hit.title for hit in hits] == ["Kept"]


# --- a one-letter typo (audit 2026-10-05, UX-04) -----------------------------
#
# `keyword_search` (Ask) corrected "dentst" to "dentist"; the Finder and the
# Notes filter, which read `/search`, found nothing and the Finder then said
# the index was empty. The route corrects a query that found nothing against
# the words the notes actually hold, and says so.


def test_a_one_letter_typo_finds_the_note_and_says_what_it_searched(client):
    client.post("/entries", json={"content": "Dentist appointment on Friday"})
    client.post("/entries", json={"content": "Ring the dentist about the filling"})
    client.post("/entries", json={"content": "Groceries for the week"})
    body = client.get("/search", params={"q": "dentst"}).json()
    assert body["corrected"] == "dentist"
    assert len(body["hits"]) == 2, body["hits"]


def test_a_word_that_exists_is_never_corrected(client):
    client.post("/entries", json={"content": "Dentist appointment on Friday"})
    body = client.get("/search", params={"q": "dentist"}).json()
    assert body["hits"]
    assert body.get("corrected") in (None, "")


def test_a_correction_is_a_word_the_notes_use_not_its_stem(client):
    """Dogfood round 1, item 19: "lecure 5" said "showing results for
    'lectur 5'". The index holds porter stems, and the closest stem to the
    typo is not a word anyone wrote; the correction is the word in the note."""
    client.post("/entries", json={"content": "Lecture 5 covered sorting"})
    client.post("/entries", json={"content": "Lectures resume on Monday"})
    body = client.get("/search", params={"q": "lecure 5"}).json()
    assert body["corrected"] == "lecture 5", body.get("corrected")
    assert body["hits"], "the corrected word still finds the notes"


def test_nothing_close_is_still_nothing(client):
    client.post("/entries", json={"content": "Dentist appointment on Friday"})
    body = client.get("/search", params={"q": "xylophone"}).json()
    assert body["hits"] == []
    assert not body.get("corrected")
    assert body["counts"]["note"] == 1, "the index size is still said, for the empty state"


def test_the_finders_empty_state_reads_the_index_not_the_chips():
    """The chips count this query's hits, so summing them for "nothing is
    indexed yet" told every empty search the notebook was empty (UX-04)."""
    from pathlib import Path

    source = Path("frontend/js/search.js").read_text(encoding="utf-8")
    empty = source[source.index("const indexed = "):]
    empty = empty[: empty.index(";")]
    assert "finderIndexTotals" in empty and "finderCounts" not in empty
    assert "finderIndexTotals = body.counts" in source
