"""CHAT_PLAN B2 and B7 (INBOX 2026-11-05).

B2, the owner: "the way in which all the metadata and other stuff that
appears below all ask searches, chat messages, popup agent stuff needs to be
redesigne or rearranged better ... when they stack up below it gets a little
unprofessional". One answer foot for Ask, Chat and the popup agent: a row of
chips gathered from the parts each surface already draws, each opening its
part below on demand, the stats at the row's end, actions in the head.
Measured at 1440 on one fake answer (the sweep is in the remaining file):
Ask 298 to 64px, Chat 306 to 59, the popup agent 147 to 59.

B7, the owner: "there is no vertical spacing for these agent run elements":
the activity panel's Running now rows on the card's gap tokens.
"""

from __future__ import annotations

import re
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
KIT = (ROOT / "frontend/js/answer-kit.js").read_text(encoding="utf-8")
CSS = (ROOT / "frontend/css/answer-foot-lazy.css").read_text(encoding="utf-8")
POP = (ROOT / "frontend/css/popup-anatomy-lazy.css").read_text(encoding="utf-8")


def _body(text: str, opener: str) -> str:
    """A function inside the foot's closure, indented one level."""
    start = text.index(opener)
    return text[start : text.index("\n  }\n", start)]


def test_every_part_an_answer_draws_under_it_is_a_chip_in_the_row() -> None:
    parts = KIT[KIT.index("const ANSWER_FOOT_PARTS = [") :]
    parts = parts[: parts.index("\n  ];\n")]
    found = dict(re.findall(r'key: "(\w+)",\s*find: "([^"]+)"', parts))
    assert found == {
        "sources": ".chat-sources",
        "grounding": ".grounding-fold",
        "evidence": ".answer-evidence-toggle",
        "notes": ".from-notes-fold",
        "patterns": ".insight-line",
        "related": ".answer-related",
        #: By its holders, so `renderAskWhy` stays its one builder (B30).
        "why": ".why-trail > details, #ask-why > details",
    }


def test_the_row_is_watched_on_all_three_surfaces() -> None:
    for root in (
        'answerFootWatch($("ai-answer")?.parentElement);',
        'answerFootWatch($("chat-messages"), ".msg.assistant");',
        'answerFootWatch($("command-palette-results"), ".msg.assistant");',
    ):
        assert root in KIT, root


def test_a_chip_says_what_it_opens_and_one_part_is_open_at_a_time() -> None:
    gather = _body(KIT, "function answerFootGather(scope) {")
    assert 'button.setAttribute("aria-expanded", String(on));' in gather
    assert 'button.setAttribute("aria-controls"' in gather
    assert "part.hidden = !on;" in gather
    #: The stats line joins the row's end; it is not a row of its own.
    assert 'scope.querySelectorAll(".msg-meta")' in gather
    toggle = _body(KIT, "function answerFootToggle(scope, key) {")
    assert "scope.dataset.footOpen = key" in toggle and "delete scope.dataset.footOpen" in toggle


def test_the_foot_adds_no_names_to_the_shared_scope() -> None:
    """Nothing here is called from another file, so it is one closure."""
    start = KIT.index("//: **One answer foot**")
    assert KIT[start:].count("\n(() => {\n") == 1 and KIT.rstrip().endswith("})();")


def test_the_observer_cannot_hear_itself() -> None:
    """A class written again is a mutation, so the gather only adds the part
    class when it is missing, and mutations inside the row are skipped."""
    gather = _body(KIT, "function answerFootGather(scope) {")
    assert 'if (!part.classList.contains("answer-foot-part")) part.classList.add("answer-foot-part");' in gather
    watch = _body(KIT, "function answerFootWatch(root, scopes = null) {")
    assert 'node.closest(".answer-foot-bar")) continue;' in watch


def test_the_sheet_loads_with_the_kit_that_draws_the_row() -> None:
    """answer-kit.js is in every answer bundle (Ask, its history, Chat), so it
    loads the row's sheet itself; the boot scripts are at their gzip cap."""
    watch = KIT.index('answerFootWatch($("ai-answer")?.parentElement);')
    assert 'lazyScript("/css/answer-foot-lazy.css");' in KIT[watch - 200 : watch]


def test_the_row_and_an_open_part_are_on_the_spacing_tokens() -> None:
    bar = CSS[CSS.index(".answer-foot-bar {") :]
    bar = bar[: bar.index("}")]
    assert "gap: var(--space-2) var(--space-3);" in bar
    #: A group gap above the chips, the focus ring's room given back.
    assert "padding: var(--space-1);" in bar
    assert "margin: calc(var(--space-4) - var(--space-1)) calc(var(--space-1) * -1) calc(var(--space-1) * -1);" in bar
    assert ".answer-foot-part > summary," in CSS
    assert ".answer-foot-bar ~ * :is(.answer-foot-part:not([hidden]), .answer-evidence)," in CSS


