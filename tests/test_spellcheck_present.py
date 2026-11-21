"""Source text: whether the checker ships is a packaging fact (its files and dependencies), so it is read from the source tree.

The spell checker stays shipped (DOCUMENTS_PLAN owner bug, "you removed
spellchecker.py"). No file of that name ever existed in this repo: the checker
is `ai/spelling.py` (typed questions, the Tidy pass) plus the browser list at
`frontend/vendor/wordlist/en.txt` (the editor's underline). Both must load and
work, so a vendoring clean-up (Brief 35) cannot take either away unseen."""

from __future__ import annotations

from pathlib import Path

from tessellate.ai import spelling

ROOT = Path(__file__).resolve().parent.parent


def test_the_speller_loads_and_tells_words_from_slips() -> None:
    assert spelling.is_word("their")
    assert not spelling.is_word("thier")
    assert not spelling.is_word("noficiations")


def test_the_editors_word_list_ships() -> None:
    words = ROOT / "frontend" / "vendor" / "wordlist" / "en.txt"
    assert words.is_file()
    assert len(words.read_text(encoding="utf-8").split()) > 10000
