"""One word count for every surface (notes audit 1031, N15; INBOX 1495).

A Japanese note was "1 word" on the card, the chat note card, the rail and the
capture box, because every count split on spaces. `core/cjk.word_count` and
the client's `wordCount` count a Han or kana character as a word and every
other script by its spaces, and agree on a shared fixture.
"""

import json
import re
import shutil
import subprocess
from pathlib import Path

import pytest

from tessellate.ai import utilities
from tessellate.core import cjk

ROOT = Path(__file__).resolve().parents[1]
JS = ROOT / "frontend" / "js"

FIXTURE = [
    ("", 0),
    ("one two  three\nfour", 4),
    ("週末のゴルフについての考え", 13),
    ("Harbor 計画 plan", 4),
    ("한국어 단어 입니다", 3),
    ("ゴルフ。考え、 done", 6),
    ("考え：仕事を済ませてから、練習", 13),
    ("今日は！雨？ ok, fine", 6),
]


@pytest.mark.parametrize("text,count", FIXTURE)
def test_the_server_counts(text, count):
    assert cjk.word_count(text) == count


def test_the_text_utilities_use_it():
    assert utilities.counts("週末のゴルフ")["words"] == 6
    assert utilities.counts("a b c")["words"] == 3


@pytest.mark.skipif(shutil.which("node") is None, reason="node is not available")
def test_the_client_counts_the_same():
    source = (JS / "settings-wiring.js").read_text(encoding="utf-8")
    start = source.index("const WORD_PER_CHARACTER")
    end = source.index("function textCounts(")
    script = source[start:end] + "\nconsole.log(JSON.stringify(process.argv.slice(1).map(wordCount)));"
    out = subprocess.run(["node", "-e", script, *[text for text, _ in FIXTURE]], capture_output=True, text=True, timeout=30)
    assert out.returncode == 0, out.stderr
    assert json.loads(out.stdout) == [count for _, count in FIXTURE]


def test_no_surface_splits_a_note_on_spaces_to_count_it():
    for name, pattern in (
        ("reply-kit.js", r"plainText\(content\)\.split\(/\\s\+/\)"),
        ("note-edit-panels.js", r"match\(/\\S\+/g\)"),
        ("dashboard.js", r"entry\.content \|\| \"\"\)\.match\(/\\S\+/g\)"),
        ("settings-wiring.js", r"const words = \(value\.match"),
    ):
        assert not re.search(pattern, (JS / name).read_text(encoding="utf-8")), name
