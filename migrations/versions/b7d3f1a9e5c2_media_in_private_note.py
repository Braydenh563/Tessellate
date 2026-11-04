"""media_uploads: in_private_note, the files a private note embeds (SEC-A2)

Additive only. False for every older row, so a database that never gets the
column from this step reads every file as outside a private note.

Revision ID: b7d3f1a9e5c2
Revises: c8e4a1f7d3b9
Create Date: 2026-11-04

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
revision: str = "b7d3f1a9e5c2"
down_revision: Union[str, Sequence[str], None] = "c8e4a1f7d3b9"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def _existing_columns() -> set:
    """What `media_uploads` already has.

    `_add_missing_columns()` in `core/database.py` runs on every startup ahead
    of the Alembic step, so on most databases the column is already there by
    the time this runs, and a plain `add_column` would fail with "duplicate
    column name" and leave `alembic_version` stuck.
    """
    bind = op.get_bind()
    return {row[1] for row in bind.exec_driver_sql('PRAGMA table_info("media_uploads")')}


def upgrade() -> None:
    """Upgrade schema."""
    existing = _existing_columns()
    with op.batch_alter_table("media_uploads", schema=None) as batch_op:
        if "in_private_note" not in existing:
            batch_op.add_column(
                sa.Column("in_private_note", sa.Boolean(), nullable=False, server_default=sa.false())
            )


def downgrade() -> None:
    """Downgrade schema."""
    existing = _existing_columns()
    with op.batch_alter_table("media_uploads", schema=None) as batch_op:
        if "in_private_note" in existing:
            batch_op.drop_column("in_private_note")
