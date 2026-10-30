"""Small audit 1028 rows fixed at the hub, each read from the code it changed."""

from __future__ import annotations

from pathlib import Path

JS = Path(__file__).resolve().parents[1] / "frontend" / "js"


def test_the_empty_documents_library_offers_one_new_document():
    """U29: the head's New document hides while the empty state shows its own."""
    src = (JS / "library.js").read_text(encoding="utf-8")
    assert 'getElementById("library-docs-new")?.classList.toggle("hidden", !docs.length && !isFilteredEmpty)' in src


def test_one_relative_time_helper_for_the_past():
    """S17: the dashboard read "how long ago" with its own copy, worded unlike
    the Library's; it uses `relativeTime` now, and a sentence it opens starts
    with a capital."""
    dash = (JS / "dashboard.js").read_text(encoding="utf-8") + (JS / "dash-night.js").read_text(encoding="utf-8")
    assert "dashRelativeTime" not in dash and "relativeTime(" in dash
    night = (JS / "dash-night.js").read_text(encoding="utf-8")
    assert "Nothing new last time. ${ago.charAt(0).toUpperCase()}${ago.slice(1)}, it found:" in night


def test_the_document_palette_names_every_find_chord():
    """D32: Ctrl+G is Go to line in code and find next in prose; the palette
    lists Go to line for code and find next (F3) for prose, with Ctrl+H."""
    src = (JS / "documents.js").read_text(encoding="utf-8")
    assert 'id: "goto-line", icon: "ph:arrow-line-down", label: "Go to a line", keys: "Ctrl+G",\n    code: true,' in src
    assert 'id: "find-next", icon: "ph:arrow-down", label: "Find the next match", keys: "F3",\n    prose: true,' in src
    assert 'id: "replace-here", icon: "ph:swap", label: "Find and replace in this document", keys: "Ctrl+H",' in src
