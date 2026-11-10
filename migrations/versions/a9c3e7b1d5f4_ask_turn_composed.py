"""ask_turns: composed, an answer no model wrote (W1 A5)

Additive only. False for every older row: nothing recorded who wrote those,
so they keep the model counter they were shown with.

Revision ID: a9c3e7b1d5f4
Revises: b7d3f1a9e5c2
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
revision: str = "a9c3e7b1d5f4"
down_revision: Union[str, Sequence[str], None] = "b7d3f1a9e5c2"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def _existing_columns() -> set:
    """What `ask_turns` already has: `_add_missing_columns()` may have added it."""
    bind = op.get_bind()
    return {row[1] for row in bind.exec_driver_sql('PRAGMA table_info("ask_turns")')}


def upgrade() -> None:
    """Upgrade schema."""
    if "composed" not in _existing_columns():
        with op.batch_alter_table("ask_turns", schema=None) as batch_op:
            batch_op.add_column(
                sa.Column("composed", sa.Boolean(), nullable=False, server_default=sa.false())
            )


def downgrade() -> None:
    """Downgrade schema."""
    if "composed" in _existing_columns():
        with op.batch_alter_table("ask_turns", schema=None) as batch_op:
            batch_op.drop_column("composed")
