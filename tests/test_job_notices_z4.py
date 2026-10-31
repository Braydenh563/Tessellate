"""audit-1031 Z4: the bell hears about a job only when it failed or a person started it.

Y7 silenced the upkeep kinds by name; the rest of the app's own jobs (model
info, resurfacing, a picture read after a save) still came in as news. The
class is the origin: a finished job started by the app, a schedule or
start-up stays in Background tasks. And a count says what it counted.
"""

from __future__ import annotations

from tessellate.core import jobruns
from tests._objmove_node import needs_node, run


@needs_node
def test_the_apps_own_finished_jobs_stay_out_of_the_bell():
    out = run(["chat-tasks.js"], """
    const own = (origin, outcome) => taskEndingIsAppsOwn({ origin, outcome });
    __out([own("", "completed"), own("app", "completed"), own("schedule", "completed"),
           own("start-up", "completed"), own("you", "completed"), own("", "failed"),
           own("app", "failed"), own("you", "failed")]);
    """)
    assert out == [True, True, True, True, False, False, False, False]


def test_renderTaskHistory_settles_a_started_row_before_skipping():
    from tests._objmove_node import JS

    text = (JS / "chat-tasks.js").read_text(encoding="utf-8")
    body = text[text.index("function renderTaskHistory("):]
    assert body.index("settleStartedNotification(") < body.index("taskEndingIsAppsOwn(")


class _Run:
    result = ""

    def skip(self):  # pragma: no cover - not reached
        raise AssertionError


def test_the_night_shift_count_says_notes_and_boards():
    run_ = _Run()
    jobruns.describe_night_pass(run_, {"scanned": 228, "boards": 21, "derived": 55})
    assert run_.result == "read 207 notes and 21 boards, found 55 facts"
    jobruns.describe_night_pass(run_, {"scanned": 1, "derived": 1})
    assert run_.result == "read 1 note, found 1 fact"
    jobruns.describe_night_pass(run_, {"scanned": 3, "boards": 3, "derived": 0})
    assert run_.result == "read 3 boards, found 0 facts"
