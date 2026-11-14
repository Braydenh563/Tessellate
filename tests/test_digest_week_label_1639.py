"""INBOX 1639: "clicking generate this week's digest only shows the line, from
your notes, no ai". The composed week was all there, under the card's fold, and
its first line was the source caption at body size. The week now has its own
label, the caption is a muted footnote, and a click scrolls the card to it."""

from pathlib import Path

DASH = Path(__file__).resolve().parents[1] / "frontend" / "js" / "dashboard.js"


def _widget() -> str:
    js = DASH.read_text(encoding="utf-8")
    start = js.index("async function renderDigestWidget(")
    return js[start:js.index("\n}\n", start)]


def test_the_source_caption_is_a_footnote_not_the_first_line():
    w = _widget()
    #: The caption comes from the server's `source` event now ("Your notes, no AI", L-chat-55): the
    #: old prefix test never matched, nothing wrote "From your notes." into the week.
    assert "source: streamDigest.source" in w
    assert "renderMarkdown(out, words)" in w and 'note.className = "muted"' in w
    # The footnote follows the week, never leads it.
    assert "[head, out, source ? note : null, controls]" in w


def test_the_week_has_its_label_and_is_scrolled_to():
    w = _widget()
    assert 'head.className = "eyebrow"' in w and 'head.textContent = "This week"' in w
    assert "showDigest(text, true)" in w and "toWeek(liveHead)" in w
    # A cached week drawn on load does not move the page.
    assert "showDigest(cached);" in w


def test_the_stream_draws_the_words_without_the_caption():
    assert "renderMarkdown(live, weekParts(soFar).words)" in _widget()
