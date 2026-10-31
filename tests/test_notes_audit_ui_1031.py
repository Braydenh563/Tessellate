"""Notes audit 1031, the shared-helper rows that live in the client.

N34 the `[[` picker inserts the title without its heading marker; N38 one
preview pass for tables, fences and formulas; N39 a picker row reads as a
phrase; N14 the phone note page does not say its title twice; N30 a link
chip's menu always has a name.
"""

from __future__ import annotations

import json
import re
import shutil
import subprocess
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
JS = ROOT / "frontend" / "js"
NODE = shutil.which("node")


def _function(path: str, name: str) -> str:
    text = (JS / path).read_text()
    start = text.index(f"function {name}(")
    return text[start : text.index("\n}\n", start) + 3]


@pytest.mark.skipif(NODE is None, reason="node is not available")
@pytest.mark.parametrize(
    "text,expected",
    [
        ("Table note\n| a | b |\n|---|---|\n| 1 | 2 |", "Table note\na · b\n\n1 · 2"),
        ("```js\nconst x = 1;\n```", "const x = 1;"),
        ("$$\\int_0^1 x^2 dx$$ and more", "formula and more"),
        ("one | two is not a table", "one | two is not a table"),
    ],
)
def test_one_preview_pass_for_tables_fences_and_formulas(text, expected):
    script = _function("shell-reminders.js", "previewBlocks") + "\nconsole.log(JSON.stringify(previewBlocks(process.argv[1])));"
    out = subprocess.run([NODE, "-e", script, text], capture_output=True, text=True, timeout=30)
    assert json.loads(out.stdout) == expected


def test_both_preview_helpers_use_that_pass():
    assert "previewBlocks(stripFrontmatter(" in (JS / "shell-reminders.js").read_text()
    assert "return previewBlocks(text)" in (JS / "navigation.js").read_text()


def test_the_picker_inserts_the_title_without_its_hash():
    body = (JS / "editor.js").read_text()
    assert '.replace(/^\\s*#{1,6}\\s+/, "")' in body[body.index("// Link by the note's opening words") :][:900]


def test_a_picker_row_is_named_as_a_phrase():
    row = _function("rich-picker.js", "richPickerRow")
    assert "aria-label" in row and "${title.textContent}, ${about}" in row


def test_the_phone_note_page_drops_the_title_its_head_already_says():
    shell = (JS / "phone-shell.js").read_text()
    assert "function dropRepeatedTitle(" in shell
    assert shell.count("dropRepeatedTitle(") >= 3  # the definition, the open and the refresh


def test_a_link_menu_is_never_nameless():
    assert re.search(r"Actions for the link to \$\{label \|\| ", (JS / "note-cards.js").read_text())
