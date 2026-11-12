"""Paragraph vectors (WORLD_CLASS_PLAN §14 item 3, row 6).

A long note's own vector averages every subject it covers, so a question
about one paragraph of it ranked below a short note that only brushed the
subject. A note of two or more paragraphs now stores a vector per paragraph
(`ChunkVector`), and `semantic_search` scores a note on the better of its own
vector and its best paragraph's. Measured on a seeded notebook by
`scratchpad/chunk_retrieval_bench.py`.
"""

from __future__ import annotations

import json

from sqlalchemy import delete, func, select

from tessellate.ai import chunks as chunk_rules
from tessellate.ai import embeddings as embeddings_module
from tessellate.ai.embeddings import paragraph_chunks
from tessellate.core.database import ChunkVector, EmbeddingRecord, Entry
from tessellate.search import chunks, search_manager

FILLER = "this paragraph keeps going with some ordinary words about the day and what happened"

JOKES = f"The scarecrow joke and the pun about fields, {FILLER}."
SHOPPING = f"Buy milk and eggs and the rest of the groceries, {FILLER}."
RACE = f"The carnival race and the 100m sprint at athletics, {FILLER}."


def _note(session, content):
    entry = Entry(content=content, tags=json.dumps([]))
    session.add(entry)
    session.commit()
    return entry


def _chunk_count(session, entry_id=None):
    query = select(func.count(ChunkVector.id))
    if entry_id is not None:
        query = query.where(ChunkVector.entry_id == entry_id)
    return session.scalar(query)


# --- splitting -----------------------------------------------------------------


def test_blank_lines_separate_paragraphs_and_spans_index_the_text():
    text = f"{JOKES}\n\n{SHOPPING}\n\n\n{RACE}"
    spans = paragraph_chunks(text)
    assert [text[a:b] for a, b in spans] == [JOKES, SHOPPING, RACE]


def test_a_heading_joins_the_paragraph_it_heads():
    text = f"# Weekend\n\n{JOKES}\n\n{SHOPPING}"
    spans = paragraph_chunks(text)
    assert len(spans) == 2
    assert text[spans[0][0] : spans[0][1]].startswith("# Weekend")
    assert text[spans[0][0] : spans[0][1]].endswith(JOKES)


def test_a_short_note_is_one_chunk():
    assert len(paragraph_chunks("Buy milk.\n\nAnd eggs.")) == 1
    assert len(paragraph_chunks(JOKES)) == 1
    assert paragraph_chunks("") == []


def test_a_very_long_paragraph_is_cut_at_sentence_ends():
    sentence = "One more sentence with exactly ten words in it here. "
    text = sentence * 60  # 600 words, one paragraph
    spans = paragraph_chunks(text)
    assert len(spans) >= 3
    for start, end in spans:
        piece = text[start:end]
        assert piece.endswith(".")
        assert len(piece.split()) <= chunk_rules.CHUNK_MAX_WORDS + 10


def test_a_note_stores_at_most_the_cap():
    text = "\n\n".join([JOKES] * (chunk_rules.CHUNK_MAX_PER_NOTE + 10))
    assert len(paragraph_chunks(text)) == chunk_rules.CHUNK_MAX_PER_NOTE


# --- storing -------------------------------------------------------------------


def test_a_long_note_stores_a_vector_per_paragraph_and_a_short_one_none(session, fake_embeddings):
    long_note = _note(session, f"{JOKES}\n\n{SHOPPING}\n\n{RACE}")
    short_note = _note(session, JOKES)
    assert fake_embeddings.store_for_entry(session, long_note)
    assert fake_embeddings.store_for_entry(session, short_note)
    rows = session.scalars(
        select(ChunkVector).where(ChunkVector.entry_id == long_note.id).order_by(ChunkVector.ordinal)
    ).all()
    assert [row.ordinal for row in rows] == [0, 1, 2]
    assert long_note.content[rows[1].start : rows[1].end] == SHOPPING
    record = session.scalar(select(EmbeddingRecord).where(EmbeddingRecord.entry_id == long_note.id))
    assert {row.embedding_id for row in rows} == {record.id}
    assert _chunk_count(session, short_note.id) == 0


