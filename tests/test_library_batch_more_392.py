"""Source text: the Library bar's menu wiring is read from the script text, as the unit suite has no browser to drive; it was driven in a sweep.

L-world-class-392 (WORLD_CLASS_PLAN decision 65): the Library's selection
bar sets tags, a category or a property on the notes ticked, through the
dialogs the Notes bar opens. Documents, chats and files carry none of the
three, so the menu acts on notes only and hides when no note is ticked.
Measured with scratchpad/sw/lib392.js: two notes set "stage: draft" (toast
"Set stage on 2 notes. Undo"), moved to Fitness, the Tags dialog opened for
2 notes; the menu button is 32px, in Delete's row.
"""

from pathlib import Path

from tests._app_js import frontend_text

HTML = (Path(__file__).parents[1] / "frontend" / "index.html").read_text(encoding="utf-8")
JS = frontend_text("library.js")


def _bars() -> str:
    start = JS.index("function renderLibraryContextBars(")
    return JS[start : JS.index("\n}\n", start)]


def test_the_library_bar_has_a_more_menu_before_delete():
    bar = HTML[HTML.index('id="library-selectbar"') : HTML.index('id="library-grid"')]
    assert bar.index('id="library-batch-more-host"') < bar.index('id="library-bulk-delete"')


def test_the_menu_opens_the_notes_bars_own_dialogs_for_ticked_notes():
    body = _bars()
    assert 'filter((i) => i.kind === "note")' in body
    for call in ("openBulkTags(notes())", "chooseNoteCategory(notes())", "openBulkProperty(notes())"):
        assert call in body
    assert 'kebabMenu([' in body, "a menu is kebabMenu (standing order 11)"
    assert 'more.classList.toggle("hidden", !chosen.some((key) => key.startsWith("note:")))' in body


def test_help_names_the_menu():
    from tessellate.ai.help_topics_core import HELP_TOPICS

    library = " ".join(t["body"] for t in HELP_TOPICS if "Tick a card's box" in t["body"])
    assert "More (tags, category or a property for the notes ticked)" in library
