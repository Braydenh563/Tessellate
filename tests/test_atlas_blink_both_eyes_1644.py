"""INBOX 1644: every eye blinks, not the first one found.

The owner: "it is only atlas's right eye or the one on the left that blinks
not the other one". Atlas draws one `.nm-blinks` group per eye; the idle
blink act (avatars.js, `nameMarkIdleAct`) took `querySelector`'s first, so
only one eye shut (measured 19.27px to 2.03px on one eye, 19.27 to 19.27 on
the other). The act animates every `.nm-blinks` of the figure now.
"""

import re
from pathlib import Path

JS_DIR = Path(__file__).resolve().parents[1] / "frontend" / "js"
AVATARS = (JS_DIR / "avatars.js").read_text(encoding="utf-8")
ATLAS = (JS_DIR / "atlas.js").read_text(encoding="utf-8")
JS = "\n".join(p.read_text(encoding="utf-8") for p in sorted(JS_DIR.glob("*.js")))


def test_no_script_animates_only_the_first_blink_group():
    assert not re.search(r"querySelector\(\s*[\"']\.nm-blinks[\"']", JS)
    assert not re.search(r"part\(\s*[\"']\.nm-blinks[\"']", JS)


def test_idle_blink_act_walks_every_blink_group():
    act = AVATARS[AVATARS.index('act === "blink"'):]
    act = act[: act.index('act === "look"')]
    assert 'querySelectorAll(".nm-blinks")' in act
    assert ".animate(" in act


def test_atlas_draws_one_blink_group_per_eye():
    assert 'atlasGroup(open, "nm-blinks atl-blink"' in ATLAS
