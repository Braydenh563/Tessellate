"""gaudit 2026-11-12: Play on the time slider did nothing when every note had
the same timestamp (min equals max, nothing to sweep). The button is now off
with a title saying why. The Map of meaning layout also gets its stats line
(it was blank)."""

from __future__ import annotations

from pathlib import Path

from tests._js_scope import unwrapped

CANVAS = unwrapped((Path(__file__).resolve().parent.parent / "frontend" / "js" / "graph-canvas.js").read_text(encoding="utf-8"))


def test_play_is_off_and_says_why_when_every_note_shares_a_date() -> None:
    sync = CANVAS[CANVAS.index("function graphSyncTimeSlider") :]
    sync = sync[: sync.index("\n  }\n")]
    assert "play.disabled = !(max > min);" in sync
    assert '"Every note has the same date, so there is nothing to play through"' in sync


def test_the_map_of_meaning_has_a_stats_line() -> None:
    stats = CANVAS[CANVAS.index("function graphRenderStats") :]
    assert 'layoutKind === "map"' in stats[: stats.index("\n  }\n")]
