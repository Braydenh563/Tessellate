"""merge: document sub-pages and chat folders, two additive branches off c3e8a1f5d9b2

Both were written on separate branches and met at a base merge (2026-11-22), leaving
two heads, which the app refuses (`frozen_smoke` expects one). Neither touches the
other's table, so the merge is empty: a database on either branch, or on neither,
upgrades to this one head.

Revision ID: e4c9a7b2d5f1
Revises: b6d2f8a4c1e9, d7a2c4e8b1f6
Create Date: 2026-11-22

"""
from typing import Sequence, Union


# revision identifiers, used by Alembic.
#
# Read off this module by attribute name by Alembic's ScriptDirectory, never
# imported anywhere in this repo: the baseline migration's own comment
# explains why CodeQL calls these unused and why __all__ answers it without
# changing any behaviour.
__all__ = ["revision", "down_revision", "branch_labels", "depends_on"]
revision: str = "e4c9a7b2d5f1"
down_revision: Union[str, Sequence[str], None] = ("b6d2f8a4c1e9", "d7a2c4e8b1f6")
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    pass


def downgrade() -> None:
    pass
