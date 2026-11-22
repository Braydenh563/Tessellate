"""Atlas's aura sits on the masculine figure (L-world-class-413, atlasaura.js).

At the default `auraAt` [31, 46] the aura's centre sat 9px left of the standing
masculine figure's middle in the large view (4.5 to 5.1% of its width, past the
sweep's 4%) and 6.5px left of the hanging one. At [33.5, 46], as the feminine
look's, the standing case read 0.6 to 2.5% over three runs.
"""

import re
from pathlib import Path

SRC = (Path(__file__).resolve().parents[1] / "frontend" / "js" / "atlas.js").read_text(encoding="utf-8")


def _look(name: str) -> str:
    start = SRC.index("const ATLAS_LOOKS = {")
    m = re.search(rf"\n  {name}: \{{(.*?)\n  \}},?\n", SRC[start:], re.S)
    assert m, f"the {name} look moved"
    return m.group(1)


def test_both_looks_centre_the_aura_at_the_same_point():
    for look in ("masculine", "feminine"):
        assert re.search(r"\n    auraAt: \[33\.5, 46\],", _look(look)), look
