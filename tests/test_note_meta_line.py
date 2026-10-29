"""A note's details line is one line (INBOX 455 (1)).

The owner: "note metadata wraps now and needs a better redesign and
structure. also I think the note date should be consistent in where it is on
the notes." Measured at 1100 before (`scratchpad/ui-sweeps/notemeta.js`, ten
seeded cards): six lines wrapped and the time sat on a line of its own on
some cards and beside the facts on others. The line is `nowrap` now; tags and
suggestions that do not fit fold into one "+N" chip, then the word facts keep
only their icon, then ellipsise; the time is always the line's last fact.
The browser half (no wrap at 1440, 1100, 820 and 390, one date x per width)
is the sweep's; this holds the shape so it cannot drift back.
"""

from __future__ import annotations

import re

from tests._app_js import JS_DIR

CSS_DIR = JS_DIR.parent / "css"


def _read(name: str) -> str:
    return (JS_DIR / name).read_text(encoding="utf-8")


def _css(name: str) -> str:
    return (CSS_DIR / name).read_text(encoding="utf-8")


def test_the_line_never_wraps():
    css = _css("08-consistency.css")
    rules = re.findall(r"\n\.entry-meta\.note-meta \{([^}]*)\}", css)
    assert any("flex-wrap: nowrap" in rule for rule in rules)
    # Measuring sees every fact at its own width; only then may some shrink.
    assert ".entry-meta.note-meta > * {\n  flex-shrink: 0;" in css
    assert ".entry-meta.note-meta:not(.is-measuring) > :is(" in css
    assert ".entry-meta.note-meta > .chip.is-icon > .ph-text {\n  display: none;" in css


def test_what_does_not_fit_folds_into_one_more_chip():
    cards = _read("note-cards.js")
    assert "const noteMetaFit = new ResizeObserver(" in cards
    assert "noteMetaFit.observe(meta);" in cards
    assert "meta.appendChild(noteMetaMore(entry));" in cards
    fit = cards[cards.index("function fitNoteMetas("):cards.index("async function publishDraft(")]
    # Reset, read and fold in three passes over every line, so a long list
    # costs two layouts rather than one per card.
    assert fit.count("for (const") >= 3 and 'classList.add("is-measuring")' in fit
    assert "el.hidden = true" in fit and 'classList.add("is-icon")' in fit
    # The "+N" opens the rest, each row doing what its chip does.
    more = cards[cards.index("function noteMetaMore("):]
    assert "openMenuAtPoint(items" in more[:1500]
    assert "filterNotesByTag(tag)" in more[:1500] and "answerTags(entry, { take: [tag] })" in more[:1500]
    # A card off screen is fitted when it is drawn, not measured alone; a
    # line that fits as drawn is left alone.
    assert 'addEventListener("contentvisibilityautostatechange"' in fit
    assert "const lines = drawn.filter(" in fit
    # A count chip patched in later is fitted again (INBOX 1446: once for the
    # batch, after every chip is in, not once per card).
    assert "fitNoteMetas(fitted)" in _read("notes-list.js")


def test_the_time_is_the_lines_last_fact_everywhere():
    cards = _read("note-cards.js")
    block = cards[cards.index('date.className = "entry-date";'):]
    assert "meta.appendChild(date);" in block[:2000]
    # The imported file's chip goes before it, not after.
    assert "meta.insertBefore(fileChip, date);" in cards
    # One auto margin on the phone's line (the time's), not two: two split the
    # room and moved the time on every card.
    phone = _css("10-responsive.css")
    actions = phone[phone.index("#entry-list > li :is(.entry-actions, .entry-meta-end) {\n    position: static;"):][:120]
    assert "margin-left: 0;" in actions
    assert "#entry-list > li .entry-meta > .entry-date {\n  margin-inline-start: auto;" in _css("08-consistency.css")


def test_the_low_score_sits_with_the_category():
    cards = _read("note-cards.js")
    assert "categoryChip ? categoryChip.after(confidenceChip) : meta.appendChild(confidenceChip)" in cards


def test_the_match_reason_folds_last_like_the_low_score():
    # INBOX 728: an icon-only "70% similar" beside a worded one read as two
    # different facts, so the reason chip gives up its words after the rest.
    cards = _read("note-cards.js")
    assert 'text.parentElement.matches(".review, .result-reason-chip")' in cards
    assert ".sort((x, y) => isLast(x) - isLast(y))" in cards
