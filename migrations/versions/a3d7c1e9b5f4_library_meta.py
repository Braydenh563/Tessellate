"""documents and media_uploads: tags, category_id, properties

Additive only (WORLD_CLASS_PLAN decision 65, L-world-class-393): the selection
bars of the Library's Documents and Media lists file what they hold the way the
Notes bar does. "[]", null and "{}" on every existing row: none had any.

Revision ID: a3d7c1e9b5f4
Revises: f7a1c3e5b9d2
Create Date: 2026-11-21

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic. See the baseline migration for why
# __all__ names them.
__all__ = ["revision", "down_revision", "branch_labels", "depends_on"]
revision: str = "a3d7c1e9b5f4"
down_revision: Union[str, Sequence[str], None] = "f7a1c3e5b9d2"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

TABLES = ("documents", "media_uploads")


def _existing_columns(table: str) -> set:
    """`_add_missing_columns()` in `core/database.py` runs ahead of Alembic on
    every startup, so the columns are usually there already; a plain
    `add_column` would then fail with "duplicate column name"."""
    bind = op.get_bind()
    return {row[1] for row in bind.exec_driver_sql(f'PRAGMA table_info("{table}")')}


def upgrade() -> None:
    """Upgrade schema."""
    for table in TABLES:
        have = _existing_columns(table)
        with op.batch_alter_table(table, schema=None) as batch_op:
            if "tags" not in have:
                batch_op.add_column(sa.Column("tags", sa.Text(), nullable=False, server_default="[]"))
            if "category_id" not in have:
                batch_op.add_column(sa.Column("category_id", sa.Integer(), nullable=True))
            if "properties" not in have:
                batch_op.add_column(sa.Column("properties", sa.Text(), nullable=False, server_default="{}"))


def downgrade() -> None:
    """Downgrade schema."""
    for table in TABLES:
        have = _existing_columns(table)
        with op.batch_alter_table(table, schema=None) as batch_op:
            for name in ("properties", "category_id", "tags"):
                if name in have:
                    batch_op.drop_column(name)
