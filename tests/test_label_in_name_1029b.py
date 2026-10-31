"""Audit 1029 rank 47: a control's accessible name starts with, or at least
contains, the words drawn on it (WCAG 2.5.3, axe `label-content-name-mismatch`).

Measured with axe 4 on the 77-note showcase notebook at 390 and 1440:

- the timeline's seven day buttons: two spans, "Fri" and "23", read to the
  checker as "Fri23" while the name says "Fri 23, ...";
- the Manage categories rows and the tags sheet rows: the name span and the
  count button ran together ("Cooking10") against "Cooking, 10 notes";
- the Reminders tab and the phone More button once a badge shows: "Reminders3"
  and "More3" against names with a space or none;
- the Tidy button past 99: it draws "99+" and said "Tidy, 150 to look at";
- the Statistics range select: its opener took the whole `<label>` text,
  options included, as its name;
- the welcome's Skip button: an `aria-label` that was the long tooltip over
  the visible word "Skip".

A leading or trailing space in a flex item is collapsed when drawn, so it costs
nothing to look at and is what lets the two words be told apart.
"""

from __future__ import annotations

import re
from pathlib import Path

JS = Path(__file__).resolve().parents[1] / "frontend" / "js"


def _read(name: str) -> str:
    return (JS / name).read_text(encoding="utf-8")


def _body(text: str, start: str, end: str = "\n}\n") -> str:
    return text.split(start, 1)[1].split(end, 1)[0]


def test_a_timeline_day_name_ends_in_a_space_so_it_reads_apart_from_the_number() -> None:
    text = _read("timeline.js")
    assert re.search(r'name\.textContent = `\$\{day\.toLocaleDateString\(undefined, \{ weekday: "short" \}\)\} `;', text)


def test_a_category_or_tag_row_name_is_read_apart_from_its_count() -> None:
    assert "name.textContent = `${meta.name} `;" in _read("categories-panel.js")
    assert "label.textContent = `${name} `;" in _read("tag-manager.js")


def test_the_reminders_badge_and_the_more_badge_are_read_apart_from_the_word() -> None:
    assert "badge.textContent = ` ${due}`;" in _read("shell-reminders.js")
    more = _body(_read("phone-shell.js"), "function syncPhoneMoreRuns()")
    assert "badge.textContent = ` ${shown}`;" in more
    assert 'more.setAttribute("aria-label", `More: ${words}`)' in more, "the runs case names its count too"


def test_the_tidy_button_names_the_count_it_draws() -> None:
    text = _body(_read("tidy.js"), "const count = $(\"notes-tidy-count\");")
    assert "`Tidy, ${count.textContent} ${body.total === 1 ? \"thing\" : \"things\"} to look at`" in text, "99+ is drawn, so 99+ is said"
    assert "${body.total} to look at" not in text.split("button.title", 1)[0]


def test_the_welcome_skip_button_is_named_by_its_own_words() -> None:
    text = _body(_read("onboarding.js"), 'const skip = $("onboarding-skip");')
    assert "aria-label" not in text, "its title is the tooltip; the words name the button"
    assert "skip.title = last" in text


def test_a_select_wrapped_in_its_label_is_named_by_the_label_alone() -> None:
    text = _body(_read("sheets-selects.js"), "function enhanceSelect(select)", "\n}\n")
    assert 'select.labels?.[0]' in text
    assert 'querySelectorAll("select, .select-shell")' in text, "the options are not the label's words"



def test_the_offer_again_button_name_starts_with_its_words() -> None:
    assert 'again.setAttribute("aria-label", `Offer again: ${tag}`)' in _read("tag-manager.js")
