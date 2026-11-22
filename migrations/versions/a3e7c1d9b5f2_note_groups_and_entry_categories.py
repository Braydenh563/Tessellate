"""note_groups, note_group_members, entry_categories (L-world-class-172, 173)

Additive only: three new tables, empty until a person uses them. A note's one
`entries.category_id` is untouched; `entry_categories` holds the further
categories a person added, and the groups are sets gathered by hand.

Revision ID: a3e7c1d9b5f2
Revises: a3d7c1e9b5f4
Create Date: 2026-11-21

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic. See the baseline migration for why
# __all__ names them.
__all__ = ["revision", "down_revision", "branch_labels", "depends_on"]
revision: str = "a3e7c1d9b5f2"
down_revision: Union[str, Sequence[str], None] = "a3d7c1e9b5f4"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def _tables() -> set:
    """`create_all()` runs ahead of Alembic on startup, so the tables are
    usually there already."""
    return set(sa.inspect(op.get_bind()).get_table_names())


def upgrade() -> None:
    """Upgrade schema."""
    have = _tables()
    if "note_groups" not in have:
        op.create_table(
            "note_groups",
            sa.Column("id", sa.Integer(), nullable=False),
            sa.Column("name", sa.String(length=100), nullable=False),
            sa.Column("created_at", sa.DateTime(), nullable=False),
            sa.Column("workspace_id", sa.String(), server_default="default", nullable=False),
            sa.PrimaryKeyConstraint("id"),
            sa.UniqueConstraint("workspace_id", "name", name="uq_note_groups_workspace_name"),
        )
        op.create_index("ix_note_groups_workspace_id", "note_groups", ["workspace_id"])
    if "note_group_members" not in have:
        op.create_table(
            "note_group_members",
            sa.Column("group_id", sa.Integer(), nullable=False),
            sa.Column("entry_id", sa.Integer(), nullable=False),
            sa.Column("added_at", sa.DateTime(), nullable=False),
            sa.ForeignKeyConstraint(["group_id"], ["note_groups.id"], ondelete="CASCADE"),
            sa.ForeignKeyConstraint(["entry_id"], ["entries.id"], ondelete="CASCADE"),
            sa.PrimaryKeyConstraint("group_id", "entry_id"),
        )
        op.create_index("ix_note_group_members_entry_id", "note_group_members", ["entry_id"])
    if "entry_categories" not in have:
        op.create_table(
            "entry_categories",
            sa.Column("entry_id", sa.Integer(), nullable=False),
            sa.Column("category_id", sa.Integer(), nullable=False),
            sa.ForeignKeyConstraint(["entry_id"], ["entries.id"], ondelete="CASCADE"),
            sa.ForeignKeyConstraint(["category_id"], ["categories.id"], ondelete="CASCADE"),
            sa.PrimaryKeyConstraint("entry_id", "category_id"),
        )
        op.create_index("ix_entry_categories_category_id", "entry_categories", ["category_id"])


def downgrade() -> None:
    """Downgrade schema."""
    have = _tables()
    for table in ("entry_categories", "note_group_members", "note_groups"):
        if table in have:
            op.drop_table(table)
