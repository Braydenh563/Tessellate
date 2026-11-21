"""One fixed clock for a test (CLAUDE.md section 8: tests use a fixed clock, never the real one).

`user_now` and `utcnow` are imported by name into many modules (`from
tessellate.core.config import user_now`), so patching one module left the
others on the real clock: on 2026-11-21 a note dated "21 November" read as
today's and "the 16th" was in the past. `pin_clock` patches the roots and every
loaded module holding them, and `clock.today`, so one call covers the app: the
person's clock, the UTC clock, a row's own stamp (`database.stamp` reads
`utcnow` by name) and the calendar day. `tests/test_fixed_clock_lint.py` keeps
tests on it."""

from __future__ import annotations

import sys
from collections.abc import Callable
from datetime import datetime, timezone

from tessellate.core import clock, config, database

#: The suite's fixed instant: a Saturday at noon UTC, the day `conftest.SUITE_DAY`
#: and `_frozen_clock.FIXED_NOW` use. A test that builds data relative to "now"
#: builds it from this and pins it, so nothing it asserts moves with the calendar.
SUITE_NOW = datetime(2026, 8, 1, 12, 0, tzinfo=timezone.utc)
#: The same instant as this machine's naive wall time (what `datetime.now()` gave).
SUITE_LOCAL = SUITE_NOW.astimezone().replace(tzinfo=None)

#: Every module holding `user_now` or `utcnow` by name (a module-level `from
#: ... import`), written out: the pin is this fixed set of pairs, not a sweep
#: of `sys.modules` with computed names (that sweep cost CodeQL's points-to
#: three times its run). `tests/test_fixed_clock_lint.py` fails when a module
#: imports either name and is missing here, or is listed and no longer does.
HOLDERS: tuple[tuple[str, str], ...] = (
    ("tessellate.ai.autonomous", "utcnow"),
    ("tessellate.ai.composer", "user_now"),
    ("tessellate.ai.entities", "utcnow"),
    ("tessellate.ai.facts", "utcnow"),
    ("tessellate.ai.learned_audit_run", "utcnow"),
    ("tessellate.ai.notebook_stats", "utcnow"),
    ("tessellate.ai.questions", "utcnow"),
    ("tessellate.ai.stats_ask", "utcnow"),
    ("tessellate.ai.tools._common", "user_now"),
    ("tessellate.api.chat_said", "user_now"),
    ("tessellate.api.chat_service", "user_now"),
    ("tessellate.api.chat_turn", "user_now"),
    ("tessellate.api.routes_board_library", "utcnow"),
    ("tessellate.api.routes_chat", "user_now"),
    ("tessellate.api.routes_code_snippets", "utcnow"),
    ("tessellate.api.routes_conversations", "utcnow"),
    ("tessellate.api.routes_documents", "user_now"),
    ("tessellate.api.routes_documents", "utcnow"),
    ("tessellate.api.routes_editor", "user_now"),
    ("tessellate.api.routes_entries", "utcnow"),
    ("tessellate.api.routes_insights", "user_now"),
    ("tessellate.api.routes_insights", "utcnow"),
    ("tessellate.api.routes_learned", "utcnow"),
    ("tessellate.api.routes_meetings", "utcnow"),
    ("tessellate.api.routes_read", "utcnow"),
    ("tessellate.api.routes_recordings", "utcnow"),
    ("tessellate.api.routes_reminders", "utcnow"),
    ("tessellate.api.routes_settings", "utcnow"),
    ("tessellate.api.routes_settings_transfer", "utcnow"),
    ("tessellate.api.routes_statistics", "user_now"),
    ("tessellate.api.routes_timeline", "utcnow"),
    ("tessellate.api.routes_vision", "utcnow"),
    ("tessellate.api.routes_webclip", "user_now"),
    ("tessellate.core.events", "utcnow"),
    ("tessellate.core.reading_bin", "utcnow"),
    ("tessellate.core.recordings", "utcnow"),
    ("tessellate.core.vault", "utcnow"),
    ("tessellate.entry.bin", "utcnow"),
    ("tessellate.entry.folder_sync", "utcnow"),
    ("tessellate.entry.manager", "utcnow"),
    ("tessellate.entry.manager_purge", "utcnow"),
    ("tessellate.entry.manager_wiki", "utcnow"),
    ("tessellate.entry.opens", "utcnow"),
    ("tessellate.entry.tidy", "utcnow"),
    ("tessellate.repo.bookmarks", "utcnow"),
    ("tessellate.repo.documents", "utcnow"),
    ("tessellate.repo.goals", "utcnow"),
    ("tessellate.repo.reminders", "utcnow"),
    ("tessellate.search.webstore", "utcnow"),
    ("tests.test_date_field_when", "utcnow"),
    ("tests.test_digest_structure", "utcnow"),
    ("tests.test_document_revisions", "utcnow"),
    ("tests.test_engine_dialogue", "user_now"),
    ("tests.test_engine_plan", "user_now"),
    ("tests.test_import_bin_clock", "utcnow"),
    ("tests.test_insight_verdicts", "user_now"),
    ("tests.test_insights_api", "utcnow"),
    ("tests.test_night_pairs", "utcnow"),
    ("tests.test_pair_passes_paths", "utcnow"),
    ("tests.test_properties_never_in_previews", "utcnow"),
    ("tests.test_query_plans", "utcnow"),
    ("tests.test_questions_own", "utcnow"),
    ("tests.test_questions_spec", "utcnow"),
    ("tests.test_recordings", "utcnow"),
    ("tests.test_recycle_bin", "utcnow"),
    ("tests.test_reminder_scoped_token", "utcnow"),
    ("tests.test_staleness", "utcnow"),
    ("tests.test_tensions_derive_paths", "utcnow"),
    ("tests.test_tensions_table_b4", "utcnow"),
    ("tests.test_timeline", "utcnow"),
    ("tests.test_timeline_query_count", "utcnow"),
    ("tests.test_undo_bin", "utcnow"),
    ("tests.test_web_store_1111", "utcnow"),
)

