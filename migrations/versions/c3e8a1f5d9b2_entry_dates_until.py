"""entry_dates: until, the last day of a range a note names

Additive only (TIMELINE_PLAN decision 13): "away 3 to 7 March" is one date row
on its first day with `until` its last, so the calendar runs it through the
range. Null on every existing row, which is what each of them is: one day.

Revision ID: c3e8a1f5d9b2
Revises: a7d3b9e2c4f6
Create Date: 2026-11-12

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic. See the baseline migration for why
# __all__ names them.
__all__ = ["revision", "down_revision", "branch_labels", "depends_on"]
revision: str = "c3e8a1f5d9b2"
down_revision: Union[str, Sequence[str], None] = "a7d3b9e2c4f6"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def _existing_columns() -> set:
    """`_add_missing_columns()` in `core/database.py` runs ahead of Alembic on
    every startup, so the column is usually there already; a plain
    `add_column` would then fail with "duplicate column name"."""
    bind = op.get_bind()
    return {row[1] for row in bind.exec_driver_sql('PRAGMA table_info("entry_dates")')}


def upgrade() -> None:
    """Upgrade schema."""
    if "until" not in _existing_columns():
        with op.batch_alter_table("entry_dates", schema=None) as batch_op:
            batch_op.add_column(sa.Column("until", sa.DateTime(), nullable=True))


def downgrade() -> None:
    """Downgrade schema."""
    if "until" in _existing_columns():
        with op.batch_alter_table("entry_dates", schema=None) as batch_op:
            batch_op.drop_column("until")
