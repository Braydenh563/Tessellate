"""The picker carries a Japanese emoticons (kaomoji) group (INBOX 904 B81).

Kaomoji hold commas, equals signs and backslashes, so they cannot live in
`ICON_EMOJI_SOURCE`'s `name=glyph,name=glyph` strings: they are an array of
`[name, text, aliases]`. Run in node, like `test_icon_picker_aliases.py`.
"""

import json
import re
import shutil
import subprocess
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
JS = (ROOT / "frontend" / "js" / "icon-picker.js").read_text(encoding="utf-8")
CSS = (ROOT / "frontend" / "css" / "icon-picker.css").read_text(encoding="utf-8")

pytestmark = pytest.mark.skipif(shutil.which("node") is None, reason="node is not installed")


def _run(expr: str):
    table = re.search(r"^const ICON_KAOMOJI = \[.*?^\];", JS, re.S | re.M)
    aliases = re.search(r"^const ICON_EMOJI_ALIASES = \{.*?^\};", JS, re.S | re.M)
    hay = re.search(r"^function iconPickerHay\(.*?^\}", JS, re.S | re.M)
    assert table, "ICON_KAOMOJI must be an array of [name, text, aliases]"
    assert aliases and hay
    script = f"{aliases.group(0)}\n{hay.group(0)}\n{table.group(0)}\nconsole.log(JSON.stringify({expr}));"
    return json.loads(subprocess.run(["node", "-e", script], capture_output=True, text=True, check=True).stdout)


def test_the_group_is_a_list_of_names_and_texts() -> None:
    rows = _run("ICON_KAOMOJI")
    assert len(rows) >= 30
    names = [r[0] for r in rows]
    texts = [r[1] for r in rows]
    assert len(set(names)) == len(names) and len(set(texts)) == len(texts)
    for name, text, *_ in rows:
        assert name == name.lower() and text.strip() == text and text
    #: The one the owner named by shape must survive a JS string's backslash.
    assert "¯\\_(ツ)_/¯" in texts


@pytest.mark.parametrize(
    "word, name",
    [("shrug", "shrug"), ("table flip", "table flip"), ("happy", "happy"), ("cry", "crying"), ("angry", "angry")],
)
def test_everyday_words_find_them(word: str, name: str) -> None:
    hay = _run("ICON_KAOMOJI.map(([n, t, a]) => iconPickerHay({name: n, aliases: a},'Japanese emoticons'))")
    rows = _run("ICON_KAOMOJI")
    found = [r[0] for r, h in zip(rows, hay) if all(w in h for w in word.split())]
    assert name in found, (word, found)


def test_no_text_uses_an_em_dash() -> None:
    assert chr(0x2014) not in "".join(r[1] for r in _run("ICON_KAOMOJI"))


def test_the_group_is_wide_tiles_in_the_picker() -> None:
    assert "Japanese emoticons" in JS and "icon-picker-tile-wide" in JS
    assert ".icon-picker-tile-wide" in CSS
