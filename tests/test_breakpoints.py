"""The width breakpoints are a design, stated once (audit 2026-10-05, FE-11).

UI_MODERNISATION_PLAN Phase 9 named four layouts (under 600, 600 to 820, 820
to 1100, 1100 and over), written `max-width: 599.98px` / `min-width: 600px`
and so on, so a window exactly 600 wide is on one side. The audit counted 58
distinct width queries, and two conventions colliding: `max-width: 600px`
(24 rules) with `min-width: 600px` (15), and `max-width: 720px` with
`min-width: 720px`, both sides matching at exactly that width.

Two rules, read from every stylesheet:

- **No width is on both sides.** A `max-width: W` and a `min-width: W`
  (rem and em at 16px) both match a window W wide.
- **The set only shrinks.** A width outside Phase 9's is either a named
  component's own (listed below, with how many rules use it) or it fails;
  the counts may only go down. The 720, 640 and 900 groups were moved onto
  the Phase 9 set on 2026-10-05 with `scratchpad/ui-sweeps/bands.js` (a
  before and after at 390 to 1440); the rules left in them are listed.
  The 900 group's header rules moved first, with
  `scratchpad/ui-sweeps/perf2-1005-bp900.js`.
"""

from __future__ import annotations

import re
from collections import Counter
from pathlib import Path

CSS = Path(__file__).resolve().parents[1] / "frontend" / "css"
QUERY = re.compile(r"\((max|min)-width:\s*([0-9.]+)(px|rem|em)\)")

PHASE_9 = {
    ("max", 599.98),
    ("min", 600.0),
    ("max", 819.98),
    ("min", 820.0),
    ("max", 1099.98),
    ("min", 1100.0),
}

#: Every other width in use on 2026-10-05, and how many queries use it.
#: Lower a number (or drop a row) when a group moves onto Phase 9's set.
ALLOWED = {
    # The three groups the audit named (720, 640 and 900) are empty: uimod-89
    # moved 35 of their 49 rules onto Phase 9's set, op4-1005 the status
    # bar's and the dashboard quick access's, and op5-1005 the last ten (the
    # whiteboard file's, to 819.98/820, which also took the tool dock off the
    # zoom cluster between 641 and 819: 6,841px² to 0, `op5-1005.js`
    # MODE=bands).
    # Components' own widths (rem at 16px: dialogs, panels, the timeline).
    ("max", 400.0): 4,
    ("min", 1024.0): 4,
    ("max", 1199.98): 3,
    ("max", 896.0): 3,
    ("max", 768.0): 3,
    ("max", 1080.0): 2,
    ("max", 1023.98): 2,
    ("max", 703.84): 2,
    ("max", 960.0): 2,
    ("max", 1216.0): 2,
    ("max", 544.0): 2,
    ("max", 1200.0): 1,
    ("max", 940.0): 1,
    ("max", 1439.98): 1,
    ("max", 1023.0): 1,
    ("max", 288.0): 1,
    ("max", 860.0): 1,
    ("max", 700.0): 1,
    ("max", 379.98): 1,
    ("max", 959.98): 1,
    ("max", 1279.98): 1,
    ("max", 1500.0): 1,
    ("max", 449.98): 1,
    ("max", 480.0): 1,
    ("max", 340.0): 1,
    ("min", 768.16): 1,
    ("max", 1499.0): 1,
    ("max", 359.98): 1,
    ("min", 360.0): 1,
    ("max", 479.98): 1,
    ("max", 208.0): 1,
    ("max", 272.0): 1,
    ("max", 416.0): 1,
    ("max", 1399.98): 1,
    ("max", 1152.0): 1,
    ("max", 560.0): 1,
    ("max", 927.84): 1,
    # The Documents sidebar's Recent head (16rem of sidebar): sheds the New word and folds its icons.
    ("max", 256.0): 1,
}


def _queries() -> Counter:
    found: Counter = Counter()
    for path in CSS.glob("*.css"):
        for line in path.read_text(encoding="utf-8").split("\n"):
            stripped = line.lstrip()
            if not stripped.startswith(("@media", "@container")):
                continue
            for side, number, unit in QUERY.findall(line):
                px = float(number) * (16 if unit in ("rem", "em") else 1)
                found[(side, round(px, 2))] += 1
    return found


def test_no_width_matches_both_sides():
    found = _queries()
    both = sorted(w for side, w in found if side == "max" and ("min", w) in found)
    assert not both, f"a window this wide gets both sides' rules: {both}"


def test_the_breakpoints_only_shrink():
    found = _queries()
    extra = {}
    for key, count in found.items():
        if key in PHASE_9:
            continue
        allowed = ALLOWED.get(key, 0)
        if count > allowed:
            extra[f"{key[0]}-width {key[1]:g}px"] = f"{count} (allowed {allowed})"
    assert not extra, (
        "a width query outside UI_MODERNISATION_PLAN Phase 9's set "
        f"(599.98/600, 819.98/820, 1099.98/1100): {extra}"
    )


def test_the_ask_results_grid_is_one_column_below_1100():
    """DESIGN.md, "Two columns of reading" (op4-1005): two columns gave each
    half 262px at 820 and 397 at 1099; from 1100 a half is 363 to 529px."""
    text = (CSS / "01-forms-settings.css").read_text(encoding="utf-8")
    rule = re.search(r"@media \(max-width: ([0-9.]+)px\) \{\s*\.chat-grid \{\s*grid-template-columns: 1fr;", text)
    assert rule and rule.group(1) == "1099.98", "the Ask results grid's one-column width moved off 1099.98"
