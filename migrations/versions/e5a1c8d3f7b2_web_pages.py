"""web_pages: pages fetched in a chat, kept a week (CHAT_PLAN web-search store)

Additive only: one new table. `create_all()` usually made it first.

Revision ID: e5a1c8d3f7b2
Revises: d2f6b8a4c1e7
Create Date: 2026-11-11

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic. See the baseline migration for the
# __all__ (read by attribute name, never imported).
__all__ = ["revision", "down_revision", "branch_labels", "depends_on"]
revision: str = "e5a1c8d3f7b2"
down_revision: Union[str, Sequence[str], None] = "d2f6b8a4c1e7"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def _tables() -> set:
    bind = op.get_bind()
    return {row[0] for row in bind.exec_driver_sql("SELECT name FROM sqlite_master WHERE type='table'")}


def upgrade() -> None:
    """Upgrade schema."""
    if "web_pages" not in _tables():
        op.create_table(
            "web_pages",
            sa.Column("id", sa.Integer(), primary_key=True),
            sa.Column("url_key", sa.String(length=2000), nullable=False),
            sa.Column("url", sa.String(length=2000), nullable=False),
            sa.Column("title", sa.String(length=500), nullable=False),
            sa.Column("domain", sa.String(length=255), nullable=False),
            sa.Column("text", sa.Text(), nullable=False),
            sa.Column("links", sa.JSON(), nullable=True),
            sa.Column("fetched_at", sa.DateTime(), nullable=False),
        )
        op.create_index("ix_web_pages_url_key", "web_pages", ["url_key"], unique=True)
        op.create_index("ix_web_pages_fetched_at", "web_pages", ["fetched_at"])


def downgrade() -> None:
    """Downgrade schema."""
    if "web_pages" in _tables():
        op.drop_table("web_pages")
