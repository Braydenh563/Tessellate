"""INBOX 1659 (the owner: "the lower body never changes or animates, same with
the surrounding nebular stream"). Measured at rest on the companion
(scratchpad probe travel.js, 6.8s): the stream's box moved 5px, the lower
body 1.7px and the nebula 1px; the loops were there but too small to see.
These pin the rest loops at a size a person can see, still on the
compositor (rotate, translate, skew on layer roots and boxes only)."""

import re
from pathlib import Path

from tests._app_js import app_js_text

CSS = Path("frontend/css/characters-lazy.css").read_text(encoding="utf-8")
JS = app_js_text()


def _frames(name):
    body = CSS[CSS.index(f"@keyframes {name} {{") :]
    return body[: body.index("\n}") if "\n}" in body[:400] else body.index("}") + 1]


def _nums(text, unit):
    return [float(v) for v in re.findall(rf"(-?[0-9.]+){unit}", text)]


def test_the_nebula_stream_flows_visibly():
    flow = _frames("atl-neb-flow")
    assert max(_nums(flow, "px")) - min(_nums(flow, "px")) >= 3.5
    assert max(_nums(flow, "deg")) - min(_nums(flow, "deg")) >= 4
    drift = _frames("atl-neb-drift")
    assert max(_nums(drift, "deg")) - min(_nums(drift, "deg")) >= 7


def test_the_lower_body_and_tail_sway_visibly():
    skirt = _frames("atl-skirt-idle")
    assert max(_nums(skirt, "deg")) - min(_nums(skirt, "deg")) >= 7
    tail = _frames("atl-tail-flow")
    assert max(_nums(tail, "deg")) - min(_nums(tail, "deg")) >= 6


def test_the_resting_tail_sways_wide_and_changes_shape_every_few_seconds():
    rest = JS[JS.index("function atlasTailRest(tail, p) {") :][:900]
    lo, hi = re.search(r"Math\.min\((\d+), Math\.max\(([0-9.]+),", rest).group(1, 2)
    assert float(hi) >= 4 and float(lo) >= 10
    hold = re.search(r"calm \? (\d+) \+ Math\.random\(\) \* (\d+)", JS)
    assert hold and int(hold.group(1)) + int(hold.group(2)) <= 10000
