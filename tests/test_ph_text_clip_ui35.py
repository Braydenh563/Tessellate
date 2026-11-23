"""Source text: "Fix or exempt the clip685 findings at 390 dark."

L-ui-modernisation-35, the `.ph-text` finding: clip685.js at 390 dark found a
`.ph-text` label in Library's Skills with its last pixel cut off at the bottom
(a descender), because `overflow: hidden` clips both axes and the ellipsis
needs only the inline one. `overflow-x: clip` keeps the ellipsis and leaves
the block axis visible (measured: overflowY "visible", textOverflow "ellipsis")."""

import re
from pathlib import Path

CSS = (Path(__file__).resolve().parents[1] / "frontend" / "css" / "07-whiteboard-misc.css").read_text(encoding="utf-8")


def test_the_label_ellipsis_clips_across_only() -> None:
    rule = re.search(r"^\.ph-text \{([^}]*)\}", CSS, re.M)
    assert rule
    body = rule.group(1)
    assert "overflow-x: clip" in body and "text-overflow: ellipsis" in body
    assert not re.search(r"(?<![-\w])overflow:", body)
