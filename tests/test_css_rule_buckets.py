"""Source text: the rule is about how stylesheets are written (which Blink bucket a selector lands in), so the CSS is read as text.

Rules that Blink tries on every element stay few (L342, L-documents-26).

A key in a 20,000 word document at 4x CPU spent 5.1 ms in style, 1.7 ms of
it in the universal bucket: rules whose rightmost compound has no id, class,
attribute or tag Blink can file them under (`tests/_css_buckets.py`). A list
`:is(.a, .b)` or `:where(.a, .b)` at the right is one of them and has a twin
that matches the same elements, with the same specificity, and is bucketed:
one selector per argument. The ones a test still reads by their text, or that
a hover/focus twin lint parses, are held at their count; the rest (`> *`,
`> :first-child`, `::selection`) have no such twin and are held too.
"""

from __future__ import annotations

from tests._css_buckets import bucketed, split_candidate, universal_selectors
from tests._css_paths import CSS_DIR

#: Universal-bucket selectors left in frontend/css after the list splits
#: (2026-11-21: 513 before, 274 of them a list `:is()`/`:where()`; 159 split).
UNIVERSAL_CAP = 375
LIST_CAP = 136


def _all() -> dict[str, list[str]]:
    return {p.name: universal_selectors(p.read_text(encoding="utf-8")) for p in sorted(CSS_DIR.glob("*.css"))}


def test_the_classifier_matches_the_selector_stats_trace():
    # Each verdict was read off Chromium's selector-stats trace (match
    # attempts on 1,000 divs, 100 of them `.k1`).
    for sel in (".k1", ":is(.k1)", ":where(.k1)", ":is(#r .k1)", ":is(.k1)::before", ":is(.k1)[class*='k']",
                "span", ":is(span):first-child", "[data-q]", ":focus", ":focus-visible", ":root", ":any-link"):
        assert bucketed(sel), sel
    for sel in (":is(.k1, .k2)", ":where(.k3, b)", ":not(.k1)", ":first-child", ".t > *", "::before",
                ":hover", ":focus-within", ":has(.k1)", "[class*='k']", ":is(.k1, .k2)[class*='k']"):
        assert not bucketed(sel), sel


def test_no_new_list_is_or_where_at_the_right():
    left = [f"{name}: {sel}" for name, sels in _all().items() for sel in sels if split_candidate(sel)]
    assert len(left) <= LIST_CAP, (
        f"{len(left)} selectors end in a list :is()/:where() (cap {LIST_CAP}); write one selector per "
        "argument, `X .a, X .b`, or `X :where(.a):is(.a, #b)` to keep a mixed list's specificity (L342)"
    )


def test_the_universal_bucket_does_not_grow():
    total = sum(len(v) for v in _all().values())
    assert total <= UNIVERSAL_CAP, f"{total} universal-bucket selectors (cap {UNIVERSAL_CAP})"
