"""Audit 1031 Z9: the app writes a place in Settings as "Settings, About", never with
an arrow (Y11 did the client; the server's two update strings were left).

A string literal naming Settings with an arrow is what a person reads in a toast or
an error; comments and docstrings are for developers and are left alone.
"""
from __future__ import annotations

import re
from pathlib import Path

SRC = Path(__file__).resolve().parents[1] / "src" / "tessellate"
ARROW = re.compile(r"""^\s*f?(?:"|')[^"']*Settings\s*(?:→|->)""")


def test_no_server_string_writes_a_settings_place_with_an_arrow() -> None:
    hits = []
    for path in SRC.rglob("*.py"):
        lines = path.read_text(encoding="utf-8").splitlines()
        for number, line in enumerate(lines, 1):
            if ARROW.match(line) and not line.lstrip().startswith(("#", '"""')):
                hits.append(f"{path.relative_to(SRC)}:{number}: {line.strip()[:90]}")
    assert not hits, "write 'Settings, About' (comma), not an arrow:\n" + "\n".join(hits)
