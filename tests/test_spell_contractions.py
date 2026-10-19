"""A missing apostrophe ("whats") is offered as the contraction ("what's") first in the
spelling menu, never as an automatic rewrite (the owner, 2026-10-19)."""

from __future__ import annotations

import json
import re
import shutil
import subprocess
from pathlib import Path

import pytest

SOURCE = (Path(__file__).resolve().parent.parent / "frontend" / "js" / "documents.js").read_text(encoding="utf-8")


def _block(start: str, end: str) -> str:
    i = SOURCE.index(start)
    return SOURCE[i : SOURCE.index(end, i) + len(end)]


@pytest.mark.parametrize(
    ("word", "want"),
    [("whats", "what's"), ("thats", "that's"), ("isnt", "isn't"), ("youre", "you're"), ("im", "i'm"),
     ("hats", None), ("its", None), ("wats", None)],
)
def test_a_missing_apostrophe_is_offered(word: str, want: str | None) -> None:
    node = shutil.which("node")
    if not node:
        pytest.skip("node is not installed")
    script = (
        "const docWordlist = new Set(['what', 'that', \"isn't\", 'hat', 'it']);\n"
        + _block("const DOC_CONTRACTION_BASES", "\n};")
        + "\n"
        + _block("function docSpellContraction(", "\n}")
        + f"\nconsole.log(JSON.stringify(docSpellContraction({json.dumps(word)})));\n"
    )
    out = subprocess.run([node, "-e", script], capture_output=True, text=True, check=True)
    assert json.loads(out.stdout.strip()) == want


def test_the_contraction_leads_the_menu_but_is_never_the_sure_answer() -> None:
    guesses = _block("function docSpellGuesses(", "\n}")
    assert "words.unshift(contraction)" in guesses
    confident = _block("function docSpellConfident(", "\n}")
    assert not re.search(r"docSpellContraction", confident)
