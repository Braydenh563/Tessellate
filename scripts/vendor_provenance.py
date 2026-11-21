#!/usr/bin/env python3
"""Write frontend/vendor/PROVENANCE.json: every vendored browser file with its
sha256, size, library, version, upstream URL, licence and notice file
(L-general-4).

The library columns come from docs/THIRD_PARTY.md's browser table, so the
credits stay the one place a version is written; this adds what a reader
cannot check by eye, that the bytes in the repository are the bytes credited.
tests/test_vendor_provenance.py recomputes every hash, so a vendored file
changed without rerunning this fails there.

    python scripts/vendor_provenance.py          # rewrite the manifest
    python scripts/vendor_provenance.py --check  # exit 1 if it is stale
"""

from __future__ import annotations

import hashlib
import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
VENDOR = ROOT / "frontend" / "vendor"
MANIFEST = VENDOR / "PROVENANCE.json"
CREDITS = ROOT / "docs" / "THIRD_PARTY.md"


def _libraries() -> dict[str, dict]:
    """The browser table's rows, keyed by the vendor path in their Files cell."""
    text = CREDITS.read_text(encoding="utf-8")
    table = text[text.index("## Browser (`frontend/vendor/`)"):]
    table = table[: table.index("\n## ", 1)]
    rows: dict[str, dict] = {}
    for line in table.splitlines():
        if not line.startswith("| ") or line.startswith("| ---") or line.startswith("| Library"):
            continue
        name, files, version, licence, source = [cell.strip() for cell in line.strip("|").split("|")][:5]
        key = re.search(r"`([^`]+)`", files).group(1)
        notice = re.search(r"\(`([^`]+)`", licence)
        rows[key] = {
            "library": name,
            "version": version.replace("`", ""),
            "upstream": source,
            "licence": re.sub(r"\s*\(`[^`]+`[^)]*\)", "", licence).strip() or licence,
            "notice": f"frontend/vendor/{notice.group(1)}" if notice else None,
        }
    return rows


def _library_for(rel: str, rows: dict[str, dict]) -> dict:
    top = rel.split("/", 1)[0]
    key = f"{top}/" if "/" in rel else rel
    if key in rows:
        return rows[key]
    stem = rel.split(".LICENSE.txt")[0]
    for name, row in rows.items():
        if not name.endswith("/") and name.startswith(stem.split(".")[0]):
            return row
    raise SystemExit(f"frontend/vendor/{rel} has no row in docs/THIRD_PARTY.md's browser table")


def build() -> list[dict]:
    rows = _libraries()
    entries = []
    for path in sorted(VENDOR.rglob("*")):
        if not path.is_file() or path == MANIFEST or "__pycache__" in path.parts:
            continue
        rel = path.relative_to(VENDOR).as_posix()
        data = path.read_bytes()
        entries.append({
            "path": f"frontend/vendor/{rel}",
            "sha256": hashlib.sha256(data).hexdigest(),
            "size": len(data),
            **_library_for(rel, rows),
        })
    return entries


def render() -> str:
    return json.dumps(build(), indent=1, ensure_ascii=False) + "\n"


def main(argv: list[str]) -> int:
    text = render()
    if "--check" in argv:
        current = MANIFEST.read_text(encoding="utf-8") if MANIFEST.exists() else ""
        if current != text:
            print("frontend/vendor/PROVENANCE.json is stale: run python scripts/vendor_provenance.py")
            return 1
        return 0
    MANIFEST.write_text(text, encoding="utf-8")
    print(f"wrote {MANIFEST.relative_to(ROOT)}")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
