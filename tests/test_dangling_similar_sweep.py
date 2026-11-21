"""L-general-21: `filing_similar_id` is not a foreign key, so Housekeeping
clears a mark that names a note no longer in the notebook."""

from tessellate.core import passes
from tessellate.core.database import Entry


def _note(session, text, similar=None):
    entry = Entry(content=text, filing_similar_id=similar)
    session.add(entry)
    session.commit()
    return entry


def test_a_mark_to_a_deleted_note_is_cleared_and_a_live_one_kept(session):
    kept = _note(session, "the original")
    gone = _note(session, "purged later")
    points_live = _note(session, "a copy of the original", similar=kept.id)
    points_gone = _note(session, "a copy of the purged one", similar=gone.id)
    session.delete(gone)
    session.commit()

    assert passes.clear_dangling_similar(session) == 1
    session.expire_all()
    assert session.get(Entry, points_live.id).filing_similar_id == kept.id
    assert session.get(Entry, points_gone.id).filing_similar_id is None
    assert passes.clear_dangling_similar(session) == 0


def test_housekeeping_runs_the_sweep_at_start_and_on_run_now():
    from tessellate.api import app

    assert passes._clear_dangling_similar in passes.MAINTENANCE_STEPS
    #: A wrapper since CodeQL's unused-global finding on the alias: calling the
    #: start-up step runs the sweep in `passes` (the intent: start-up sweeps).
    called = []
    original = passes._clear_dangling_similar
    passes._clear_dangling_similar = lambda: called.append(1)
    try:
        app._clear_dangling_similar()
    finally:
        passes._clear_dangling_similar = original
    assert called == [1]
    import inspect

    assert '"_clear_dangling_similar"' in inspect.getsource(app._startup_maintenance)
