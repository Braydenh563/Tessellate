"""Blind test 2026-10-31, items 7, 9 and 10: one read per boot, and labels that
say what they are.

Measured in the running app (port 8810, fresh data dir, 1440x900): GET
/help/sample-notebook fired 2 times per boot before, 1 after (the dashboard's
card, its Get started menu and the bell row each asked for the same state at
once). The bell said "2 of 3 done" with no name set, which was true (a note and
an answer); it now says what is left. Drag reorder with a real mouse (press,
still hold, move, release) put the third card first on Notes (sort became
Custom order) and on Library, Documents: nothing to fix there."""
from pathlib import Path

from tessellate.ai import help_chat, help_topics_more
from tests._app_js import app_js_text

FRONTEND = Path(__file__).resolve().parents[1] / "frontend"


def _js(name: str) -> str:
    return (FRONTEND / "js" / name).read_text(encoding="utf-8")


def test_the_first_steps_state_is_one_shared_in_flight_read():
    js = _js("first-run.js")
    assert "let firstStepsPending = null;" in js
    start = js.index("function firstStepsState()")
    body = js[start : js.index("\n}\n", start)]
    assert "if (!firstStepsPending)" in body and ".finally(" in body
    assert body.count("firstStepsRead()") == 1
    # The three fetches live in the read, once, not in the wrapper.
    assert js.count('apiJson("/help/sample-notebook")') == 1


def test_the_bell_row_names_what_is_left():
    js = _js("first-run.js")
    assert 'Left: ${todo.join(", ")}' in js


def test_a_tag_suggestion_has_short_names_and_titles():
    js = _js("note-cards.js")
    assert 'take.setAttribute("aria-label", `Add tag ${tag}`)' in js
    assert 'discard.setAttribute("aria-label", `Dismiss tag ${tag}`)' in js
    assert "`Add tag ${tag}. ${reason}`" in js
    assert "`Dismiss: stop suggesting #${tag} for this note`" in js


def test_the_date_chip_says_it_is_not_a_reminder():
    assert "Dates this note mentions, not a reminder." in _js("note-cards.js")


def test_the_filter_menus_say_what_they_hold():
    html = (FRONTEND / "index.html").read_text(encoding="utf-8")
    assert 'title="Filter options: match notes by meaning, or keep this search to come back to"' in html
    assert 'title="Filter options: match by meaning, or include the bin"' in html


def test_save_and_save_as_draft_say_how_they_differ():
    html = (FRONTEND / "index.html").read_text(encoding="utf-8")
    save = html[html.index('<button id="save-btn"') :].split(">", 1)[0]
    draft = html[html.index('<button id="save-draft-btn"') :].split(">", 1)[0]
    assert "file it by category and tags" in save and "Save as draft keeps it unfiled" in save
    assert "nothing is filed" in draft and "Drafts" in draft


def test_a_saved_capture_offers_the_way_back_to_writing():
    js = app_js_text()
    start = js.index("function offerJumpToNewNote(")
    body = js[start : js.index("\n}\n", start)]
    assert 'smallButton("ph:pencil-simple Write another"' in body and "focusCaptureBox" in body


def test_help_names_the_new_words():
    capture = next(t for t in help_chat.HELP_TOPICS if t["id"] == "capture")["body"]
    assert "Write another" in capture and "Save as draft" in capture
    tags = next(t for t in help_topics_more.MORE_TOPICS if t["id"] == "suggested-tags")["body"]
    assert "(Dismiss)" in tags


def test_new_copy_has_no_em_dash_or_exclamation():
    for text in (_js("first-run.js"), _js("note-cards.js")):
        for line in ("Left: ", "Dates this note mentions", "Dismiss: stop suggesting"):
            for row in [r for r in text.splitlines() if line in r]:
                assert chr(0x2014) not in row and "!" not in row.replace("!==", "").replace("!=", "").replace("!(", "").replace("!!", ""), row
