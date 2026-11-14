"""Source text: the hand-over's cost is a layout timing measured in a browser at 4x CPU (buddylag.js), which pytest cannot time, so this reads the branch that skips it. A blink, a glance or a turn is not handed over (L-ui-modernisation-62).

With Atlas on at 4x CPU, the act hand-over after a tab switch forced 24 to 46
ms of layout (buddylag.js). Per act (a probe of each act, 4x, Atlas): a hand-over
into or out of a blink, a glance or a turn eased nothing in every run (0
eases), yet read every part before and after the change, 10 to 370 ms. Those
acts change only the lids (a plain `scale: 0` rule, or the lids' own `scaleY`
loop) and `data-turn`, which is written outside the hand-over, so nothing a
hand-over eases moves.
"""

from __future__ import annotations

import re

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
AV = (ROOT / "frontend" / "js" / "avatars.js").read_text(encoding="utf-8")


def _act_body() -> str:
    start = AV.index("function nameMarkBuddyAct(act, ms) {")
    end = AV.index("\n  }\n", start)
    return AV[start:end]


def test_lids_only_acts_skip_the_hand_over():
    """Source text: nameMarkBuddyAct names the lids-only acts and swaps the hand-over for the plain change between them and rest."""
    body = _act_body()
    m = re.search(r'const lidsOnly = \[was, act\]\.every\(\(a\) => !a \|\| \["blink", "glance", "turn"\]\.includes\(a\)\);', body)
    assert m, "the lids-only test is missing from nameMarkBuddyAct"
    # The leave into rest and the enter from rest: the two hand-overs a lids-only change can reach (the
    # same act twice is never `joined`, and a land is not lids-only).
    assert "if (lidsOnly) leave();\n      else nameMarkBuddyBlend(buddy, leave);" in body
    assert "if (lidsOnly) change();\n      else nameMarkBuddyBlend(buddy, change, NMB_BLEND_IN_MS);" in body
    assert body.index("const lidsOnly") < body.index("if (lidsOnly) leave();")


def test_eased_acts_keep_their_hand_over():
    """Source text: a look and a shift move the head or the body (look: 2 and 4 eases, shift: 1), so they are not in the lids-only list."""
    body = _act_body()
    lids = re.search(r'\["blink", "glance", "turn"\]', body)
    assert lids and "look" not in lids.group(0) and "shift" not in lids.group(0)
    css = "\n".join(p.read_text(encoding="utf-8") for p in (ROOT / "frontend" / "css").glob("*.css"))
    # The lids-only acts' own rules touch only the lids (`.nm-blinks`, `.atl-layer-lids`), never a blended part.
    for act in ("blink", "glance", "turn"):
        for rule in re.findall(rf"\.nmb-act-{act}\b[^{{]*", css):
            assert re.search(r"nm-blinks|atl-layer-lids", rule), (act, rule)


def test_bar_clip_is_kept_while_the_window_is_the_same():
    """Source text: nameMarkBuddyAloft.rest reads the bars' boxes only when the perch, the window or the written clip changed, or the kept one is 15s old.

    Every act's state write (`nameMarkBuddyState`) called it after the act's class went on, and its
    `nameMarkBuddyLedges` read was the first layout read of the task: 660ms of `getBoundingClientRect`
    over 30 acts at 4x on Atlas (a CPU profile of that probe), against 5ms in the hand-over's own reads.
    """
    start = AV.index("nameMarkBuddyAloft.rest = (on = true) => {")
    body = AV[start:AV.index("\n  };\n", start)]
    key = body.index("const key = want ? `${kind}|${innerWidth}x${innerHeight}` : \"\";")
    keep = body.index("if (kept && kept.key === key && kept.clip === band.style.clipPath && performance.now() - kept.at < NMB_COVERS_MAX_MS) return;")
    read = body.index("nameMarkBuddyLedges()")
    assert key < keep < read
    assert "nameMarkBuddyAloft.kept = { key, clip: band.style.clipPath, at: performance.now() };" in body
