"""entries: origin_document_id, the document a note was extracted from

Additive only. A nullable integer, null on every existing row: nothing
recorded where those notes came from, and null says so (L-general-42).

Revision ID: c7e1a3b5d9f2
Revises: b6d2f8a4c1e9
Create Date: 2026-11-22

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
__all__ = ["revision", "down_revision", "branch_labels", "depends_on"]
revision: str = "c7e1a3b5d9f2"
down_revision: Union[str, Sequence[str], None] = "b6d2f8a4c1e9"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def _existing_columns() -> set:
    """What `entries` already has: the startup auto-migrator may have added the column first."""
    bind = op.get_bind()
    return {row[1] for row in bind.exec_driver_sql('PRAGMA table_info("entries")')}


def upgrade() -> None:
    """Upgrade schema."""
    if "origin_document_id" not in _existing_columns():
        with op.batch_alter_table("entries", schema=None) as batch_op:
            batch_op.add_column(sa.Column("origin_document_id", sa.Integer(), nullable=True))


def downgrade() -> None:
    """Downgrade schema."""
    if "origin_document_id" in _existing_columns():
        with op.batch_alter_table("entries", schema=None) as batch_op:
            batch_op.drop_column("origin_document_id")
