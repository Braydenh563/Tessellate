"""search by meaning: stored vectors carry the new engine's name

The built-in engine moved from sentence-transformers (PyTorch) to fastembed
(ONNX Runtime) on 2026-10-27, keeping the same models. Every vector names
the engine and model it came from (`model_version`, "sentence-transformers:
BAAI/bge-small-en-v1.5"), search reads only the vectors that match the live
engine's name, and the backfill fills only notes with no vector at all, so
without this every note would stop being found by meaning and never be
embedded again. The two engines' vectors for one text measured cosine
0.999999 or better, so the vectors of the models measured here are renamed,
not recomputed: no re-embed. Measured on 2026-10-27, the same texts through
both engines on the same weights, unit vectors, cosine per text:

- BAAI/bge-small-en-v1.5: min 0.9999987 over 8 texts.
- intfloat/multilingual-e5-small: min 0.9999999 over 20 texts (largest
  single-component difference 1.3e-07), with the "query: " prefix the app
  puts in front of E5 inputs.

Only those two are renamed. Any other model's vectors (MiniLM, bge-base, the
quantised ONNX builds fastembed runs, the large ones) were never compared, so
they keep their old name, search ignores them, and the backfill (it fills a
note whose vector came from another model) embeds those notes again rather
than trusting an unmeasured match. Data only: no row is added or dropped.

Revision ID: f1b3c5d7e9a2
Revises: c4e8a1f6b2d9
Create Date: 2026-10-27

"""
from typing import Sequence, Union

from alembic import op


# revision identifiers, used by Alembic. See the baseline migration for the
# __all__ (read by attribute name, never imported).
__all__ = ["revision", "down_revision", "branch_labels", "depends_on"]
revision: str = "f1b3c5d7e9a2"
down_revision: Union[str, Sequence[str], None] = "c4e8a1f6b2d9"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

#: Every table whose rows name the model their vector came from.
TABLES = ("embeddings", "chunk_vectors", "embeddings_staged")
OLD = "sentence-transformers:"
NEW = "fastembed:"
#: The models whose two engines' vectors were measured equal (see above).
MEASURED = ("BAAI/bge-small-en-v1.5", "intfloat/multilingual-e5-small")


def _tables(bind) -> set:  # noqa: ANN001
    return {row[0] for row in bind.exec_driver_sql("SELECT name FROM sqlite_master WHERE type='table'")}


def _rename(source: str, target: str) -> None:
    bind = op.get_bind()
    present = _tables(bind)
    for table in TABLES:
        if table not in present:
            continue
        for repo in MEASURED:
            bind.exec_driver_sql(
                f"UPDATE {table} SET model_version = ? WHERE model_version = ?",
                (target + repo, source + repo),
            )


def upgrade() -> None:
    _rename(OLD, NEW)


def downgrade() -> None:
    _rename(NEW, OLD)
