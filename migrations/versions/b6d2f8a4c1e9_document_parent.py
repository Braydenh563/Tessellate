"""documents: parent_id, the document a sub-page sits under

Additive only (DOCUMENTS_PLAN D14, L-documents-44). Null on every existing
row, which is what each of them is: a page at the top level.

Revision ID: b6d2f8a4c1e9
Revises: c3e8a1f5d9b2
Create Date: 2026-11-14

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic. See the baseline migration for why
# __all__ names them.
__all__ = ["revision", "down_revision", "branch_labels", "depends_on"]
revision: str = "b6d2f8a4c1e9"
down_revision: Union[str, Sequence[str], None] = "c3e8a1f5d9b2"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def _existing_columns() -> set:
    """`_add_missing_columns()` in `core/database.py` runs ahead of Alembic on
    every startup, so the column is usually there already."""
    bind = op.get_bind()
    return {row[1] for row in bind.exec_driver_sql('PRAGMA table_info("documents")')}


def upgrade() -> None:
    """Upgrade schema."""
    if "parent_id" not in _existing_columns():
        with op.batch_alter_table("documents", schema=None) as batch_op:
            batch_op.add_column(sa.Column("parent_id", sa.Integer(), nullable=True))


def downgrade() -> None:
    """Downgrade schema."""
    if "parent_id" in _existing_columns():
        with op.batch_alter_table("documents", schema=None) as batch_op:
            batch_op.drop_column("parent_id")
