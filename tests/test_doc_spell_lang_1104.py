"""D30 (audit 1028): spelling follows a document's `lang` frontmatter key. The English list
cannot spell French, so a document marked as another language gets no spelling check until a
language pack is installed, rather than every word flagged."""

from __future__ import annotations
from tests._app_js import frontend_text

import json
import shutil
import subprocess
from pathlib import Path

import pytest

SOURCE = frontend_text("documents.js")


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


BAD = "The the cat. Your going to love it. Thier dog is here."


def _findings(text: str) -> list[str]:
    import tempfile

    root = Path(__file__).resolve().parent.parent
    with tempfile.TemporaryDirectory() as tmp:
        fixture = Path(tmp) / "f.json"
        fixture.write_text(json.dumps({"clean": [{"tag": "t", "text": text}], "planted": []}), encoding="utf-8")
        out = subprocess.run(
            ["node", str(root / "tests" / "_grammar_harness.js"), str(root), str(fixture)],
            capture_output=True, text=True, timeout=180, check=True,
        )
    return [f["rule"] for f in json.loads(out.stdout)["clean"][0]["findings"]]


@pytest.mark.skipif(shutil.which("node") is None, reason="node is not installed")
def test_english_document_is_checked_and_a_french_one_is_not() -> None:
    assert {"repeat", "confusion", "spelling"} <= set(_findings(BAD))
    assert _findings("---\nlang: fr\n---\n" + BAD) == []


def test_panel_note_names_spelling_and_grammar() -> None:
    assert "Spelling and grammar are off" in SOURCE
