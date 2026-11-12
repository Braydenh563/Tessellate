"""The companion's control boxes are read while it is carried (lag-1109 row 13).

The release read was the first read after the drag: 49 to 119 ms at 4x, one
forced layout in `nameMarkBuddyControlsIn`, on the path to the landing. The
boxes are now read once the frame that drew the pick-up is done, and a throw
keeps what was read since the pick-up instead of dropping it (the observers
still drop it on any scroll, resize or change). Measured in
docs/roadmap/agent-remaining/w34-def1-1111.md.
"""

from __future__ import annotations

import re
import shutil
import subprocess
from pathlib import Path

import pytest
from tests._js_scope import unwrapped

ROOT = Path(__file__).resolve().parent.parent
AV = unwrapped((ROOT / "frontend" / "js" / "avatars.js").read_text(encoding="utf-8"))


def test_the_pick_up_warms_the_boxes_after_the_class_is_drawn() -> None:
    assert re.search(
        r'buddy\.classList\.add\("nm-buddy-dragging"\);\s*\n\s*drag\.pickedAt = performance\.now\(\);\s*\n\s*nmb\.warmCovers\(\);',
        AV,
    )


def test_a_throw_keeps_the_boxes_read_since_the_pick_up_and_drops_older_ones() -> None:
    body = AV[AV.index("      if (thrown) {\n        //: The tab's control boxes read since"):]
    body = body[: body.index("      const world")]
    assert "nmb.covers?.at >= drag.pickedAt" in body
    assert "nameMarkBuddyIndexReset();" in body
    assert body.index("nameMarkBuddyIndexReset();") < body.index("nmb.covers = kept;")


@pytest.mark.skipif(shutil.which("node") is None, reason="node is not installed")
def test_the_warm_read_runs_only_while_it_is_still_carried() -> None:
    fn = re.search(r"^nmb\.warmCovers = \(\) => \{.*?^\};", AV, re.S | re.M)
    assert fn, "nmb.warmCovers is gone from avatars.js"
    script = f"""
let carried = true;
const calls = [];
const document = {{ getElementById: () => ({{ classList: {{ contains: (c) => c === "nm-buddy-dragging" && carried }} }}) }};
globalThis.setTimeout = (fn) => fn();
const afterFrames = (fn, n) => {{ calls.push("frames " + n); fn(); }};
const nameMarkBuddyTab = () => "notes";
const nameMarkBuddyControlBoxes = (tab) => calls.push("boxes " + tab);
const nmb = {{}};
{fn.group(0)}
nmb.warmCovers();
carried = false;
nmb.warmCovers();
process.stdout.write(JSON.stringify(calls));
"""
    out = subprocess.run(["node", "-e", script], capture_output=True, text=True, check=True).stdout
    assert out == '["frames 1","boxes notes","frames 1"]', out
