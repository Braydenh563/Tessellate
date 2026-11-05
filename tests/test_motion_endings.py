"""Nothing waits on an animation or a transition that may never run.

**Why this exists (the review of 2026-09-27).** The owner has reduced motion
on, and under it the stylesheet stops transitions outright (`transition-
duration: 0s`, `tests/test_motion_tokens.py`) and several rules write
`animation: none`. Neither starts anything, so neither ends: an
`animationend` or `transitionend` listener on such an element never fires.
Measured on `flashSaved` (settings-wiring.js), the ring a keyboard save
draws on the control it pressed: `.just-saved` carries `animation: none`
under the system hint, so the class and the inline `--just-saved-rest` it
wrote stayed on the button for good, and every Ctrl+S added one more
listener that would never run.

The rule: a listener for the end of an animation or a transition sits next
to something that finishes the job without it, within the same function: a
timer, a check that anything is running (`getAnimations`), or the
reduced-motion test (`reducedMotionWanted`, `prefers-reduced-motion`). The
listeners that only re-check something (`avatars.js`'s companion, which is
also driven by the class change that starts the move) are named below.
"""

from __future__ import annotations

import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
FRONTEND = ROOT / "frontend"

#: Listeners that finish nothing: they ask the companion to look again, and
#: the change that set the motion going already asked it.
OBSERVERS = {
    ("avatars.js", 'for (const type of ["pointerdown", "pointerup", "keydown", "transitionrun"'),
    ("avatars.js", 'document.addEventListener("transitionend", (event) => {'),
}

FALLBACK = re.compile(r"setTimeout\(|getAnimations\(|reducedMotionWanted\(|prefers-reduced-motion")


def _enclosing_function(text: str, at: int) -> str:
    #: A file wrapped in an IIFE indents its functions; the nearest function
    #: start at any indent, closed by a brace at that same indent (with only
    #: column-0 starts, a wrapped file read as an empty region and failed).
    starts = list(re.finditer(r"\n([ \t]*)(?:async )?function ", text[:at]))
    if not starts:
        return text[: text.find("\n}\n", at) if text.find("\n}\n", at) != -1 else len(text)]
    start, indent = starts[-1].start(), starts[-1].group(1)
    end = text.find("\n" + indent + "}\n", at)
    return text[start : end if end != -1 else len(text)]


def test_every_end_listener_has_a_way_to_finish_without_it():
    offenders = []
    for path in sorted((FRONTEND / "js").glob("*.js")):
        text = path.read_text(encoding="utf-8")
        for m in re.finditer(r'addEventListener\(\s*"(animationend|transitionend)"|for \(const type of \[[^\]]*"(?:animationend|transitionend)"', text):
            line_start = text.rfind("\n", 0, m.start()) + 1
            line = text[line_start : text.find("\n", m.start())].strip()
            if any(name == path.name and line.startswith(prefix) for name, prefix in OBSERVERS):
                continue
            if not FALLBACK.search(_enclosing_function(text, m.start())):
                number = text.count("\n", 0, m.start()) + 1
                offenders.append(f"{path.name}:{number}: {line}")
    assert not offenders, (
        "An end listener with nothing to finish its job when no animation or "
        "transition runs (reduced motion runs none):\n" + "\n".join(offenders)
    )


def test_the_save_ring_finishes_when_no_ring_runs():
    text = (FRONTEND / "js" / "settings-wiring.js").read_text(encoding="utf-8")
    body = _enclosing_function(text, text.index("function flashSaved(el)") + 1)
    assert "getAnimations()" in body and "if (!ring)" in body, "flashSaved waits on a ring that reduced motion never starts"
    assert "ring.finished.then(finish, finish)" in body, "a cancelled ring must finish too"
