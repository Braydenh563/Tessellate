"""job_run_log: finished runs kept across restarts (L-world-class-570)

Additive only: a new table, empty until runs finish. The History tab read a
ring in process memory that a restart emptied.

Revision ID: f7a1c3e5b9d2
Revises: e5a9c2d7b3f1
Create Date: 2026-11-21

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic. See the baseline migration for why
# __all__ names them.
__all__ = ["revision", "down_revision", "branch_labels", "depends_on"]
revision: str = "f7a1c3e5b9d2"
down_revision: Union[str, Sequence[str], None] = "e5a9c2d7b3f1"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def _tables() -> set:
    """`create_all()` runs ahead of Alembic on startup, so the table is
    usually there already."""
    return set(sa.inspect(op.get_bind()).get_table_names())


def upgrade() -> None:
    """Upgrade schema."""
    if "job_run_log" in _tables():
        return
    op.create_table(
        "job_run_log",
        sa.Column("run_id", sa.String(length=40), nullable=False),
        sa.Column("kind", sa.String(length=40), nullable=False),
        sa.Column("title", sa.String(length=400), nullable=False),
        sa.Column("label", sa.String(length=400), nullable=False),
        sa.Column("origin", sa.String(length=20), nullable=False),
        sa.Column("why", sa.String(length=400), nullable=False),
        sa.Column("outcome", sa.String(length=12), nullable=False),
        sa.Column("detail", sa.String(length=400), nullable=False),
        sa.Column("started", sa.Float(), nullable=False),
        sa.Column("ended", sa.Float(), nullable=False),
        sa.Column("duration_ms", sa.Float(), nullable=True),
        sa.Column("count", sa.Integer(), nullable=False),
        sa.Column("lines", sa.JSON(), nullable=False),
        sa.Column("logged_at", sa.DateTime(), nullable=False),
        sa.PrimaryKeyConstraint("run_id"),
    )
    op.create_index("ix_job_run_log_ended", "job_run_log", ["ended"])
    op.create_index("ix_job_run_log_logged_at", "job_run_log", ["logged_at"])


def downgrade() -> None:
    """Downgrade schema."""
    if "job_run_log" in _tables():
        op.drop_table("job_run_log")
