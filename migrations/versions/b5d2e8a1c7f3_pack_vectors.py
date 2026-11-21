"""store embeddings at half width (L-world-class-174)

`core/packed_vector.py` packs a new vector as float16 on write and reads either
width, so this only converts the rows already there (in batches, so a large
notebook does not hold them all). The file keeps its size until the next
VACUUM, which the nightly pass runs (`autonomous._vacuum`). Downgrade writes
every row back as float32, which is what an older build reads.

Revision ID: b5d2e8a1c7f3
Revises: a3e7c1d9b5f2
Create Date: 2026-11-21

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

from tessellate.core import packed_vector


# revision identifiers, used by Alembic. See the baseline migration for why
# __all__ names them.
__all__ = ["revision", "down_revision", "branch_labels", "depends_on"]
revision: str = "b5d2e8a1c7f3"
down_revision: Union[str, Sequence[str], None] = "a3e7c1d9b5f2"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

TABLES = ("embeddings", "embeddings_staged", "chunk_vectors")
BATCH = 500


def _convert(convert) -> None:  # noqa: ANN001
    bind = op.get_bind()
    present = set(sa.inspect(bind).get_table_names())
    for table in TABLES:
        if table not in present:
            continue
        last = 0
        while True:
            rows = bind.execute(
                sa.text(f"SELECT id, embedding FROM {table} WHERE id > :last ORDER BY id LIMIT :n"),
                {"last": last, "n": BATCH},
            ).fetchall()
            if not rows:
                break
            changed = []
            for row_id, blob in rows:
                new = convert(bytes(blob)) if blob is not None else blob
                if new != blob:
                    changed.append({"i": row_id, "b": new})
            if changed:
                bind.execute(sa.text(f"UPDATE {table} SET embedding = :b WHERE id = :i"), changed)
            last = rows[-1][0]


def upgrade() -> None:
    _convert(packed_vector.pack)


def downgrade() -> None:
    _convert(packed_vector.unpack)
