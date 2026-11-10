"""Private spaces: spaces.is_private, documents.is_private and the two
sealed_by_space flags (INBOX 1727)

Additive only. False for every older row: no space was private, no document
was sealed, and nothing was sealed by a space, so every existing row reads
exactly as it did.

Revision ID: d2f6b8a4c1e7
Revises: a9c3e7b1d5f4
Create Date: 2026-11-10

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
#
# Read off this module by attribute name by Alembic's ScriptDirectory, never
# imported anywhere in this repo: the baseline migration's own comment
# explains why CodeQL calls these unused and why __all__ answers it without
# changing any behaviour.
__all__ = ["revision", "down_revision", "branch_labels", "depends_on"]
revision: str = "d2f6b8a4c1e7"
down_revision: Union[str, Sequence[str], None] = "a9c3e7b1d5f4"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

#: Table, then the flags it gains.
_COLUMNS = {
    "spaces": ("is_private",),
    "documents": ("is_private", "sealed_by_space"),
    "entries": ("sealed_by_space",),
}


def _existing_columns(table: str) -> set:
    """What `table` already has: `_add_missing_columns()` in
    `core/database.py` runs ahead of this step on most startups, and a plain
    `add_column` would then fail with "duplicate column name"."""
    bind = op.get_bind()
    return {row[1] for row in bind.exec_driver_sql(f'PRAGMA table_info("{table}")')}


def upgrade() -> None:
    """Upgrade schema."""
    for table, names in _COLUMNS.items():
        existing = _existing_columns(table)
        with op.batch_alter_table(table, schema=None) as batch_op:
            for name in names:
                if name not in existing:
                    batch_op.add_column(sa.Column(name, sa.Boolean(), nullable=False, server_default=sa.false()))


def downgrade() -> None:
    """Downgrade schema."""
    for table, names in _COLUMNS.items():
        existing = _existing_columns(table)
        with op.batch_alter_table(table, schema=None) as batch_op:
            for name in names:
                if name in existing:
                    batch_op.drop_column(name)
