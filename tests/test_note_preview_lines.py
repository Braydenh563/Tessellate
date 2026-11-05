"""INBOX 458: a long note's clamped preview showed "..." alone under its
title. The body kept the blank line after the title (or a second one), and
the two-line clamp spent its lines on blanks. The preview strips every blank
line after the title and, while clamped, runs the paragraphs together."""

from tests._app_js import app_js_text


def test_every_blank_line_after_the_title_goes():
    app = app_js_text()
    body = app[app.index("function bodyWithoutTitleLine"):]
    body = body[: body.index("\n}\n")]
    assert 'while (lines[i] !== undefined && lines[i].trim() === "") lines.splice(i, 1);' in body


def test_a_clamped_card_collapses_its_blank_lines_and_an_open_one_does_not():
    app = app_js_text()
    assert 'content.classList.contains("entry-clamped") ? body.replace(' in app
    # Opening, closing and the "it fitted after all" check all redraw.
    assert app.count("fillContent();") >= 3


# INBOX 473: "increase the amount of lines or characters in a note that show
# before it gets cut off by the show more". The clamp was 2 lines (1 on a
# phone); it is one token now, 4 by default, 3 compact and 5 spacious.
def _css(name):
    from pathlib import Path

    return (Path(__file__).resolve().parent.parent / "frontend" / "css" / name).read_text(encoding="utf-8")


def test_the_clamp_is_one_token_that_density_changes():
    forms = _css("01-forms-settings.css")
    assert ":root {\n  --note-preview-lines: 4;\n}" in forms
    compact = forms[forms.index(':root[data-density="compact"]'):]
    assert "--note-preview-lines: 3;" in compact[: compact.index("}")]
    spacious = forms[forms.index(':root[data-density="spacious"]'):]
    assert "--note-preview-lines: 5;" in spacious[: spacious.index("}")]
    rule = _css("06-timeline-dialogs.css")
    #: A long chat question folds with the same clamp (9ac90c4), so the selector is a list.
    rule = rule[rule.index(".entry-content.entry-clamped,"):]
    rule = rule[: rule.index("}")]
    assert "-webkit-line-clamp: var(--note-preview-lines);" in rule


def test_no_breakpoint_pins_the_clamp_back_to_one_line():
    assert ".entry-content.entry-clamped" not in _css("10-responsive.css")


def test_the_js_threshold_agrees_with_the_clamp():
    app = app_js_text()
    assert "const LONG_NOTE_LINES = 3;" in app
