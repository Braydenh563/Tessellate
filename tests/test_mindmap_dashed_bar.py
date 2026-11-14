"""A mind map topic's Dashed edge bar has gaps on every ground (INBOX 581).

The owner, verbatim: "on the mindmap, the solid and dashed bar are exactly the
same on mind map nodes". After 569 (the pin's dash), one case was left: a
border's gaps show the element's own background, which runs under the border
by default, and a core topic's background is `--wb-branch`, the bar's own
colour, so its Dashed bar drew solid (scratchpad/ui-sweeps/gl1005-mmbar.js:
0% gap lines on a core ellipse, pill or box; 2 of 16 core cases told apart).
A dashed bar clips the ground to the padding box, and the rule has to outrank
the core and filled rules' `background` shorthand, which resets the clip.
"""

import re
from pathlib import Path

CSS = "".join(  # L-ui-modernisation-31: Library-only rules live in library-lazy.css
    (Path(__file__).resolve().parent.parent / "frontend" / "css" / n).read_text(encoding="utf-8")
    for n in ("07-whiteboard-misc.css", "library-lazy.css")
)


def _specificity(selector: str) -> tuple[int, int]:
    attrs_classes = len(re.findall(r"\.[\w-]+|\[[^\]]+\]", selector))
    return (selector.count("#"), attrs_classes)


def test_a_dashed_bar_clips_the_ground_so_its_gaps_show():
    rule = re.search(r"\n([^{}\n]*data-spine=\"dashed\"[^{}\n]*)\{[^}]*background-clip: padding-box;", CSS)
    assert rule, "the dashed bar's background-clip rule is missing"
    clip = _specificity(rule.group(1))
    for grounded in (".wb-map-node.wb-map-core", ".wb-map-node.wb-map-filled"):
        assert re.search(re.escape(grounded) + r" \{[^}]*\bbackground:", CSS), grounded
        assert clip > _specificity(grounded), f"{rule.group(1).strip()} does not outrank {grounded}"
