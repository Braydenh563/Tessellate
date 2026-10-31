"""One surface per element (INBOX 1489, the owner: "faint box behind the header
of the notes page and the tab pills").

Two causes, found by measuring the Classic look's glass tokens, both a head or
a pill label drawing a second surface inside a container that already has one:

1. A sticky head painted `var(--card)` inside a `.card` that paints
   `var(--card)`. `--card` is a translucent wash, so the two stack: the Notes
   Categories head measured alpha 0.549 over 0.549 (0.797 composite), pixels
   (38, 45, 61) in the head against (35, 39, 56) in the card beside it. A
   sticky head needs a ground only while content passes under it, so it is bare
   at rest and takes an opaque ground when it is stuck
   (`@container scroll-state(stuck: ...)`, one recipe in 08-consistency.css).
2. A bare `<button>` inside a pill keeps the base `button` rule's
   `box-shadow: var(--shadow-accent-glow)` when its class resets only the
   `background`. The minimised panel's "Settings x" pill: both buttons carried
   a 25% accent glow around a transparent box.

`DESIGN.md`, "A head or a pill label never paints a surface of its own".
"""

from __future__ import annotations

import re
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
CSS = sorted((ROOT / "frontend" / "css").glob("*.css"))

#: Sticky elements that are allowed to paint the card's own ground. May only
#: shrink: a table head's sticky cells are not a box the recipe has been
#: measured on (a `container-type` on a table cell), so it keeps its composited
#: ground until it is.
FROZEN_STICKY_CARD_GROUND = {".timeline-table thead th"}

#: The sticky elements the recipe makes bare at rest (heads stick to the top,
#: the two feet to the bottom).
BARE_STICKY = {
    "#sidebar > .sidebar-head",
    ".contents-heading",
    ".timeline-bucket-head",
    ".note-edit-foot",
    "#capture .capture-commit-row",
}


def _strip(css: str) -> str:
    return re.sub(r"/\*.*?\*/", "", css, flags=re.S)


def _rules():
    for sheet in CSS:
        text = _strip(sheet.read_text(encoding="utf-8"))
        for match in re.finditer(r"([^{}]+)\{([^{}]*)\}", text):
            yield sheet.name, match.group(1).strip(), match.group(2)


#: Sticky and on `--card`, but not inside a card: the top bar is the page's own
#: chrome, so its `--card` is its only surface.
NOT_INSIDE_A_CARD = {"header#top-bar"}


def _declares_card_ground(body: str) -> bool:
    #: `var(--modal-bg, var(--card))` only falls back to it; that is not painting it.
    return bool(re.search(r"(?<![\w-])background(?:-color)?:[^;]*(?<!,\s)(?<!, )var\(--card\)", body))


def test_a_sticky_element_never_paints_the_cards_own_ground() -> None:
    found = set()
    for _sheet, selector, body in _rules():
        if "position: sticky" in body and _declares_card_ground(body):
            for part in selector.split(","):
                found.add(" ".join(part.split()))
    found -= NOT_INSIDE_A_CARD
    assert found <= FROZEN_STICKY_CARD_GROUND, (
        "a sticky head or foot paints --card inside a card that paints it; use the "
        f"stuck-ground recipe in 08-consistency.css: {sorted(found - FROZEN_STICKY_CARD_GROUND)}"
    )
    # The freeze only shrinks: a name that no longer offends is deleted from it.
    assert found >= FROZEN_STICKY_CARD_GROUND, sorted(FROZEN_STICKY_CARD_GROUND - found)


def test_the_stuck_ground_recipe_covers_every_bare_sticky_element() -> None:
    text = _strip((ROOT / "frontend" / "css" / "08-consistency.css").read_text(encoding="utf-8"))
    start = text.index("@supports (container-type: scroll-state)")
    recipe = text[start : start + 4000]
    assert "container-type: scroll-state" in recipe
    for selector in BARE_STICKY:
        assert selector in recipe, f"{selector} is not in the stuck-ground recipe"
    # A head sticks to the top, a foot to the bottom: one query asks for either.
    assert "scroll-state(stuck: top) or scroll-state(stuck: bottom)" in recipe
    # A browser without scroll-state queries keeps a ground, never a head with rows through it.
    assert "@supports not (container-type: scroll-state)" in text
    fallback = text[text.index("@supports not (container-type: scroll-state)") :][:900]
    for selector in BARE_STICKY:
        assert selector in fallback, f"{selector} has no fallback ground"
    assert "var(--card)" in fallback
    # The ground when stuck is opaque: rows pass under it.
    assert "var(--modal-bg-opaque)" in recipe


def test_a_bare_sticky_element_sets_no_ground_of_its_own() -> None:
    """Each of the five sticky rules is sticky and paints nothing of its own
    (`background: none` at most; the recipe supplies a ground only when stuck,
    and the fallback for a browser without scroll-state queries, a card one)."""
    for selector in BARE_STICKY:
        bodies = [
            body
            for _sheet, rule_selector, body in _rules()
            if "position: sticky" in body and selector in [" ".join(p.split()) for p in rule_selector.split(",")]
        ]
        assert bodies, selector
        for body in bodies:
            for value in re.findall(r"(?<![\w-])background(?:-color)?:\s*([^;]*);", body):
                assert value.strip() in {"none", "transparent"}, f"{selector}: background {value}"


def _bare_button_rules():
    """Rules for a bare button inside a pill or chip, or a toast's quiet buttons,
    that blank the background: the case where the base glow is left behind."""
    inner = re.compile(
        r"(?:[\w-]*(?:pill|chip)[\w-]*\s*(?:>\s*)?button|\.minimised-pill-(?:open|x)|\.toast-close|\.toast-action"
        r"|\.toast\s+\.toast-help)\s*$"
    )
    for sheet, selector, body in _rules():
        if not re.search(r"(?<![\w-])background(?:-color)?:\s*(?:none|transparent)\b", body):
            continue
        for part in selector.split(","):
            part = " ".join(part.split())
            if inner.search(part) and ":" not in part.split()[-1].lstrip("."):
                yield sheet, part, body


def test_a_label_inside_a_pill_that_blanks_its_ground_blanks_its_glow() -> None:
    rules = list(_bare_button_rules())
    names = {part for _s, part, _b in rules}
    # Guards the guard: the family it was written for is really matched.
    assert {".minimised-pill button", ".toast-close", ".toast-action"} <= names, sorted(names)
    for sheet, part, body in rules:
        assert re.search(r"box-shadow:\s*none", body), f"{sheet}: {part} blanks its background and keeps the base glow"


def test_the_accent_glow_is_painted_by_the_filled_button_alone() -> None:
    """`--shadow-accent-glow` is the filled button's lift. A rule outside the two
    filled grounds that applies it paints a glow around whatever it is on."""
    users = {
        " ".join(selector.split())
        for _sheet, selector, body in _rules()
        if re.search(r"box-shadow:\s*var\(--shadow-accent-glow\)", body)
    }
    assert users == {
        "button",
        ".dock > * > details.dock-menu > summary.dock-menu-primary:not(.icon-only):not(.icon-button)",
    }, sorted(users)
