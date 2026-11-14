"""Write frontend/credits.json from docs/THIRD_PARTY.md.

Settings, Help, Credits lists every library the app is built on (the owner:
"we should reference all the vendored repos and libraries somewhere to give
them credit"). THIRD_PARTY.md is the one record, kept whole by
tests/test_vendor_manifest.py; this turns its tables into the list the page
reads, and tests/test_credits.py fails when the two disagree.

    python scripts/build_credits.py
"""

from __future__ import annotations

import json
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / "docs/THIRD_PARTY.md"
TARGET = ROOT / "frontend/credits.json"


def _plain(cell: str) -> str:
    return re.sub(r"\s+", " ", cell.replace("`", "")).strip()


#: The page's words for THIRD_PARTY.md's section heads (the headings name
#: folders, which mean nothing to the person reading the credits).
TITLES = {
    "Python": "In the server",
    "Python packages": "In the server, installed with pip",
    "Browser": "In the app",
    "Optional downloads": "Optional downloads",
    "Board library": "The whiteboard's shapes",
}
#: The Data section is prose, not a table; its one outside source by hand.
DATA = {"title": "Data", "rows": [{"name": "Wikipedia's lists of common misspellings", "licence": "CC BY-SA 4.0", "source": "https://en.wikipedia.org/wiki/Wikipedia:Lists_of_common_misspellings"}]}


def credits() -> list[dict]:
    groups: list[dict] = []
    for block in re.split(r"^## ", SOURCE.read_text(encoding="utf-8"), flags=re.M)[1:]:
        title = TITLES.get(_plain(block.splitlines()[0].split("(")[0]), "")
        rows = []
        for line in block.splitlines():
            cells = [c.strip() for c in line.strip().strip("|").split("|")]
            if len(cells) < 6 or cells[0] in ("Library", "---") or set(cells[0]) <= {"-", " "}:
                continue
            licence = _plain(cells[3].split("(")[0])
            rows.append({"name": _plain(cells[0]), "licence": licence, "source": cells[4].strip()})
        if rows and title:
            groups.append({"title": title, "rows": rows})
    return [*groups, DATA]


def render() -> str:
    return json.dumps({"groups": credits()}, indent=1, ensure_ascii=False) + "\n"


if __name__ == "__main__":
    TARGET.write_text(render(), encoding="utf-8")
    print(f"wrote {TARGET.relative_to(ROOT)}: {sum(len(g['rows']) for g in credits())} libraries")