_REAL_USER_NOW = config.user_now
_REAL_UTCNOW = database.utcnow


def pin_clock(monkeypatch, now: datetime | Callable[[], datetime]) -> None:  # noqa: ANN001
    """Every clock answers `now` (or `now()`, for a clock a test moves).

    A naive `now` is the person's wall time on this machine's zone; an aware
    one is an instant `user_now` reads in the person's zone. `utcnow` gives
    the same instant in UTC."""

    def moment() -> datetime:
        return now() if callable(now) else now

    def user(settings=None):  # noqa: ANN001, ANN202
        # A naive pin is the wall time itself; an aware one is an instant,
        # read in the person's zone as the real `user_now` reads it.
        at = moment()
        return at if at.tzinfo is None else config.on_users_clock(settings, at, at.tzinfo)

    def utc() -> datetime:
        return moment().astimezone(timezone.utc)

    user.pinned = utc.pinned = True  # type: ignore[attr-defined]

    monkeypatch.setattr(config, "user_now", user)
    monkeypatch.setattr(database, "utcnow", utc)
    monkeypatch.setattr(clock, "today", lambda: moment().date())
    # Every holder, the tests' own too: a test that imported `utcnow` by name
    # and calls it reads the pinned clock like the app does.
    fakes = {"user_now": user, "utcnow": utc}
    for name, attr in HOLDERS:
        if (module := sys.modules.get(name)) is not None:
            monkeypatch.setattr(module, attr, fakes[attr])


def unpin_late_imports() -> None:
    """Put the real clocks back on a module first imported while a clock was
    pinned (an app module, or a test file collected late): its `from ...
    import user_now` took the pinned function, which monkeypatch never set
    and so never undoes (`conftest._unpin_clock`)."""
    reals = {"user_now": _REAL_USER_NOW, "utcnow": _REAL_UTCNOW}
    for name, attr in HOLDERS:
        module = sys.modules.get(name)
        if module is not None and getattr(getattr(module, attr, None), "pinned", False) is True:
            setattr(module, attr, reals[attr])
