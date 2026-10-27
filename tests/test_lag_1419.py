"""INBOX 1419 (launch speed and the forced layouts in the owner's boot log).
Source-shape pins; the numbers (4x CPU throttle, 300 notes) are in the INBOX
entry's result line."""

from __future__ import annotations

from tests._app_js import frontend_text


def _body(js: str, head: str) -> str:
    start = js.index(head)
    return js[start : js.index("\n}\n", start)]


def test_a_strip_indicator_is_placed_after_the_click_not_inside_its_mutation_microtask():
    """The microtask read the whole new page's layout before the click's own
    work was done (library button, whiteboard open, Settings > Help: 100 to
    250ms at 4x CPU each); the frame then laid it out again."""
    glide = _body(frontend_text("shell-reminders.js"), "function glideStrip(")
    assert "new MutationObserver(() => place(true))" not in glide
    assert "setTimeout(() => ((queued = 0), place(true))" in glide


def test_the_notes_strip_token_has_no_read_of_its_own_before_the_observer():
    body = _body(frontend_text("phone-shell.js"), "function initNotesSubtabHeightToken(")
    assert "observe(strip);\n  write();" not in body


def test_the_dashboard_outline_follows_the_grid_after_a_paint():
    body = _body(frontend_text("dashboard.js"), "function dashFillingSkeleton(")
    assert "afterFrames(() => setTimeout(" in body
    assert "grid.offsetTop - top0" in body


def test_the_brand_logo_waits_for_the_page_to_load_before_it_reads_layout():
    body = _body(frontend_text("phone-shell.js"), "function renderBrandLogo(")
    assert 'document.readyState !== "complete"' in body
    assert body.index("document.readyState") < body.index("renderEmblemWhenShown")


def test_the_digest_words_are_stemmed_on_first_use_not_at_import():
    """The first stem builds the spelling-pair table (about 0.3s of every
    launch); the digest's three word sets were stemmed at import."""
    from pathlib import Path

    src = (Path(__file__).resolve().parents[1] / "src/tessellate/ai/composer_digest.py").read_text(encoding="utf-8")
    assert "_FRAME_WORDS = frozenset(composer._stem" not in src
    assert "_VERBS = frozenset(composer._stem" not in src
    assert "_FRAME_WORDS()" in src and "_VERBS()" in src and "_ASKING()" in src
