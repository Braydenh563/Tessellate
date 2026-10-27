"""The composed weekly digest's reminder lines (owner, 2026-10-27).

A reminder's text can keep the stub of the date the parser lifted out of it
("when I get home , probably around"), and the line then read "home , probably
around (20 October)": a space before the comma, a dangling "around", and the
date in brackets as if it were part of the words. Fixed clock throughout."""

from datetime import date, datetime, timezone
from types import SimpleNamespace

from tessellate.ai import activity

TODAY = date(2026, 10, 27)


def _row(text, day):
    return SimpleNamespace(text=text, due_at=datetime(2026, 10, day, 9, 0, tzinfo=timezone.utc))


def _said(*rows):
    return activity._named(list(rows), TODAY, timezone.utc)


def test_stub_of_a_lifted_date_is_tidied():
    said = _said(_row("Do my tax return when I get home , probably around", 20))
    assert " ," not in said
    assert "around (" not in said and "probably (" not in said
    assert said == "Do my tax return when I get home (due 20 October)."


def test_plain_reminder_keeps_its_words_and_gets_the_due_date():
    assert _said(_row("Renew the passport", 25)) == "Renew the passport (due 25 October)."


def test_a_comma_inside_the_words_stays():
    assert _said(_row("Buy milk, eggs and bread", 25)) == "Buy milk, eggs and bread (due 25 October)."


def test_a_link_label_with_markup_draws_inside_the_link():
    """The composer links a bold title (`[**Title**](#/note/3)`); the renderer
    read the label as plain text and printed the asterisks."""
    from tests._app_js import app_js_text

    js = app_js_text()
    start = js.index("if (!labelIsTheUrl && LINK_LABEL_MARKUP.test(linkText)) {")
    block = js[start : js.index("element.appendChild(a);", start)]
    assert "appendInlineRun(a, linkText" in block
    # No link in a link, no picture in a link; the label never goes in as HTML.
    assert "autolinkBareUrls: false" in block and "innerHTML" not in block
