"""conversations: folder, the name a saved chat is filed under

Additive only. A short string, empty on every existing row: no chat was filed
before the sidebar could group by folder.

Revision ID: d7a2c4e8b1f6
Revises: c3e8a1f5d9b2
Create Date: 2026-11-21

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
revision: str = "d7a2c4e8b1f6"
down_revision: Union[str, Sequence[str], None] = "c3e8a1f5d9b2"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def _existing_columns() -> set:
    """What `conversations` already has.

    The same guard as the other additive migrations: `_add_missing_columns()`
    in `core/database.py` runs on every startup ahead of the Alembic step, so
    on most databases the column is already there and a plain `add_column`
    would fail with "duplicate column name" and leave `alembic_version` stuck.
    """
    bind = op.get_bind()
    return {row[1] for row in bind.exec_driver_sql('PRAGMA table_info("conversations")')}


def upgrade() -> None:
    """Upgrade schema."""
    if "folder" not in _existing_columns():
        with op.batch_alter_table("conversations", schema=None) as batch_op:
            batch_op.add_column(sa.Column("folder", sa.String(length=60), nullable=False, server_default=""))


def downgrade() -> None:
    """Downgrade schema."""
    if "folder" in _existing_columns():
        with op.batch_alter_table("conversations", schema=None) as batch_op:
            batch_op.drop_column("folder")
