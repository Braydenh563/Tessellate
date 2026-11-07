"""The in-app companion dive (companion dive 1107): a bar or hang companion keeps clear of the
new tab's controls, its peek handle is the head it draws, it says how to use it, and
the palette can focus it. Source-level checks (the app runs against a fake transport
here); the measured numbers are in docs/roadmap/agent-remaining/inappdive-1107.md."""

from __future__ import annotations

import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
CSS = (ROOT / "frontend" / "css" / "08-consistency.css").read_text(encoding="utf-8")


def _rule(selector: str) -> str:
    start = CSS.index(selector + " {")
    return CSS[start : CSS.index("}", start)]


def test_the_peek_handle_is_the_head_it_draws() -> None:
    # 390x844, Notes: the handle hit-tested from y 710 to 784 while the head is drawn from y 752
    # (the char is translated by --nmb-edge - 34), so 38px of empty air over New note took its taps.
    clip = re.search(r"clip-path: inset\((.*)\);", _rule('#nm-buddy[data-legs="peek"] .nm-buddy-face'))
    assert clip, "the tucked-behind-the-bar clip"
    top = clip.group(1).split(" -80px")[0]
    #: Leaves the emerge's 10px rise (edge - 44) uncut, and no more than that.
    assert top == "calc(var(--nmb-edge) - 44px)", top



def test_a_bar_or_hang_that_changes_tab_looks_again_for_a_clear_perch() -> None:
    av = (ROOT / "frontend" / "js" / "avatars.js").read_text(encoding="utf-8")
    changed = av[av.index("function nameMarkBuddyTabChanged") :]
    changed = changed[: changed.index("\n}\n")]
    bar = changed[changed.index('(nmb.perch === "bar" || nmb.perch === "hang")') :]
    assert "setTimeout(queueNameMarkBuddyCheck, 900)" in bar[: bar.index("return;")]
