"""spaces: the seeded "Default Space" is "Default space"

Sentence case is the app's copy rule (sweep 1028b W30). Only a row still
carrying the exact seeded name is renamed, so a space the person named
themselves is never touched; if a space already holds the new name (the
create route now refuses duplicates, older data may not), the old name stays
rather than making two the same.

Revision ID: e2a6c8d4b0f7
Revises: f1b3c5d7e9a2
Create Date: 2026-10-28

"""
from typing import Sequence, Union

from alembic import op


# revision identifiers, used by Alembic. See the baseline migration for why
# __all__ names them.
__all__ = ["revision", "down_revision", "branch_labels", "depends_on"]
revision: str = "e2a6c8d4b0f7"
down_revision: Union[str, Sequence[str], None] = "f1b3c5d7e9a2"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def _rename(old: str, new: str) -> None:
    bind = op.get_bind()
    tables = {row[0] for row in bind.exec_driver_sql("SELECT name FROM sqlite_master WHERE type='table'")}
    if "spaces" not in tables:
        return
    op.execute(
        f"UPDATE spaces SET name = '{new}' WHERE id = 'default' AND name = '{old}' "
        f"AND NOT EXISTS (SELECT 1 FROM spaces WHERE id <> 'default' AND lower(trim(name)) = lower('{new}'))"
    )


def upgrade() -> None:
    """Upgrade schema."""
    _rename("Default Space", "Default space")


def downgrade() -> None:
    """Downgrade schema."""
    _rename("Default space", "Default Space")
