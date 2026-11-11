"""media_uploads: board_only, a picture that stays on its board until Save to Library

Additive only. A boolean, false on every existing row, which is the honest
answer: those pictures were all filed.

Revision ID: a7d3b9e2c4f6
Revises: e5a1c8d3f7b2
Create Date: 2026-11-11

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
revision: str = "a7d3b9e2c4f6"
down_revision: Union[str, Sequence[str], None] = "e5a1c8d3f7b2"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def _existing_columns() -> set:
    """What `media_uploads` already has.

    The same guard as the other additive migrations: `_add_missing_columns()`
    in `core/database.py` runs on every startup ahead of the Alembic step, so
    on most databases the column is already there and a plain `add_column`
    would fail with "duplicate column name" and leave `alembic_version` stuck.
    """
    bind = op.get_bind()
    return {row[1] for row in bind.exec_driver_sql('PRAGMA table_info("media_uploads")')}


def upgrade() -> None:
    """Upgrade schema."""
    if "board_only" not in _existing_columns():
        with op.batch_alter_table("media_uploads", schema=None) as batch_op:
            batch_op.add_column(
                sa.Column("board_only", sa.Boolean(), nullable=False, server_default=sa.false())
            )


def downgrade() -> None:
    """Downgrade schema."""
    if "board_only" in _existing_columns():
        with op.batch_alter_table("media_uploads", schema=None) as batch_op:
            batch_op.drop_column("board_only")