def test_the_row_is_one_row() -> None:
    """The row is one row while it fits (B2 review: Ask 54px for 4 chips at 1440).
    The owner's Windows window (INBOX 1733) showed "Mon 4:52 p" clipped: the
    stats line was a shrinking, overflow-hidden item, cut to nothing at 900 to
    1100. That intent moved: the time is never cut, so the row wraps and the
    stats line keeps its whole width, dropping to a second line at the end."""
    bar = CSS[CSS.index(".answer-foot-bar {") :]
    bar = bar[: bar.index("}")]
    assert "flex-wrap: wrap;" in bar and "flex-wrap: nowrap" not in bar
    assert ".answer-foot-bar > .answer-foot-chip {\n  flex: none;" in CSS
    meta = CSS[CSS.index(".answer-foot-bar > .msg-meta {") :]
    meta = meta[: meta.index("}")]
    assert "flex: 0 0 auto;" in meta and "overflow" not in meta and "min-width: 0" not in meta
    gather = _body(KIT, "function answerFootGather(scope) {")
    assert "kept.title = " in gather


def test_a_chip_is_made_once_and_kept() -> None:
    """The review of B2: every change while an answer streams rebuilt every
    chip, so a press whose mousedown and mouseup straddled a rebuild was lost.
    A chip is found again by its key; only a new one is made and wired."""
    gather = _body(KIT, "function answerFootGather(scope) {")
    assert "let button = had.get(spec.key);" in gather
    made = gather[gather.index("if (!button) {") : gather.index("const label = answerFootChipLabel")]
    assert 'addEventListener("click"' in made and gather.count("addEventListener") == 1
    #: The row is put together again only when its children differ.
    assert "want.every((el, index) => bar.children[index] === el)) return;" in gather


def test_a_pattern_answered_is_not_still_to_check() -> None:
    """The review of B2: after Confirm the line read "Confirmed: ..." and the
    chip still said "1 pattern to check". A line still to check carries its
    verdict pair."""
    parts = KIT[KIT.index("const ANSWER_FOOT_PARTS = [") :]
    patterns = parts[parts.index('key: "patterns"') : parts.index('key: "related"')]
    assert 'line.querySelector(".insight-verdicts")' in patterns and "to check" in patterns


def test_an_answers_actions_are_in_its_head_row() -> None:
    """B2's "actions in the head", the review: the popup agent's row floated
    over the head's corner covered the byline and the first line at 390 with
    touch on. Chat and the popup agent put the row in the name row, in its
    flow, as Ask's column head does; a question's row stays under its bubble."""
    chat = (ROOT / "frontend/js/chat-turn.js").read_text(encoding="utf-8")
    reopened = (ROOT / "frontend/js/sheets-selects.js").read_text(encoding="utf-8")
    palette = (ROOT / "frontend/js/palette.js").read_text(encoding="utf-8")
    #: The failed turn's row, and the one list the live and reopened paths share.
    assert chat.count('(bubble.querySelector(":scope > .msg-role") || bubble).appendChild(') == 2
    shared = chat[chat.index("function assistantMessageActions(") :]
    shared = shared[: shared.index("\n}\n")]
    assert shared.rstrip().endswith('return (bubble.querySelector(":scope > .msg-role") || bubble).appendChild(row);')
    for text in (chat, reopened):
        assert "appendChild(\n    assistantMessageActions(" not in text and "appendChild(assistantMessageActions(" not in text
    assert "      assistantMessageActions({\n        bubble: handles.bubble," in reopened
    assert "agentLabel.appendChild(\n    chatMessageActions([" in palette and "actionRow" not in palette
    head = CSS[CSS.index(".msg-role > .msg-actions {") :]
    head = head[: head.index("}")]
    assert "position: static;" in head and "margin-inline-start: auto;" in head
    assert ".command-palette-results > .msg.assistant > .msg-actions" not in CSS


def test_running_now_rows_are_on_the_card_gaps() -> None:
    """B7: measured 11, 0 and 6px between the model line, a job's name row,
    its fold and its bar; 8px (`--space-3`) inside a job after."""
    start = POP.index(".activity-running .pop-card-body,\n.activity-running .entry-list > li {")
    block = POP[start : POP.index(".activity-running .entry-list {", start)]
    assert "flex-direction: column;\n  gap: var(--space-3);" in block
    assert ".activity-running .pop-card-body {\n  gap: var(--space-4);" in block
    assert "margin-block: 0;" in block
