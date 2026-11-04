"""D30 (audit 1028): spelling follows a document's `lang` frontmatter key. The English list
cannot spell French, so a document marked as another language gets no spelling check until a
language pack is installed, rather than every word flagged."""

from __future__ import annotations

import json
import shutil
import subprocess
from pathlib import Path

import pytest

SOURCE = (Path(__file__).resolve().parent.parent / "frontend" / "js" / "documents.js").read_text(encoding="utf-8")


def _block(start: str) -> str:
    i = SOURCE.index(start)
    return SOURCE[i : SOURCE.index("\n}", i) + 2]


def _method() -> str:
    i = SOURCE.index("  langOf(text) {")
    return SOURCE[i : SOURCE.index("\n  },", i) + 5]


def _lang(text: str) -> str:
    node = shutil.which("node")
    if not node:
        pytest.skip("node is not installed")
    script = f"const docProse = {{ {_method()} }};\nconsole.log(JSON.stringify(docProse.langOf({json.dumps(text)})));\n"
    return json.loads(subprocess.run([node, "-e", script], capture_output=True, text=True, check=True).stdout)


@pytest.mark.parametrize(
    ("text", "want"),
    [
        ("plain text", "en"),
        ("---\ntitle: x\n---\nbody", "en"),
        ("---\nlang: fr\n---\nbonjour", "fr"),
        ("---\nlanguage: \"de-CH\"\n---\nhallo", "de"),
        ("---\nlang: en-GB\n---\ncolour", "en"),
        ("---\nlang: FR\r\n---\r\nx", "fr"),
        ("body\n---\nlang: fr\n---", "en"),
    ],
)
def test_lang_key_is_read_from_leading_frontmatter_only(text: str, want: str) -> None:
    assert _lang(text) == want


def test_non_english_skips_the_word_loop_and_the_panel_says_so() -> None:
    prose = _block("function docProseFindings(")
    assert 'docProse.langOf(text) === "en"' in prose
    assert "checkWords" in prose
    assert "docProse.langNote(" in SOURCE
