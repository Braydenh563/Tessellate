"""Dangling `filing_similar_id` values are cleared once per launch (L-general-21).

The column is not a ForeignKey on purpose, so deleting the note it names
leaves the id behind; the sweep nulls those and leaves live pointers alone.
"""

from __future__ import annotations

import inspect

from tessellate.api import app as app_module
from tessellate.core import deps
from tessellate.core.database import Entry
from tessellate.entry import filing_sweep


def test_only_pointers_to_missing_notes_are_cleared(app_state):
    session = deps.get_db().session()
    try:
        kept, gone = Entry(content="kept"), Entry(content="gone")
        session.add_all([kept, gone])
        session.flush()
        live = Entry(content="points at a live note", filing_similar_id=kept.id)
        stale = Entry(content="points at a deleted note", filing_similar_id=gone.id)
        none = Entry(content="no pointer")
        session.add_all([live, stale, none])
        session.flush()
        session.delete(gone)
        session.commit()
        assert filing_sweep.clear_dangling(session) == 1
        session.expire_all()
        assert (live.filing_similar_id, stale.filing_similar_id, none.filing_similar_id) == (kept.id, None, None)
        assert filing_sweep.clear_dangling(session) == 0
    finally:
        session.close()


def test_the_sweep_runs_with_the_launch_housekeeping(app_state):
    assert "_clear_dangling_filing_pointers" in inspect.getsource(app_module._startup_maintenance)
    app_module._clear_dangling_filing_pointers()
