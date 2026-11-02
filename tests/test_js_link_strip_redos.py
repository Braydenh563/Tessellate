"""Markdown link stripping in the frontend runs in linear time (OPEN 846).

`\\[([^\\]]*)\\]\\([^)]*\\)` unanchored is quadratic: on 40,000 "[" (or
"[a](" repeated) every start scans to the end of the text and backs off.
Measured in node: 8.6 s and 7.2 s for one `.replace` over a pasted
document's worth of brackets. The safe shape leaves the next opener out of
each run (`[^[\\]\\n]*` for the text, `[^()\\n]*` for the address), so a
failed start stops at the next bracket: 1 ms on the same inputs. The Python
side has its own oracle tests; this is the JavaScript one.
"""

from __future__ import annotations

import re
import shutil
import subprocess
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
JS = sorted((ROOT / "frontend" / "js").glob("*.js"))

#: A link's text run that may cross the next "[" or a line, unbounded.
QUADRATIC = re.compile(r"\[\^\\\]\]\*\)?\\\]\\\(")


def test_no_unanchored_link_strip_crosses_the_next_bracket():
    offenders = []
    for path in JS:
        for n, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
            if QUADRATIC.search(line) and "/^" not in line:
                offenders.append(f"{path.name}:{n}")
    assert offenders == []


@pytest.mark.skipif(shutil.which("node") is None, reason="node not installed")
def test_the_link_strips_finish_on_a_wall_of_brackets():
    script = r"""
const rs = [/!\[([^[\]\n]*)\]\([^()\n]*\)/g, /\[([^[\]\n]*)\]\([^()\n]*\)/g, /!?\[([^[\]\n]*)\]\([^()\n]*\)?/g,
            /!?\[([^[\]\n|]*)(?:\|[^[\]\n]*)?\]\([^()\n]*\)?/g];
for (const s of ["[".repeat(40000), "[a](".repeat(20000)]) for (const r of rs) s.replace(r, "$1");
const said = "see [the docs](https://x.y/z) and ![pic](a.png)".replace(rs[2], "$1");
if (said !== "see the docs and pic") throw new Error(said);
const aliased = "see [the docs|alias](https://x.y/z)".replace(rs[3], "$1");
if (aliased !== "see the docs") throw new Error(aliased);
"""
    for path, needle in (
        ("documents-prose.js", r"/\[([^[\]\n]*)\]\([^()\n]*\)/g"),
        #: The alias after "|" is dropped (UX review 1031, a48d533) in a
        #: separate group, so the two runs never overlap.
        ("navigation.js", r"/!?\[([^[\]\n|]*)(?:\|[^[\]\n]*)?\]\([^()\n]*\)?/g"),
        ("desk-companion.js", r"/!?\[([^[\]\n|]*)(?:\|[^[\]\n]*)?\]\([^()\n]*\)?/g"),
    ):
        assert needle in (ROOT / "frontend" / "js" / path).read_text(encoding="utf-8"), path
    subprocess.run(["node", "-e", script], check=True, timeout=60)
