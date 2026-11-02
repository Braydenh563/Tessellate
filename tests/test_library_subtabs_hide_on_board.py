"""INBOX 476: the Library sub-tab bar hides while a whiteboard or mind map is
open, at every width, as it never showed on the documents editor (that is its
own page). It was a phone-only rule; the editor's own Back ("Boards") returns
to the list and the bar with it."""

from pathlib import Path

CSS = Path(__file__).resolve().parent.parent / "frontend" / "css" / "10-responsive.css"
SELECTOR = (
    "#tab-library:has(> #library-view-whiteboard:not(.hidden) "
    "> #wb-canvas-view:not(.hidden)) #library-subtabs {"
)


def test_the_rule_is_top_level_not_inside_a_phone_media_query():
    css = CSS.read_text(encoding="utf-8")
    at = css.index(SELECTOR)
    line_start = css.rindex("\n", 0, at) + 1
    # A top-level rule starts in column 0; the phone version was indented
    # inside `@media (max-width: 599.98px)`.
    assert at == line_start
    assert css[at : css.index("}", at)].count("display: none;") == 1


def test_the_board_has_its_own_way_back():
    index = (CSS.parent.parent / "index.html").read_text(encoding="utf-8")
    assert 'id="wb-back-to-boards"' in index
