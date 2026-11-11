"""Wrap a classic frontend script whole in one closure (ranked row 37a).

    python scripts/wrap_scope.py frontend/js/FILE.js exportedName [more ...]

The header comment stays outside; the body moves two spaces in, inside
`(() => {` ... `})();`, and the foot lists the names other files call:
`Object.assign(window, { name });`. A multi-line template literal's own lines are not indented. Then run
`node --check`, `tests/test_global_scope_ratchet.py` (lower
`GLOBAL_NAMES_CAP` by what it printed) and the file's own tests.
"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from tests._js_scope import template_lines  # noqa: E402


def wrap(text: str, exports: list[str]) -> str:
    lines = text.split("\n")
    #: A line that begins inside a multi-line template literal is string text:
    #: indenting it would change the string, so it stays as it is (the inverse of
    #: `tests/_js_scope.unwrapped`, which reads the same set).
    inside = template_lines(text)
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
    return "\n".join(lines[:start] + ["(() => {"] + [("  " + line) if line.strip() and start + n not in inside else line for n, line in enumerate(body)] + foot)


def main(argv: list[str]) -> None:
    if len(argv) < 2:
        raise SystemExit(__doc__)
    path = Path(argv[0])
    path.write_text(wrap(path.read_text(encoding="utf-8"), argv[1:]), encoding="utf-8")
    print(f"wrapped {path.name}, exporting {', '.join(argv[1:])}")


if __name__ == "__main__":
    main(sys.argv[1:])
