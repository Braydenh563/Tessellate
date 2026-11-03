"""documents: threads, the comment threads behind the inline remarks

Additive only. A JSON text of author, time, replies and resolved state per
remark (core/docthreads.py); "" is none, as every older row reads, so a
database that never gets the column from this step is still correct.

Revision ID: c8e4a1f7d3b9
Revises: e2a6c8d4b0f7
Create Date: 2026-11-03

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
revision: str = "c8e4a1f7d3b9"
down_revision: Union[str, Sequence[str], None] = "e2a6c8d4b0f7"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def _existing_columns() -> set:
    """What `documents` already has.

    `_add_missing_columns()` in `core/database.py` runs on every startup ahead
    of the Alembic step, so on most databases the column is already there by
    the time this runs, and a plain `add_column` would fail with "duplicate
    column name" and leave `alembic_version` stuck.
    """
    bind = op.get_bind()
    return {row[1] for row in bind.exec_driver_sql('PRAGMA table_info("documents")')}


def upgrade() -> None:
    """Upgrade schema."""
    existing = _existing_columns()
    with op.batch_alter_table("documents", schema=None) as batch_op:
        if "threads" not in existing:
            batch_op.add_column(
                sa.Column("threads", sa.Text(), nullable=False, server_default=sa.text("''"))
            )


def downgrade() -> None:
    """Downgrade schema."""
    existing = _existing_columns()
    with op.batch_alter_table("documents", schema=None) as batch_op:
        if "threads" in existing:
            batch_op.drop_column("threads")
