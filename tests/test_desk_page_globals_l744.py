"""Every global the companion's drawing files call at run time is defined on the desk companion's page (ledger L744).

Found measuring that page for its CPU budget: `desktop-companion.html` loads avatars.js and atlas.js but not dashboard.js, where
`afterFrames` is declared, so every Atlas mood change on the desk threw "afterFrames is not defined" (atlas.js `atlasPlay`,
avatars.js `afterClean`) and the blend after it never ran.
"""

from __future__ import annotations

import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
FRONT = ROOT / "frontend"


def _scripts(page: str) -> list[str]:
    html = (FRONT / page).read_text(encoding="utf-8")
    return [FRONT / m.split("?")[0].lstrip("/") for m in re.findall(r'<script src="([^"]+)"', html)]


def test_the_desk_page_defines_the_frame_helper_its_drawing_files_call() -> None:
    files = _scripts("desktop-companion.html")
    text = {f.name: f.read_text(encoding="utf-8") for f in files}
    callers = [n for n, t in text.items() if re.search(r"\bafterFrames\(", t)]
    assert {"avatars.js", "atlas.js"} <= set(callers), "the drawing files do call it"
    defined = [n for n, t in text.items() if re.search(r"(?:function afterFrames\b|window\.afterFrames\s*=)", t)]
    assert defined, "no script on the desk page defines afterFrames"
