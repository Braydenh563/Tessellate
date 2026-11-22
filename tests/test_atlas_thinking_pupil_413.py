"""Atlas's thinking pupils rest inside their eyes (L-world-class-413, companioneyes.js).

The thinking mood parked the pupil 1.8px left and 2.2px up in the drawing, which put the
right pupil over the top of its white at rest (up to half its edge points outside, 65 cases
in the sweep). The placement is now 0.8px by 0.9px, which the sweep measures as 0 outside.
"""

import re
from pathlib import Path

# The Atlas rules moved to the lazy characters sheet with the boot diet; the placement is the same.
CSS = (Path(__file__).resolve().parents[1] / "frontend" / "css" / "characters-lazy.css").read_text(encoding="utf-8")


def test_thinking_pupil_placement_is_within_the_eye():
    m = re.search(r'\.nm-atlas\[data-atlas-mood="thinking"\] \{(.*?)\n\}', CSS, re.S)
    assert m, "thinking mood rule moved"
    px = float(re.search(r"--atl-px: (-?[\d.]+)px", m.group(1)).group(1))
    py = float(re.search(r"--atl-py: (-?[\d.]+)px", m.group(1)).group(1))
    assert abs(px) <= 1.0 and abs(py) <= 1.0
