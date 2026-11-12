"""The owner: "redesign or fix the metadata, badges and links etc in the ask
subtab matching records notes column" (INBOX 510).

Measured at 1440 with `scratchpad/ui-sweeps/askcards.js` before: the card's
text 12.8px in (the Notes list's is 26.4px); the category in full ink at
500; link chips filled in the accent wash at 600, their pill 2px inside the
text edge; the match reason a filled green 600 pill on a row of its own; the
citation number a box on a plain card and invisible on the cited one. After:
26.4px, muted at 400, outlined muted pills on the text edge, the reason one
quiet fact in the facts line after the date, and one numbered box on both
grounds. The DOM is the sweep's; these hold the rules and the one line of
script that places the reason."""

from __future__ import annotations

import re
from pathlib import Path
from tests._app_js import with_pieces
from tests._css_paths import FORMER_08, sheets

ROOT = Path(__file__).resolve().parent.parent
CSS = sheets(*FORMER_08)
ASK = with_pieces("capture-ask.js")


def _rule(selector: str) -> str:
    # The last one: the rules that were 08's sit after their component's own.
    found = re.findall(re.escape(selector) + r" \{([^}]*)\}", CSS)
    assert found, selector
    return found[-1]


def test_the_reason_is_a_fact_in_the_facts_line_not_a_row_of_its_own():
    assert "placeResultBadge(row, badge);" in ASK
    assert 'meta.insertBefore(badge, meta.querySelector(":scope > .entry-date"));' in ASK
    assert "row.appendChild(badge);" not in ASK
    # The chip's quiet rules (`#raw-results .entry-meta > .result-reason-chip`)
    # went with the old facts line: `replyRecordCards` replaces that line with
    # `.record-meta` on Ask and Chat alike, so the chip is never seen styled.
    assert "#raw-results .entry-meta > .result-reason-chip" not in CSS
    # The one left is 03-dashboard-widgets.css's own gap rule.
    assert CSS.count("#raw-results .entry-meta {") == 1


def test_the_card_takes_the_notes_lists_inset_and_its_quiet_metadata():
    assert "padding-left: calc(var(--space-7) + var(--space-2));" in _rule("#raw-results > li[data-id]")
    assert "#raw-results .entry-meta.note-meta > .chip.category" not in CSS
    lazy = (ROOT / "frontend" / "css" / "reply-kit-lazy.css").read_text(encoding="utf-8")
    assert ":is(#raw-results, .records-cards) > li.record-card[data-id]" in lazy
    meta = re.search(r"\n\.record-meta \{([^}]*)\}", lazy)
    assert meta and "color: var(--muted);" in meta.group(1)


def test_chat_draws_the_same_card_as_ask():
    chat = with_pieces("chat-turn.js")
    assert 'list.className = "entry-list records-cards";' in chat
    assert "replyRecordCards(list, meta.raw_results, matchInfo, scored)" in chat


def test_links_are_the_lists_outlined_pill_on_the_text_edge_and_one_line():
    pill = _rule("#raw-results .link-connection")
    assert "border-radius: var(--radius-pill);" in pill and "border: 1px solid" in pill
    chip = _rule("#raw-results .link-connection > .chip.link")
    assert "margin: 0;" in chip and "border: 0;" in chip and "white-space: nowrap;" in chip
    assert "text-overflow: ellipsis;" in _rule("#raw-results .link-connection > .chip.link > span:last-child")
    voice = _rule("#raw-results .chip.link")
    assert "background: transparent;" in voice and "font-weight: 400;" in voice


def test_the_citation_number_has_an_edge_of_its_own_on_any_ground():
    assert "box-shadow: inset 0 0 0 1px" in _rule("#raw-results li > .record-index")
