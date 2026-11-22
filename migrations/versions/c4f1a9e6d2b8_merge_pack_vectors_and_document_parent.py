"""merge: float16 packed vectors and the document parent

Joins the two heads two branches left (b5d2e8a1c7f3, b6d2f8a4c1e9). No schema
change of its own.

Revision ID: c4f1a9e6d2b8
Revises: b5d2e8a1c7f3, b6d2f8a4c1e9
Create Date: 2026-11-22

"""
from typing import Sequence, Union


# revision identifiers, used by Alembic. See the baseline migration for why
# __all__ names them.
__all__ = ["revision", "down_revision", "branch_labels", "depends_on"]
revision: str = "c4f1a9e6d2b8"
down_revision: Union[str, Sequence[str], None] = ("b5d2e8a1c7f3", "b6d2f8a4c1e9")
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    pass


def downgrade() -> None:
    pass
