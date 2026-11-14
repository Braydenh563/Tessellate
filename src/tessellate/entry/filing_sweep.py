"""Clear `Entry.filing_similar_id` values that point at a note which is gone.

The column is deliberately not a ForeignKey (a deleted note must never be
held up by an advisory pointer), so a deletion leaves the id behind.
`routes_entries._filing_similar` already reads a missing target as "no
duplicate"; this is the once-per-launch tidy-up of the same fact, so the
column stays honest for anything that reads it raw (L-general-21).
"""

from __future__ import annotations

import logging

from sqlalchemy import select, update
from sqlalchemy.orm import Session

from tessellate.core.database import Entry

logger = logging.getLogger("tessellate.startup")


def clear_dangling(session: Session) -> int:
    """Set every pointer whose target row does not exist to NULL; return how many."""
    live = select(Entry.id)
    done = session.execute(
        update(Entry)
        .where(Entry.filing_similar_id.is_not(None), Entry.filing_similar_id.not_in(live))
        .values(filing_similar_id=None)
        .execution_options(synchronize_session=False)
    )
    session.commit()
    cleared = done.rowcount or 0
    if cleared:
        logger.info("cleared %s dangling filing_similar_id pointer(s)", cleared)
    return cleared
