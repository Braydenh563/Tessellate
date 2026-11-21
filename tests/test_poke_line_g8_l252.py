"""L252 (audit G8): a face does not say the same poke line twice running."""

from __future__ import annotations

import re
from pathlib import Path

SRC = (Path(__file__).resolve().parent.parent / "frontend/js/avatars.js").read_text()


def _body() -> str:
    start = SRC.index("function nameMarkLine(seed)")
    return SRC[start:SRC.index("\n  }\n", start)]


def test_the_poke_line_skips_the_one_just_said():
    body = _body()
    assert "lastNameMarkLine" in body and re.search(r"filter\(\(line\) => line !== lastNameMarkLine\)", body)


def test_every_mood_has_a_second_line_to_move_to():
    table = SRC[SRC.index("const NAME_MARK_LINES"):SRC.index("function nameMarkLine")]
    for mood, lines in re.findall(r"(\w+): \[([^\]]*)\]", table):
        assert lines.count('", "') >= 1 or lines.count('","') >= 1, mood
