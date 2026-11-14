"""Regenerate frontend/vendor/PROVENANCE.json from docs/THIRD_PARTY.md.

One entry per vendored file: path, sha256, size, plus the library's version,
upstream URL, licence and notice file from the credits table, so a file's
origin is machine-readable. `tests/test_vendor_provenance.py` recomputes the
hashes; run `python scripts/vendor_provenance.py` after changing a vendored
file (L-general-4).
"""

from __future__ import annotations

import hashlib
import json
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
VENDOR = ROOT / "frontend" / "vendor"
OUT = VENDOR / "PROVENANCE.json"


def library_rows() -> list[dict]:
    """The browser table's rows, as {prefix, library, version, licence, notice, source}."""
    text = (ROOT / "docs" / "THIRD_PARTY.md").read_text(encoding="utf-8")
    browser = text.split("## Browser (`frontend/vendor/`)", 1)[1].split("\n## ", 1)[0]
    rows = []
    for line in browser.splitlines():
        if not line.startswith("| ") or line.startswith("| ---") or line.startswith("| Library"):
            continue
        cells = [c.strip() for c in line.strip().strip("|").split("|")]
        prefix = re.match(r"`([^`]+)`", cells[1])[1]
        notice = re.search(r"`([^`]*(?:LICENSE|COPYING)[^`]*)`", cells[3])
        rows.append(
            {
                "prefix": prefix,
                "library": cells[0],
                "version": cells[2],
                "licence": re.sub(r"\s*\(`[^)]*`\)", "", cells[3]).strip(),
                "notice": notice[1] if notice else "",
                "source": cells[4],
            }
        )
    return rows


def owner(path: str, rows: list[dict]) -> dict | None:
    for row in rows:
        prefix = row["prefix"]
        if path == prefix or (prefix.endswith("/") and path.startswith(prefix)):
            return row
    for row in rows:  # a licence file named beside a single-file library
        if row["notice"] and path == row["notice"]:
            return row
    return None


def build() -> dict:
    rows = library_rows()
    files = []
    for file in sorted(p for p in VENDOR.rglob("*") if p.is_file() and p != OUT):
        rel = file.relative_to(VENDOR).as_posix()
        row = owner(rel, rows)
        files.append(
            {
                "path": rel,
                "sha256": hashlib.sha256(file.read_bytes()).hexdigest(),
                "size": file.stat().st_size,
                "library": row["library"] if row else None,
                "version": row["version"] if row else None,
                "upstream": row["source"] if row else None,
                "licence": row["licence"] if row else None,
                "notice": (row["notice"] if row else None) or None,
            }
        )
    return {"files": files}


if __name__ == "__main__":
    OUT.write_text(json.dumps(build(), indent=1) + "\n", encoding="utf-8")
    print(f"{len(build()['files'])} files")
