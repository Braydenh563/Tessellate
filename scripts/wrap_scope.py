"""Wrap a classic frontend script whole in one closure (ranked row 37a).

    python scripts/wrap_scope.py frontend/js/FILE.js exportedName [more ...]

The header comment stays outside; the body moves two spaces in, inside
`(() => {` ... `})();`, and the foot lists the names other files call:
`Object.assign(window, { name });`. Refuses a file with a template literal
that spans lines, whose text would change if it were re-indented. Then run
`node --check`, `tests/test_global_scope_ratchet.py` (lower
`GLOBAL_NAMES_CAP` by what it printed) and the file's own tests.
"""

from __future__ import annotations

import sys
from pathlib import Path


def wrap(text: str, exports: list[str]) -> str:
    lines = text.split("\n")
    spanning = [n for n, line in enumerate(lines, 1) if line.count("`") % 2]
    if spanning:
        raise SystemExit(f"a template literal spans lines at {spanning[:5]}; wrap by hand")
    start = 0
    while start < len(lines) and (lines[start].startswith("//") or not lines[start].strip()):
        start += 1
    body = lines[start:]
    while body and not body[-1].strip():
        body.pop()
    foot = [
        "",
        "  //: The file's whole surface: what other files and the stand-ins call (ranked row 37a).",
        "  Object.assign(window, { " + ", ".join(exports) + " });",
        "})();",
        "",
    ]
    return "\n".join(lines[:start] + ["(() => {"] + [("  " + line) if line.strip() else "" for line in body] + foot)


def main(argv: list[str]) -> None:
    if len(argv) < 2:
        raise SystemExit(__doc__)
    path = Path(argv[0])
    path.write_text(wrap(path.read_text(encoding="utf-8"), argv[1:]), encoding="utf-8")
    print(f"wrapped {path.name}, exporting {', '.join(argv[1:])}")


if __name__ == "__main__":
    main(sys.argv[1:])
