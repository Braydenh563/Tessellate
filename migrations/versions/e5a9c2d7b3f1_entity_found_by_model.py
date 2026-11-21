"""entities: model, the model that found the name (WORLD_CLASS_PLAN B4 stamp)

Additive only. Null on every existing row: which model found an older name was
never kept, and the page then says only when it was found.

Revision ID: e5a9c2d7b3f1
Revises: c3e8a1f5d9b2
Create Date: 2026-11-21

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic. See the baseline migration for why
# __all__ names them.
__all__ = ["revision", "down_revision", "branch_labels", "depends_on"]
revision: str = "e5a9c2d7b3f1"
down_revision: Union[str, Sequence[str], None] = "c3e8a1f5d9b2"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def _existing_columns() -> set:
    """`_add_missing_columns()` in `core/database.py` runs ahead of Alembic on
    every startup, so the column is usually there already; a plain
    `add_column` would then fail with "duplicate column name"."""
    bind = op.get_bind()
    return {row[1] for row in bind.exec_driver_sql('PRAGMA table_info("entities")')}


def upgrade() -> None:
    """Upgrade schema."""
    if "model" not in _existing_columns():
        with op.batch_alter_table("entities", schema=None) as batch_op:
            batch_op.add_column(sa.Column("model", sa.String(length=80), nullable=True))


def downgrade() -> None:
    """Downgrade schema."""
    if "model" in _existing_columns():
        with op.batch_alter_table("entities", schema=None) as batch_op:
            batch_op.drop_column("model")
