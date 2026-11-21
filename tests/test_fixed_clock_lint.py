"""Tests use a fixed clock, never the real one (CLAUDE.md section 8).

On 2026-11-21 five composer tests failed on py3.13: their fixture pinned
`user_now` on two or three modules, and the modules it missed (`from
tessellate.core.config import user_now` binds the name at import) read the real
day, so "21 November" was today and "the 16th" had passed. `tests/_clock.pin_clock`
pins every holder at once; these lints keep the suite on it."""

from __future__ import annotations

import re
from pathlib import Path

TESTS = Path(__file__).resolve().parent

#: Files that read the real clock on purpose, measured 2026-11-21: they build
#: data relative to "now" (a reminder due in two hours, a note 40 days old) and
#: the route or store they call reads the same real clock, so nothing they
#: assert depends on the calendar. This set only shrinks: a new test pins its
#: day with `pin_clock` (or `_frozen_clock` for the reminder routes).
REAL_CLOCK_RELATIVE = {
    "_voice_eval.py",
    "test_acts.py",
    "test_agent_tools_api.py",
    "test_bin_documents_reminders_row30.py",
    "test_composer_1324.py",
    "test_composer_route_688.py",
    "test_conversation_retention.py",
    "test_dialogue_b8.py",
    "test_folder_roundtrip.py",
    "test_greeting_compose.py",
    "test_ics.py",
    "test_job_runs.py",
    "test_jobstore.py",
    "test_lan.py",
    "test_magic_add_wording.py",
    "test_meetings_644.py",
    "test_output_forms.py",
    "test_records_a3.py",
    "test_recurring_rules_l493.py",
    "test_related_elsewhere.py",
    "test_reminder_calendar_links.py",
    "test_reminder_edit_save.py",
    "test_reminder_notifier.py",
    "test_reminder_snooze_row34.py",
    "test_reminder_suggest.py",
    "test_reminder_targets_row15.py",
    "test_reminders_ics.py",
    "test_reminders_reschedule.py",
    "test_resurface_spec.py",
    "test_routes_batch.py",
    "test_small_b_1108_review.py",
    "test_starter_acts.py",
    "test_tensions.py",
    "test_text_utilities.py",
    "test_tidy.py",
    "test_timeline_calendar_window.py",
    "test_timeline_on_this_day.py",
}

_REAL_READ = re.compile(r"\b(?:date\.today|datetime\.now|datetime\.today|datetime\.utcnow)\(")
_ONE_MODULE = re.compile(r"""setattr\(\s*(?:[\w.]+\s*,\s*["']user_now["']|["'][\w.]+\.user_now["'])""")


def _sources():
    for path in sorted(TESTS.glob("*.py")):
        if path.name not in {"_clock.py", Path(__file__).name}:
            yield path, path.read_text(encoding="utf-8")


def test_the_clock_is_pinned_everywhere_or_not_at_all():
    """Patching `user_now` on one module leaves every other holder on the real day."""
    offenders = [path.name for path, text in _sources() if _ONE_MODULE.search(text)]
    assert not offenders, f"pin the clock with tests._clock.pin_clock(monkeypatch, NOW): {offenders}"


def test_no_new_test_reads_the_real_clock():
    offenders = [
        path.name for path, text in _sources()
        if path.name not in REAL_CLOCK_RELATIVE and path.name not in _DOCUMENTED and _REAL_READ.search(text)
    ]
    assert not offenders, f"pin the day with tests._clock.pin_clock (a fixed NOW), not the real clock: {offenders}"


def test_the_relative_list_only_names_files_that_still_read_the_clock():
    stale = sorted(name for name in REAL_CLOCK_RELATIVE if not _REAL_READ.search((TESTS / name).read_text(encoding="utf-8")))
    assert not stale, f"drop these from REAL_CLOCK_RELATIVE, they no longer read the real clock: {stale}"


#: Name the real clock in prose or in a lint pattern, never call it for data.
_DOCUMENTED = {"_frozen_clock.py", "test_fixed_day_1693.py", "test_drifted_copies_1031.py", "test_daily_journal.py"}


def test_pin_clock_reaches_a_module_that_imported_user_now_by_name(monkeypatch):
    from datetime import datetime

    from tessellate.api import routes_chat
    from tessellate.core import config
    from tests._clock import pin_clock

    when = datetime(2026, 8, 1, 9, 0)
    pin_clock(monkeypatch, when)
    assert config.user_now() == when and routes_chat.user_now(None) == when
