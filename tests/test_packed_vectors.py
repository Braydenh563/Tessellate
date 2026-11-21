"""Vectors stored at half width (L-world-class-174).

Search, the graph and the tools still read float32 bytes; only the disk holds
less. A row written before the change is read as it was, the conversion is a
migration with a downgrade, and the bytes round-trip through a backup copy.
"""

from __future__ import annotations

import sqlite3
from pathlib import Path

import numpy as np
from alembic import command
from alembic.config import Config
from sqlalchemy import create_engine, select, text
from sqlalchemy.orm import Session

from tessellate.core import packed_vector
from tessellate.core.database import Base, EmbeddingRecord

ROOT = Path(__file__).resolve().parents[1]


def _unit(rng, dim=384):
    v = rng.standard_normal(dim).astype("float32")
    return v / np.linalg.norm(v)


def test_a_vector_packs_to_half_and_reads_back_as_float32():
    v = _unit(np.random.default_rng(1))
    stored = packed_vector.pack(v.tobytes())
    assert len(stored) == 1 + 2 * 384 and packed_vector.is_packed(stored)
    back = np.frombuffer(packed_vector.unpack(stored), dtype="float32")
    assert back.shape == v.shape and float(np.abs(back - v).max()) < 1e-3


def test_float32_rows_written_before_are_read_as_they_were():
    raw = _unit(np.random.default_rng(2)).tobytes()
    assert not packed_vector.is_packed(raw)
    assert packed_vector.unpack(raw) == raw


def test_a_vector_float16_cannot_hold_is_stored_whole():
    for bad in (np.array([1.0, np.nan], dtype="float32"), np.array([1e9, 1.0], dtype="float32")):
        assert packed_vector.pack(bad.tobytes()) == bad.tobytes()
    assert packed_vector.pack(b"") == b"" and packed_vector.pack(b"abc") == b"abc"


def test_a_stored_row_is_about_half_the_size_and_reads_through_the_orm(tmp_path):
    engine = create_engine(f"sqlite:///{tmp_path / 'v.db'}")
    Base.metadata.create_all(engine)
    rng = np.random.default_rng(3)
    vectors = [_unit(rng) for _ in range(40)]
    with Session(engine) as session:
        for i, v in enumerate(vectors):
            session.add(EmbeddingRecord(entry_id=i + 1, embedding=v.tobytes(), dim=384, model_version="t"))
        session.commit()
        sizes = session.execute(text("SELECT length(embedding) FROM embeddings")).scalars().all()
        assert set(sizes) == {1 + 2 * 384}
        read = {r.entry_id: np.frombuffer(r.embedding, dtype="float32") for r in session.scalars(select(EmbeddingRecord))}
    assert len(read[5]) == 384 and float(np.abs(read[5] - vectors[4]).max()) < 1e-3


def test_the_top_ten_barely_moves(tmp_path):
    rng = np.random.default_rng(4)
    matrix = np.stack([_unit(rng, 64) for _ in range(1500)])
    packed = np.stack(
        [np.frombuffer(packed_vector.unpack(packed_vector.pack(v.tobytes())), dtype="float32") for v in matrix]
    )
    overlap = []
    for q in matrix[:60]:
        want = set(np.argsort(-(matrix @ q))[:10])
        got = set(np.argsort(-(packed @ q))[:10])
        overlap.append(len(want & got) / 10)
    assert sum(overlap) / len(overlap) >= 0.97


def test_a_backup_copy_reads_the_same(tmp_path):
    engine = create_engine(f"sqlite:///{tmp_path / 'a.db'}")
    Base.metadata.create_all(engine)
    v = _unit(np.random.default_rng(5))
    with Session(engine) as session:
        session.add(EmbeddingRecord(entry_id=1, embedding=v.tobytes(), dim=384, model_version="t"))
        session.commit()
    engine.dispose()
    source = sqlite3.connect(tmp_path / "a.db")
    target = sqlite3.connect(tmp_path / "b.db")
    source.backup(target)
    target.close()
    source.close()
    copy = create_engine(f"sqlite:///{tmp_path / 'b.db'}")
    with Session(copy) as session:
        row = session.scalars(select(EmbeddingRecord)).one()
        assert float(np.abs(np.frombuffer(row.embedding, dtype="float32") - v).max()) < 1e-3


def test_the_migration_converts_old_rows_and_the_downgrade_restores_them(tmp_path):
    db = tmp_path / "old.db"
    engine = create_engine(f"sqlite:///{db}")
    Base.metadata.create_all(engine)
    engine.dispose()
    rng = np.random.default_rng(6)
    originals = [_unit(rng).tobytes() for _ in range(7)]
    con = sqlite3.connect(db)
    for i, blob in enumerate(originals):
        con.execute(
            "INSERT INTO embeddings (entry_id, embedding, dim, model_version, created_at) VALUES (?, ?, 384, 't', '2026-01-01')",
            (i + 1, blob),
        )
    con.commit()
    con.close()
    config = Config(str(ROOT / "alembic.ini"))
    config.set_main_option("script_location", str(ROOT / "migrations"))
    config.set_main_option("sqlalchemy.url", f"sqlite:///{db}")
    command.stamp(config, "a3e7c1d9b5f2")
    command.upgrade(config, "b5d2e8a1c7f3")
    lengths = {r[0] for r in sqlite3.connect(db).execute("SELECT length(embedding) FROM embeddings")}
    assert lengths == {1 + 2 * 384}
    command.downgrade(config, "a3e7c1d9b5f2")
    rows = [bytes(r[0]) for r in sqlite3.connect(db).execute("SELECT embedding FROM embeddings ORDER BY id")]
    assert all(len(r) == 4 * 384 for r in rows)
    for before, after in zip(originals, rows):
        assert float(np.abs(np.frombuffer(before, dtype="float32") - np.frombuffer(after, dtype="float32")).max()) < 1e-3
