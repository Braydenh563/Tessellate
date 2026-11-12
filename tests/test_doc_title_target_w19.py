"""The document title field meets the phone's target floor (W19, sweep-1028b: 85x32 at 390
beside a 44px Edit / Read well). Measured 44 after, at 390, 700 and 819, with no sideways scroll."""

import re

from tests._css_paths import FORMER_10, sheets

CSS = sheets(*FORMER_10)


def test_the_title_takes_the_target_floor_below_820():
    at = CSS.index("@media (max-width: 819.98px) {\n  #tab-documents #doc-view-seg {")
    block = CSS[at : CSS.index("\n}\n", at)]
    assert re.search(r"#tab-documents \.doc-dock-identity\s*\{\s*--identity-h:\s*var\(--target-min\);", block)
