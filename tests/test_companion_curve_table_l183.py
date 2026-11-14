"""Brief 34's rules for the companion's motion, as built (L183, 2026-11-14).

- One curve table: every Web Animation the companion files start eases through `NMB_CURVE`
  (avatars.js), never a literal. Measured: 18 distinct easing literals across eight files became
  13 names in one table, 104 call sites, 0 literals left.
- The idle rule: a weighted pick that never takes one of the last five acts while another suits.
- The debounce: a habit waits out typing (1.5 s since the last key), at most four times, and every
  reaction keeps a 6 s gap and a budget of four a minute.
"""

from __future__ import annotations

import re
from pathlib import Path

JS = Path(__file__).resolve().parents[1] / "frontend" / "js"
FILES = ("avatars", "atlas-life", "atlas-micro", "atlas-motion", "companion-menu", "companion-settings", "companion-throw", "companion-travel")
AVATARS = (JS / "avatars.js").read_text(encoding="utf-8")


def _table() -> dict[str, str]:
    body = re.search(r"const NMB_CURVE = \{(.*?)\n  \};", AVATARS, re.S).group(1)
    return dict(re.findall(r"^\s*(\w+): (.+?),$", body, re.M))


def test_every_companion_ease_names_the_one_table() -> None:
    used = set()
    for name in FILES:
        src = (JS / f"{name}.js").read_text(encoding="utf-8")
        assert not re.findall(r"easing: *[\"'`]", src), f"{name}.js eases through a literal, not NMB_CURVE"
        used |= set(re.findall(r"NMB_CURVE\.(\w+)", src))
    table = _table()
    assert used <= set(table), f"names missing from the table: {used - set(table)}"
    curves = {v for k, v in table.items() if k != "blend"}
    assert len(curves) == len(table) - 1 <= 13, "one curve per name, and no more than the 13 built"
    assert table["settle"] == '"cubic-bezier(0.4, 0, 0.2, 1)"', "settle is the --ease-in-out token"
    assert 120 <= int(table["blend"]) <= 400, "a joint eases into an act over 120 to 400 ms (Brief 34)"


def test_the_table_is_set_before_anything_in_the_file_runs() -> None:
    assert AVATARS.index("const NMB_CURVE = {") < AVATARS.index("const NAME_MOOD_LEXICON")


def test_the_idle_rule_and_the_debounce_hold() -> None:
    assert "const NMB_RECENT_ACTS = 5;" in AVATARS
    assert "const fresh = pool.filter(([act]) => !recent.includes(act));" in AVATARS
    assert "if (typed < 1500) {" in AVATARS and "if (wait[kind] <= 4) setTimeout(() => nameMarkBuddyReact(kind, target), 1600 - typed);" in AVATARS
    assert "const NMB_REACT_GAP = 6000;" in AVATARS and "const NMB_REACT_BUDGET = 4;" in AVATARS
