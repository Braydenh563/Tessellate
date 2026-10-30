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


def test_a_prompt_heading_has_no_trailing_colon():
    """U33: `promptDialog` shows its message as the dialog's heading, so
    "Rename this document:" read as a label cut off; every caller says it as
    a title now."""
    import re

    for path in JS.glob("*.js"):
        src = path.read_text(encoding="utf-8")
        found = re.findall(r'(?:promptDialog|promptTitle|docPromptInModal)\(\s*(["`])((?:(?!\1).)*?):\1', src, re.S)
        assert not found, f"{path.name}: {[text for _, text in found]}"


def test_no_field_in_the_page_is_named_by_its_placeholder_alone():
    """S13: a placeholder goes the moment someone types and many readers skip
    it, so every field that has one has a label, `for` or wrapping, or an
    aria-label."""
    import re

    html = (JS.parent / "index.html").read_text(encoding="utf-8")
    labelled = set(re.findall(r'<label[^>]*\bfor="([^"]+)"', html))
    bare = []
    for match in re.finditer(r"<(?:input|textarea)\b([^>]*)>", html, re.S):
        attrs = match.group(1)
        if "placeholder=" not in attrs or re.search(r'aria-label=|aria-labelledby=|type="hidden"', attrs):
            continue
        ident = re.search(r'\bid="([^"]+)"', attrs)
        if ident and ident.group(1) in labelled:
            continue
        before = html[: match.start()]
        if before.rfind("<label") > before.rfind("</label>"):
            continue
        bare.append(ident.group(1) if ident else attrs[:60])
    assert not bare, bare
