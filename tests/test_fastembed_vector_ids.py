"""Vectors made before the engine moved to fastembed keep being found
(the owner, 2026-10-27: replace sentence-transformers and torch with
fastembed, same model family).

Each vector names the engine that made it, search reads only the live
engine's, and the backfill fills only notes with no vector, so a renamed
engine would strand every vector for good. The two engines' vectors for one
text measured cosine 0.999999, so migration f1b3c5d7e9a2 renames them and
nothing is embedded again; a saved "sentence-transformers" setting reads as
the new engine.
"""

from __future__ import annotations

import sqlite3
from pathlib import Path

from alembic import command
from alembic.config import Config

from sqlalchemy import create_engine

from tessellate.core import embedmodels
from tessellate.core.database import Base

ROOT = Path(__file__).resolve().parents[1]
BEFORE = "c4e8a1f6b2d9"
REV = "f1b3c5d7e9a2"
TABLES = ("embeddings", "chunk_vectors", "embeddings_staged")


def _config(db_path: Path) -> Config:
    config = Config(str(ROOT / "alembic.ini"))
    config.set_main_option("script_location", str(ROOT / "migrations"))
    config.set_main_option("sqlalchemy.url", f"sqlite:///{db_path}")
    return config


def _old_db(db_path: Path) -> None:
    engine = create_engine(f"sqlite:///{db_path}")
    Base.metadata.create_all(engine)
    engine.dispose()
    command.stamp(_config(db_path), BEFORE)


def _insert(con: sqlite3.Connection, table: str, values: dict) -> None:
    """A row with the given values and a plain default for any other NOT NULL column."""
    for _, name, kind, notnull, default, _pk in con.execute(f"PRAGMA table_info({table})").fetchall():
        if notnull and default is None and name not in values and name != "id":
            upper = kind.upper()
            values[name] = 0 if any(k in upper for k in ("INT", "BOOL", "FLOAT", "REAL")) else ("2026-01-01 00:00:00" if "DATE" in upper else "")
    con.execute(f"INSERT INTO {table} ({', '.join(values)}) VALUES ({', '.join('?' * len(values))})", list(values.values()))


def _versions(db: Path, table: str) -> list:
    con = sqlite3.connect(db)
    try:
        return [r[0] for r in con.execute(f"SELECT model_version FROM {table} ORDER BY id")]
    finally:
        con.close()


def _seed(db: Path) -> None:
    con = sqlite3.connect(db)
    try:
        for table in TABLES:
            for entry_id, version in enumerate(
                ("sentence-transformers:BAAI/bge-small-en-v1.5", "ollama:nomic-embed-text", "sentence-transformers:intfloat/multilingual-e5-small"),
                start=1,
            ):
                _insert(con, table, {"entry_id": entry_id, "model_version": version})
        con.commit()
    finally:
        con.close()


def test_old_engine_vectors_are_renamed_in_every_table_and_others_are_left(tmp_path):
    db = tmp_path / "old.db"
    _old_db(db)
    _seed(db)
    command.upgrade(_config(db), REV)
    for table in TABLES:
        assert _versions(db, table) == [
            "fastembed:BAAI/bge-small-en-v1.5",
            "ollama:nomic-embed-text",
            "fastembed:intfloat/multilingual-e5-small",
        ], table


def test_downgrade_gives_the_old_names_back(tmp_path):
    db = tmp_path / "old.db"
    _old_db(db)
    _seed(db)
    command.upgrade(_config(db), REV)
    command.downgrade(_config(db), BEFORE)
    assert _versions(db, "embeddings")[0] == "sentence-transformers:BAAI/bge-small-en-v1.5"


def test_a_second_run_changes_nothing(tmp_path):
    """Run once: renamed rows no longer match, so a re-run (or a resumed
    launch) has nothing to do and no vector is embedded twice."""
    db = tmp_path / "old.db"
    _old_db(db)
    _seed(db)
    command.upgrade(_config(db), REV)
    command.stamp(_config(db), BEFORE)
    command.upgrade(_config(db), REV)
    assert _versions(db, "chunk_vectors")[0] == "fastembed:BAAI/bge-small-en-v1.5"


def test_the_renamed_id_is_the_one_the_live_engine_searches_with(monkeypatch):
    """What the migration writes is what `backend_id()` reads, so the
    backfill sees every renamed note as embedded and does not run again."""
    from tessellate.ai.embeddings import EmbeddingService

    service = EmbeddingService.__new__(EmbeddingService)
    service._models = type("Models", (), {"embedding_backend": lambda self: "fastembed"})()
    monkeypatch.setattr(EmbeddingService, "st_repo", lambda self: "BAAI/bge-small-en-v1.5")
    assert service.backend_id() == "fastembed:BAAI/bge-small-en-v1.5"


def test_a_saved_old_engine_name_reads_as_the_new_engine():
    assert embedmodels.backend_name("sentence-transformers") == "fastembed"
    assert embedmodels.backend_name("fastembed") == "fastembed"
    assert embedmodels.backend_name("ollama") == "ollama"
    assert embedmodels.backend_name(None) == "fastembed"
