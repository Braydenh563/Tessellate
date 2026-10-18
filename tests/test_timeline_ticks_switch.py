"""INBOX 1300 C36: the dates beside the Timeline's density strip can be hidden.

A remembered switch in the Timeline's Options menu; the lazy ticks file owns
the wiring (the boot scripts are at their gzip budget)."""

from __future__ import annotations

from pathlib import Path

FRONTEND = Path(__file__).resolve().parents[1] / "frontend"


def test_the_options_menu_has_the_switch_and_the_ticks_file_wires_it() -> None:
    html = (FRONTEND / "index.html").read_text(encoding="utf-8")
    menu = html.split('id="timeline-options-menu"', 1)[1].split("</details>", 1)[0]
    assert 'id="timeline-ticks-toggle"' in menu and "dock-menu-check" in menu
    ticks = (FRONTEND / "js" / "timeline-ticks.js").read_text(encoding="utf-8")
    assert '"timeline-ticks"' in ticks and "timelineTicksWanted()" in ticks
    assert 'getElementById("timeline-ticks-toggle")' in ticks or '$("timeline-ticks-toggle")' in ticks
