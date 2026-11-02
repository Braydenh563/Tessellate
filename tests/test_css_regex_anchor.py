"""A CSS rule regex starts at a brace, never at every character (CI time, 1102).

`re.findall(r"([^{}]+)\\{", css)` over the 3.2 MB stylesheet took 16 s: where a
run of text ends at `}` the match fails, and the engine retries it from every
later character of the run, so the cost is the square of each block's length.
The reduced-motion lint spent 29 s that way and the motion recipes 24 s; the
3.11 and 3.12 Tests jobs ran out of their 40 minutes (PR 211).

A run that fails from its first character fails from every later one, so
anchoring the start after a brace (or at the start of the text) finds the same
matches: 0.06 s for the pattern above. This keeps the next lint from bringing
the quadratic form back.
"""

from __future__ import annotations

import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
ANCHOR = r"(?:(?<=[{}])|\A)"
UNANCHORED = re.compile(r"""r["']\(?\[\^\{\}\][*+]""")


def test_brace_class_patterns_are_anchored():
    offenders = []
    for folder in ("tests", "scripts"):
        for path in sorted((ROOT / folder).rglob("*.py")):
            if path.name == Path(__file__).name:
                continue  # the sample below is the unanchored form on purpose
            for number, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
                if UNANCHORED.search(line):
                    offenders.append(f"{path.relative_to(ROOT)}:{number}")
    assert not offenders, (
        f"Start these patterns with {ANCHOR}, or each failed run is retried "
        "from every character (16 s over the stylesheet):\n  " + "\n  ".join(offenders)
    )


def test_the_anchor_finds_the_same_rules():
    css = ".a { color: red; }\n@media (x) { .b { top: 0 } }\n.c{}"
    plain = re.findall(r"([^{}]+)\{([^{}]*)\}", css)
    assert re.findall(ANCHOR + r"([^{}]+)\{([^{}]*)\}", css) == plain
