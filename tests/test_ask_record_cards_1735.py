"""The owner (INBOX 1735): the Ask tab's Matching records cards "look messy and
unprofessional". Measured before at 390, 1024 and 1440 in dark (a seeded
notebook, `else say university`): a facts lane 24 to 52px tall with gaps of
-257 to 200px between its items, 8 elements cut at 1440, 26.4px left against
28px right padding, links one chip a row. After: one facts line 17px tall with
a 0 gap, nothing cut, 12.8px both sides, the links behind one "N links" row.
These hold the shape; the numbers come from the sweep."""

from __future__ import annotations

import re
from pathlib import Path

from tests._app_js import with_pieces
from tests import _js_scope

ROOT = Path(__file__).resolve().parent.parent
KIT = _js_scope.unwrapped((ROOT / "frontend" / "js" / "reply-kit.js").read_text(encoding="utf-8"))
LAZY_CSS = (ROOT / "frontend" / "css" / "reply-kit-lazy.css").read_text(encoding="utf-8")


def _body(name: str) -> str:
    return KIT.split(f"function {name}(", 1)[1].split("\n}\n", 1)[0]


def test_the_facts_line_holds_only_facts_that_exist_and_no_icons():
    body = _body("replyRecordCards")
    for cls in ("record-cat", "record-date", "record-score"):
        assert f'"{cls}"' in body
    assert "if (category)" in body and "if (date)" in body and 'typeof score === "number"' in body
    assert "ph:" not in body, "a bare icon says nothing alone"
    assert "old.replaceWith(line)" in body


def test_one_score_not_two():
    body = _body("replyRecordCards")
    assert body.count("record-score") == 1
    assert "% match" in body


def test_links_fold_into_one_counted_disclosure():
    body = _body("replyRecordCards")
    assert "disclosure-row" in body and "aria-expanded" in body
    assert "link${count === 1" in body
    assert 'classList.add("show-all", "hidden")' in body


def test_the_excerpt_is_two_lines_with_show_more():
    assert "--note-preview-lines: 2;" in LAZY_CSS
    body = _body("replyRecordCards")
    assert "\"Show more\"" in body and "noteClampFit.observe(body)" in body


def test_the_reason_is_one_plain_secondary_line():
    body = _body("replyRecordCards")
    assert '"record-why"' in body and "textContent = why" in body
    rule = re.search(r"\.record-why \{([^}]*)\}", LAZY_CSS)
    assert rule and "color: var(--muted);" in rule.group(1)


def test_padding_is_even_and_nothing_that_fits_is_clipped():
    rule = re.search(r":is\(#raw-results, \.records-cards\) > li\.record-card\[data-id\],\s*:is\(#raw-results, \.records-cards\) > li\.record-card\.is-numbered\[data-id\] \{([^}]*)\}", LAZY_CSS)
    assert rule and "padding-inline: var(--space-5);" in rule.group(1)
    meta = re.search(r"\.record-meta \{([^}]*)\}", LAZY_CSS).group(1)
    assert "flex-wrap: wrap;" in meta and "overflow: hidden" not in meta
    assert "text-overflow: ellipsis" not in LAZY_CSS.split("A Matching records card", 1)[1].split("Grounded in, as a source list", 1)[0]


def test_both_ask_paths_draw_the_cards():
    assert "replyRecordCards(rawList, meta.raw_results, matchInfo, scored)" in with_pieces("ask-compose.js")
    assert "replyRecordCards(rawList, turn.raw_results, matchInfo, scored)" in with_pieces("ask-history.js")


# Owner findings on the cards (mr2-1110), measured at 390 with a seeded
# "courses and study" notebook (`scratchpad/mr2-1110/own.js`): a link-only card
# at opacity 0.85 (0.65 two steps away), the title running 9 to 21px under the
# number badge on 4 of 6 cards, the "N links" row at 0px left padding, a
# link-only card with no stat at all, and no "Mentions" date on any card.
def test_every_card_has_one_brightness():
    boot = (ROOT / "frontend" / "css" / "03-dashboard-widgets.css").read_text(encoding="utf-8")
    assert not re.search(r"\.result-connected(-2hop)? \{[^}]*opacity", boot)


def test_a_title_stays_clear_of_the_number_badge_and_the_links_row_is_padded():
    badge = re.search(r"\) > li\.record-card\.is-numbered > \.entry-content \{([^}]*)\}", LAZY_CSS)
    assert badge and "padding-inline-end: calc(1.25rem + var(--space-2));" in badge.group(1)
    toggle = re.search(r"> \.record-links-toggle \{([^}]*)\}", LAZY_CSS).group(1)
    assert "padding: var(--space-1) var(--space-2);" in toggle


def test_a_link_only_card_and_a_dated_note_still_say_their_stat():
    body = _body("replyRecordCards")
    assert '"Linked"' in body and '"Two steps away"' in body, "a link-only card has a word where the percentage goes"
    assert 'old.querySelector(".chip.when")' in body and '"record-mention"' in body
    assert body.count('"record-score"') == 1


def test_a_link_only_note_never_sits_above_a_direct_match():
    from types import SimpleNamespace

    from tessellate.search.search_manager import direct_before_linked

    notes = [SimpleNamespace(id=i) for i in (12, 13, 14, 15, 16)]
    info = {13: {"type": "connected_2hop"}, 12: {"type": "connected"}, 14: {"type": "connected"}}
    out = direct_before_linked(notes, {12, 13, 14}, info)
    assert [n.id for n in out] == [15, 16, 12, 14, 13], "direct first, one step before two, each keeps its order"
