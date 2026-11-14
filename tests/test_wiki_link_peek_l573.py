"""L573: a note's `[[link]]` previews its note on hover or focus.

The peek is the citation peek's one panel (citation-peek.js), loaded lazily by
a delegate in app.js, so the boot scripts carry three lines, not a card.
"""

from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
JS = ROOT / "frontend" / "js"


def test_a_wiki_link_carries_the_name_it_points_at():
    text = (JS / "notes-list.js").read_text(encoding="utf-8")
    at = text.index('link.className = "wiki-link";')
    assert "link.dataset.wiki = name;" in text[at : at + 120]


def test_hover_and_focus_load_the_peek_lazily():
    text = (JS / "app.js").read_text(encoding="utf-8")
    assert '["mouseover", "focusin"]' in text
    assert '".wiki-link[data-wiki]"' in text
    assert 'wikiPeek: ["/js/citation-peek.js", "/js/wiki-peek.js"]' in text
    # A failed load never calls into a file that did not arrive.
    assert 'ensureModule("wikiPeek").then((ok) => ok && wikiPeek(' in text
    index = (ROOT / "frontend" / "index.html").read_text(encoding="utf-8")
    assert "wiki-peek.js" not in index


def test_the_peek_previews_notes_only_and_waits_on_hover():
    text = (JS / "wiki-peek.js").read_text(encoding="utf-8")
    assert "resolveWikiTarget(link.dataset.wiki)" in text
    assert 'target?.kind !== "note"' in text
    assert "keyboard ? 0 : 350" in text
    assert "openCitationPeek(link," in text
    assert "Object.assign(window, { wikiPeek })" in text


def test_help_says_a_link_previews():
    from tessellate.ai import help_topics_core

    body = next(t["body"] for t in help_topics_core.TOPICS if t["id"] == "links") if hasattr(help_topics_core, "TOPICS") else Path(help_topics_core.__file__).read_text(encoding="utf-8")
    assert "Hover or focus a [[link]] to preview its note." in body
