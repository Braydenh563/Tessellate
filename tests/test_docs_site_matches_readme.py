"""docs/index.html says what the README says (L-world-class-187, IDEAS.md
"check docs/index.html's text against the README"). The checked pass found the
page still saying that with no model notes stay Uncategorised and answers wait
for a model, while the README (and the words path, CHAT_PLAN decision 75)
files and answers without one; and it listed four graph layouts of seven."""

from __future__ import annotations

import html
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
PAGE = ROOT / "docs" / "index.html"


def _text(path: Path) -> str:
    raw = re.sub(r"(?s)<(script|style)\b.*?</\1>", "", path.read_text(encoding="utf-8"))
    return " ".join(html.unescape(re.sub(r"<[^>]+>", " ", raw)).split())


def test_the_page_does_not_say_a_model_is_needed_to_file_or_answer():
    page = _text(PAGE)
    assert "filed as Uncategorised" not in page
    assert "Filing and answers switch on when you add a model" not in page
    readme = (ROOT / "README.md").read_text(encoding="utf-8")
    assert "With no model, Atlas still answers from your notes" in readme
    assert "answers from your notes with citations" in page


def test_the_page_names_every_graph_layout_the_app_offers():
    graph = (ROOT / "frontend/js/graph.js").read_text(encoding="utf-8")
    kinds = re.search(r'return \[("force"[^\]]*)\]\.includes\(saved\)', graph).group(1)
    names = [k.strip().strip('"') for k in kinds.split(",") if k.strip().strip('"') != "map"]
    line = re.search(r"([A-Z][a-z]+(?:, [a-z]+)*,? and [a-z]+ layouts)", _text(PAGE)).group(1).lower()
    assert all(name in line for name in names), (names, line)


def test_the_shortcuts_the_page_names_are_the_readme_ones():
    page, readme = _text(PAGE), (ROOT / "README.md").read_text(encoding="utf-8").replace("`", "")
    for keys in re.findall(r"\b(?:Ctrl\+Shift\+[A-Z]|Ctrl\+[A-Z]|Alt\+[A-Z])\b", page):
        assert keys in readme, keys
