"""INBOX 1575, a31c: the companion's placement after a tab switch (the lag log's `avatars.js go`,
`TimerHandler:setTimeout` 749 ms, forced layout 500 ms).

Reproduced at 4x CPU on a 2,000-note notebook with the companion on (a click through nine tabs):
`nameMarkBuddyNextSpot` 22.3 s in all (Library 7.3 s, Timeline 3.7 to 4.8 s), 1,010 to 1,412
`elementsFromPoint` calls a switch, one `nameMarkBuddyWordsUnder` on the Dashboard 2.2 s. Each cause
is pinned here by the shape that fixed it. The new names are members of `nmb` (the global-names
ratchet: tests/test_global_scope_ratchet.py).
"""

from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
AV = (ROOT / "frontend" / "js" / "avatars.js").read_text(encoding="utf-8")


def _body(source: str, head: str) -> str:
    start = source.index(head)
    depth = 0
    for i in range(source.index("{", start), len(source)):
        depth += source[i] == "{"
        depth -= source[i] == "}"
        if depth == 0:
            return source[start : i + 1]
    raise AssertionError(head)


def _fn(name: str) -> str:
    return _body(AV, f"function {name}(")


UNDER = _body(AV, "  under(px, py) {")
ROOT_WORDS = _body(AV, "  rootWords(root) {")


def test_a_hit_test_asks_for_the_top_element_not_the_whole_stack() -> None:
    assert UNDER.index("document.elementFromPoint(px, py)") < UNDER.index("document.elementsFromPoint(px, py)")
    assert 'closest("#nm-buddy")' in UNDER, "the stack is asked for only when the hit is the companion"
    # The two placement paths use it; the stack call is not made anywhere in the choice.
    assert "nmb.under(px, py)" in _fn("nameMarkBuddyCoverPoint")
    assert "nmb.under(px, py)" in _fn("nameMarkBuddyWordsUnder")
    assert "elementsFromPoint" not in _fn("nameMarkBuddyCoverPoint") + _fn("nameMarkBuddyWordsUnder")


def test_the_sampled_share_stops_at_three_covered_points() -> None:
    covers = _fn("nameMarkBuddyCovers")
    assert "coverStop: 3" in AV
    assert covers.count("if (covered >= nmb.budget.coverStop) break;") == 2, "after a fresh hit test and after a cached one"


def test_the_search_has_a_budget_the_same_on_every_machine() -> None:
    choose = _fn("nameMarkBuddyChoose")
    assert "budget: { ms: 250, hits: 360, fitMs: 120, fitHits: 160," in AV
    assert "if (!nmb.fitting) {" in choose and "nmb.budget.left = nmb.budget.hits;" in choose
    assert "if (scored > 0 && (nmb.budget.left <= 0 || performance.now() > nmb.budget.until)) break;" in choose
    # The retry at the smaller size has its own, smaller, budget; it is set before the recursion.
    assert choose.index("nmb.budget.left = nmb.budget.fitHits;") < choose.index("small = nameMarkBuddyChoose(")
    # The budget is spent by hit tests and by a measured block (twenty of them).
    assert "nmb.budget.left -= 1;" in _fn("nameMarkBuddyCoverPoint")
    assert "nmb.budget.left -= 20;" in _fn("nameMarkBuddyWordsUnder")


def test_a_block_is_walked_once_a_placement() -> None:
    assert "nmb.wordsCache?.get(root)" in ROOT_WORDS and "nmb.wordsCache?.set(root, rects)" in ROOT_WORDS
    choose = _fn("nameMarkBuddyChoose")
    assert "nmb.wordsCache = new Map();" in choose
    assert choose.index("nmb.wordsCache = new Map();") < choose.index("queueMicrotask(() => {"), "dropped when the stack unwinds"
    assert "nmb.wordsCache = null;" in choose[choose.index("queueMicrotask(() => {") :]


def test_the_words_walk_counts_elements_and_passes_drawings() -> None:
    assert "wordsEl: 1500" in AV
    assert "looked > nmb.budget.wordsEl || nmb.budget.noWords.test(node.localName)" in ROOT_WORDS
    assert ROOT_WORDS.index("nmb.budget.noWords.test(node.localName)") < ROOT_WORDS.index("node.checkVisibility()"), "a drawing is passed before the visibility check"
    assert "looked <= nmb.budget.wordsEl" in ROOT_WORDS
