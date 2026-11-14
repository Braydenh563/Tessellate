"""L137: in the large view the visiting companion is drawn at 2.2x, so a body
move written in px (nmb-hop's 14px lift) travels 2.2x as far in the same time,
the head moving 2.2x faster than at rest. The viewer scope lengthens each
hop-family duration by the scale, so the speed matches the resting figure."""
import re
from pathlib import Path

CSS = (Path(__file__).resolve().parents[1] / "frontend/css/08-consistency.css").read_text()
SCALE = 2.2
BASE = {"hop": 0.75, "cheer": 0.65, "wave2": 0.75, "carry": 0.75}


def _scope_rule(selector_fragment):
    m = re.search(r"\.nm-viewer-figure > #nm-buddy:is\([^)]*" + re.escape(selector_fragment) + r"[^)]*\) \.nm-buddy-char \{([^}]*)\}", CSS)
    assert m, selector_fragment
    return m.group(1)


def _seconds(decl):
    return float(re.search(r"animation-duration:\s*([\d.]+)s", decl).group(1))


def test_hop_family_is_slowed_by_the_scale_in_the_large_view():
    assert _seconds(_scope_rule(".nmb-act-hop")) >= BASE["hop"] * SCALE - 0.01
    assert _seconds(_scope_rule(".nmb-act-cheer")) >= BASE["cheer"] * SCALE - 0.01
    assert _seconds(_scope_rule(".nmb-act-carry")) >= BASE["carry"] * SCALE - 0.01