def test_a_resave_embeds_only_the_paragraph_that_changed(session, fake_embeddings):
    note = _note(session, f"{JOKES}\n\n{SHOPPING}\n\n{RACE}")
    fake_embeddings.store_for_entry(session, note)
    seen: list[str] = []
    original = fake_embeddings.embed_text

    def counting(text):
        seen.append(text)
        return original(text)

    fake_embeddings.embed_text = counting
    note.content = f"{JOKES}\n\n{SHOPPING} Also bread.\n\n{RACE}"
    session.commit()
    fake_embeddings.store_for_entry(session, note)
    # The note vector, then one paragraph: the other two kept their vectors.
    assert len(seen) == 2
    assert "Also bread" in seen[1]
    assert _chunk_count(session, note.id) == 3


# --- scoring -------------------------------------------------------------------


def test_a_long_note_ranks_on_its_best_paragraph(session, fake_embeddings):
    """The joke paragraph of a three-subject note beats a note that only
    brushes jokes; with paragraph scores off it does not."""
    long_note = _note(session, f"Weekend\n\n{SHOPPING}\n\n{JOKES}\n\n{RACE}")
    brushing = _note(session, "A funny thing at the shops: milk was half price.")
    for entry in (long_note, brushing):
        fake_embeddings.store_for_entry(session, entry)

    def ranking():
        chunks.reset()
        found = search_manager.semantic_search(
            session, "the scarecrow pun", fake_embeddings, limit=5, min_similarity=0.0, relative_z_margin=-10
        )
        return [(entry.id, round(score, 3)) for entry, score in found]

    chunks.ENABLED = False
    try:
        before = ranking()
    finally:
        chunks.ENABLED = True
    after = ranking()
    assert before[0][0] == brushing.id
    assert after[0] == (long_note.id, 1.0)


def test_a_chunk_does_not_outlive_its_note_vector(session, fake_embeddings):
    """Ten places delete a note vector by bulk statement; none of them knows
    this table. A chunk counts only beside the vector it was cut with."""
    long_note = _note(session, f"Weekend\n\n{SHOPPING}\n\n{JOKES}\n\n{RACE}")
    other = _note(session, "A funny thing at the shops: milk was half price.")
    for entry in (long_note, other):
        fake_embeddings.store_for_entry(session, entry)
    session.execute(delete(EmbeddingRecord).where(EmbeddingRecord.entry_id == long_note.id))
    session.commit()
    found = search_manager.semantic_search(
        session, "the scarecrow pun", fake_embeddings, limit=5, min_similarity=0.0, relative_z_margin=-10
    )
    assert long_note.id not in [entry.id for entry, _score in found]
    # And the orphan pass removes the rows themselves.
    from tessellate.core import deps

    embeddings_module.clean_orphaned_vectors(deps.get_db().session)
    session.expire_all()
    assert _chunk_count(session, long_note.id) == 0


def test_making_a_note_private_deletes_its_paragraph_vectors(session, fake_embeddings, monkeypatch):
    from tessellate.entry import manager_private

    long_note = _note(session, f"{SHOPPING}\n\n{JOKES}")
    fake_embeddings.store_for_entry(session, long_note)
    assert _chunk_count(session, long_note.id) == 2
    monkeypatch.setattr("tessellate.core.vault.key", lambda: b"k" * 32)
    assert manager_private.set_private(session, long_note, True)
    session.commit()
    assert _chunk_count(session, long_note.id) == 0


def test_the_backfill_gives_old_long_notes_paragraphs(session, fake_embeddings):
    from tessellate.core import deps

    body = "\n\n".join([SHOPPING, JOKES, RACE, SHOPPING.replace("milk", "bread")])
    note = _note(session, body)
    fake_embeddings.store_for_entry(session, note)
    session.execute(delete(ChunkVector))
    session.commit()
    assert _chunk_count(session) == 0
    embeddings_module.backfill_missing(fake_embeddings, deps.get_db().session)
    session.expire_all()
    assert _chunk_count(session, note.id) == 4
