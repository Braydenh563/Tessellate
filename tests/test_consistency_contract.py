"""The consistency contract's lints that had no test (WORLD_CLASS_PLAN section 1).

Section 1 of the plan states the vocabulary every screen follows and names a
lint for each rule. Five were never written (the 2026-09-24 read of the plan
marked them "no lint"), so a session that did not know the rule could break
it and nothing failed. They live together here because they share one shape:
read `index.html` or the stylesheets, count what breaks the rule, and either
fail on any (nothing breaks it today) or hold a ratchet at today's count
(something does, and removing it is a design judgement a lint should not
make). A ratchet is lowered in the commit that earns it and never raised.

1. **Surface budget** (1.1). No card inside a card, no panel inside a panel,
   no `.glass` inside a `.glass`, no `details > summary.btn` inside a card.
   Measured 2026-10-04: no violation in `index.html`, so it fails on any.
2. **One primary per modal** (1.2). At most one filled button in a modal
   overlay, or in one settings pane, with no allowance: the five that held
   two or three (2026-10-04) were fixed. A stage-gated pair (Run then Accept,
   Record then Save) writes the later button `ghost` and hands the fill over
   with `stagePrimary` when its stage comes (`STAGE_PAIRS`).
3. **Meta without border or hover** (1.2). A `.chip` that draws a border
   (an inset 1px shadow counts) or answers hover is a control wearing a
   chip's clothes. A chip you can press is a `.chip-interactive` (`chip()`
   with a handler: a button by role) and is styled through that class, the
   control recipe; every other rule on a `.chip` is meta. Two recipes keep an
   edge by name (`META_EDGED`), each with its reason; nothing else may.
4. **A menu item's rest background** (1.3). A row in a menu is transparent
   until pointed at. Measured: none paints one at rest.
5. **The palette carries every action** (D14). The plan's wording was "every
   `data-action` in the DOM appears in the palette"; the app has no
   `data-action` attribute, so the lint reads the two places an action is
   declared in the DOM and in code: every top-level tab button
   (`data-tab`), and every chord in `DEFAULT_SHORTCUTS`. Each needs a row in
   `paletteCommands`, bar the chords that only mean something inside one
   editing surface (`CONTEXTUAL_CHORDS`, each with its reason).

Like the other frontend lints this cannot see a rendered page; the sweeps in
`scratchpad/ui-sweeps/` do that. If one fails it has found something real:
fix the cause, never widen the rule.
"""

from __future__ import annotations

import re
from html.parser import HTMLParser
from pathlib import Path

from tests._app_js import frontend_text
from tests._css_paths import css_text

ROOT = Path(__file__).resolve().parents[1]
INDEX = ROOT / "frontend" / "index.html"

_VOID = {
    "input", "img", "br", "hr", "meta", "link", "source", "col", "area", "base",
    "embed", "track", "wbr", "path", "circle", "rect", "line", "polyline",
    "polygon", "stop",
}  # fmt: skip


def _markup() -> str:
    return re.sub(r"<!--.*?-->", "", INDEX.read_text(encoding="utf-8"), flags=re.S)


# ---------------------------------------------------------------------------
# 1. Surface budget
# ---------------------------------------------------------------------------


class _Nesting(HTMLParser):
    """Records an element whose surface class sits inside the same class."""

    SURFACES = ("card", "panel", "glass")

    def __init__(self) -> None:
        super().__init__()
        self.stack: list[dict] = []
        self.found: list[str] = []
        self.seen = dict.fromkeys(self.SURFACES, 0)

    def handle_starttag(self, tag, attrs):
        a = dict(attrs)
        classes = set((a.get("class") or "").split())
        name = a.get("id") or ".".join(sorted(classes)) or tag
        for surface in self.SURFACES:
            if surface in classes:
                self.seen[surface] += 1
                if any(surface in f["classes"] for f in self.stack):
                    self.found.append(f".{surface} inside .{surface}: {name} (line {self.getpos()[0]})")
        if (
            tag == "summary"
            and "btn" in classes
            and any(f["tag"] == "details" for f in self.stack)
            and any("card" in f["classes"] for f in self.stack)
        ):
            self.found.append(f"details > summary.btn inside a card: {name} (line {self.getpos()[0]})")
        if tag not in _VOID:
            self.stack.append({"tag": tag, "classes": classes})

    def handle_endtag(self, tag):
        for i in range(len(self.stack) - 1, -1, -1):
            if self.stack[i]["tag"] == tag:
                del self.stack[i:]
                return


def test_a_surface_is_never_inside_the_same_surface():
    parser = _Nesting()
    parser.feed(_markup())
    # The walk must be seeing the page: a parser that silently read nothing
    # would pass for ever. (No element carries the bare class `panel` today,
    # so that check is a guard for the day one does.)
    assert parser.seen["card"] > 30 and parser.seen["glass"] > 15, parser.seen
    assert not parser.found, (
        "a card inside a card, a panel inside a panel or a glass inside a glass "
        "(WORLD_CLASS_PLAN 1.1: one edge per level):\n  " + "\n  ".join(parser.found)
    )


# ---------------------------------------------------------------------------
# 2. One primary per modal
# ---------------------------------------------------------------------------

#: Classes that make a button something other than the surface's filled action.
_NOT_PRIMARY = {
    "ghost", "icon-only", "icon-button", "linklike", "doc-dock-menu-item",
    "seg-btn", "chip",
}  # fmt: skip

#: Stage-gated pairs: (unit, the first stage's button, the later one). The
#: later one is `ghost` in the markup and `stagePrimary(first, later, turn)`
#: moves the one fill between them, so a dialog never shows two.
STAGE_PAIRS = (
    ("doc-ai-panel", "doc-ai-run", "doc-ai-accept"),  # Suggest, then Replace
    ("ocr-workspace", "ocr-read-page", "ocr-to-note"),  # Read, then Save as note (INBOX 717)
    ("ocr-workspace", "ocr-to-note", "ocr-edit-save"),  # editing the reading
    ("meeting-overlay", "meeting-record", "meeting-save"),  # Record, then Save
    ("meeting-overlay", "meeting-save", "meeting-done-open"),  # then Open what was saved
    ("settings-searchindex", "embedding-apply", "embedding-error-fix"),  # a broken model
)


class _Primaries(HTMLParser):
    def __init__(self) -> None:
        super().__init__()
        self.stack: list[dict] = []
        self.units: dict[str, list[str]] = {}
        self.modals = 0

    def handle_starttag(self, tag, attrs):
        a = dict(attrs)
        classes = set((a.get("class") or "").split())
        if tag not in _VOID:
            self.stack.append({"tag": tag, "classes": classes, "id": a.get("id"), "role": a.get("role")})
        if "modal-overlay" in classes:
            self.modals += 1
        if tag != "button":
            return
        unit = None
        for depth, frame in enumerate(self.stack):
            if "modal-overlay" in frame["classes"]:
                unit = frame["id"] or ".".join(sorted(frame["classes"]))
                # The settings screen is a shell of panes, each its own
                # surface with its own one action: the unit is the pane.
                if unit == "settings-modal":
                    pane = next(
                        (
                            f["id"]
                            for f in self.stack[depth + 1 :]
                            if f["id"] and f["id"].startswith("settings-") and f["tag"] in ("section", "div", "details")
                        ),
                        None,
                    )
                    unit = pane  # None: the shell's own nav, not a pane
                break
        if not unit:
            return
        if classes & _NOT_PRIMARY or a.get("role") == "tab" or (a.get("id") or "").startswith("settings-nav-"):
            return
        if any(
            "seg" in f["classes"] or "segmented-control" in f["classes"] or f["role"] == "tablist"
            #: A glyph tab row that jumps within a pane (`pane-tabs`, INBOX 1478) is a
            #: `nav` of jump buttons, not a tablist: still navigation, never the action.
            or "tabs-line" in f["classes"]
            for f in self.stack[:-1]
        ):
            return
        self.units.setdefault(unit, []).append(a.get("id") or "(no id)")

    def handle_endtag(self, tag):
        for i in range(len(self.stack) - 1, -1, -1):
            if self.stack[i]["tag"] == tag:
                del self.stack[i:]
                return


def _primaries() -> _Primaries:
    parser = _Primaries()
    parser.feed(_markup())
    return parser


def test_a_modal_has_one_filled_button():
    parser = _primaries()
    assert parser.modals >= 10, "the walk found no modals: the lint is looking at the wrong thing"
    over = {unit: ids for unit, ids in parser.units.items() if len(ids) > 1}
    assert not over, (
        "more than one filled button in a modal (or settings pane) "
        "(WORLD_CLASS_PLAN 1.2: one primary per surface; make the others ghost, "
        "or hand the fill over with stagePrimary):\n  "
        + "\n  ".join(f"{unit}: {ids}" for unit, ids in over.items())
    )


def test_a_stage_gated_pair_hands_the_fill_over():
    """The later button of a pair is ghost in the markup, so the lint above
    sees one; the code that opens its stage must fill it, or it never is."""
    parser = _primaries()
    code = "".join(p.read_text(encoding="utf-8") for p in (ROOT / "frontend" / "js").glob("*.js"))
    assert "function stagePrimary(a, b, bTurn)" in code
    for unit, first, later in STAGE_PAIRS:
        # A chain of stages (the OCR workspace: Read, then Save as note, then
        # Save changes while editing): the markup's one filled button is the
        # head of the chain, the first that is no pair's later one.
        head = first
        while any(u == unit and b == head for u, _, b in STAGE_PAIRS):
            head = next(a for u, a, b in STAGE_PAIRS if u == unit and b == head)
        assert parser.units.get(unit) == [head], (unit, parser.units.get(unit))
        assert re.search(rf'<button id="{later}" class="ghost[ "]', _markup()), later
        assert f'stagePrimary("{first}", "{later}", ' in code, f"{later} is never filled"


# ---------------------------------------------------------------------------
# CSS reading, shared by 3 and 4
# ---------------------------------------------------------------------------


def _rules() -> list[tuple[str, str]]:
    """(selector, body) for every innermost rule, comments stripped."""
    text = re.sub(r"/\*.*?\*/", "", css_text(), flags=re.S)
    return [(sel.strip(), body) for sel, body in re.findall(r"([^{}]+)\{([^{}]*)\}", text)]


def _split_top_level(selector: str, separators: str) -> list[str]:
    """Split on commas or combinators that are not inside parentheses."""
    parts: list[str] = []
    depth = 0
    current = ""
    for char in selector:
        if char == "(":
            depth += 1
        elif char == ")":
            depth -= 1
        if depth == 0 and char in separators:
            if current.strip():
                parts.append(current.strip())
            current = ""
            continue
        current += char
    if current.strip():
        parts.append(current.strip())
    return parts


def _subjects(selector: str) -> list[str]:
    """The last compound of each comma-separated selector: the element the
    rule actually styles (`.card .chip:hover` styles a `.chip`)."""
    out = []
    for one in _split_top_level(selector, ","):
        compounds = _split_top_level(one, " >+~\n\t")
        if compounds:
            out.append(compounds[-1])
    return out


# ---------------------------------------------------------------------------
# 3. Meta: no border, no hover
# ---------------------------------------------------------------------------

_META = re.compile(r"(?<![\w-])\.(?:chip|meta)(?![\w-])")
#: A width or style on the shorthand, or a width/style longhand. A colour or
#: radius alone draws nothing, and `border: 0` or `none` is the recipe.
_BORDER_DRAWN = re.compile(
    r"(?<![\w-])border(?:-(?:top|right|bottom|left|inline|block)(?:-(?:start|end))?)?(?:-(?:width|style))?"
    r"\s*:\s*(?!\s*(?:0|none|transparent|inherit|initial|unset)\b)([^;]+)"
    r"|box-shadow\s*:[^;]*\binset\s+0\s+0\s+0\s+1px"
)  # fmt: skip

#: The two chip recipes that keep an edge, by DESIGN.md's own decision. Not a
#: ratchet: a third needs its row in DESIGN.md first.
META_EDGED = {
    # The status label (`.chip.item-label`) kept an edge here until INBOX 553
    # (c), 2026-10-05: it is a tinted pill without one now, so the lint holds
    # it like every other fact.
    # A suggested tag (INBOX 440) is two buttons in one box, take and
    # discard: the box is the group's edge, as `.link-connection` is a link's.
    ".chip.suggested-tag",
}


def _meta_violations() -> list[str]:
    found: set[str] = set()
    for selector, body in _rules():
        for subject in _subjects(selector):
            if not _META.search(subject) or ".chip-interactive" in subject:
                continue
            if any(subject.startswith(name) for name in META_EDGED):
                continue
            if ":hover" in subject:
                found.add(f"hover: {subject}")
            # A pseudo-element draws its own thing (the dot before a category).
            if "::" in subject or re.search(r":(?:before|after)\b", subject):
                continue
            if _BORDER_DRAWN.search(body):
                found.add(f"border: {subject}")
    return sorted(found)


def test_meta_chips_do_not_draw_borders_or_answer_hover():
    # The walk must be seeing the chips: a selector that matched nothing
    # would pass for ever.
    seen = sum(1 for selector, _ in _rules() for subject in _subjects(selector) if _META.search(subject))
    assert seen > 50, f"the meta selector matched {seen} rules: the lint is looking at the wrong thing"
    found = _meta_violations()
    assert not found, (
        "a chip rule draws a border or answers hover (WORLD_CLASS_PLAN 1.2: meta has no "
        "border, no hover; a chip you can press is a .chip-interactive, styled as one):\n  "
        + "\n  ".join(found)
    )


def test_the_edged_chips_are_still_drawn_with_an_edge():
    """An exception for a recipe that lost its edge is a hole for the next one."""
    edged = {
        name
        for selector, body in _rules()
        for subject in _subjects(selector)
        for name in META_EDGED
        if subject.startswith(name) and ":hover" not in subject and _BORDER_DRAWN.search(body)
    }
    assert edged == META_EDGED, f"drop from META_EDGED: {META_EDGED - edged}"


# ---------------------------------------------------------------------------
# 4. A menu item's rest background
# ---------------------------------------------------------------------------

_MENU_ITEM = re.compile(
    r"(?<![\w-])\.(?:menu-item|doc-dock-menu-item|wb-menu-item|library-image-menu-item|action-menu-item)(?![\w-])"
)
#: Anything that is not the item at rest: pointed at, focused, chosen, off.
_NOT_REST = re.compile(
    r":(?:hover|focus|focus-visible|focus-within|active|disabled|checked|not|has)\b"
    r"|\[|\.(?:active|selected|current|open|on|is-[\w-]+)\b"
)
_TRANSPARENT = re.compile(
    r"^\s*(?:none|transparent|inherit|unset|initial|revert|rgba?\(\s*0\s*,\s*0\s*,\s*0\s*,\s*0\s*\))\s*(?:!important)?\s*$"
)


def _menu_rest_backgrounds() -> tuple[int, list[str]]:
    rows = 0
    found: list[str] = []
    for selector, body in _rules():
        for one in _split_top_level(selector, ","):
            subjects = _split_top_level(one, " >+~\n\t")
            if not subjects or not _MENU_ITEM.search(subjects[-1]):
                continue
            rows += 1
            if _NOT_REST.search(one):
                continue
            for value in re.findall(r"(?<![\w-])background(?:-color)?\s*:\s*([^;]+)", body):
                if not _TRANSPARENT.match(value):
                    found.append(f"{one.strip()[:80]} -> background: {value.strip()}")
    return rows, found


def test_a_menu_item_is_transparent_at_rest():
    rows, found = _menu_rest_backgrounds()
    assert rows > 20, "no menu-item rules matched: the lint is looking at the wrong thing"
    assert not found, (
        "a menu row paints a background before it is pointed at "
        "(WORLD_CLASS_PLAN 1.3: ghost, no rest fill; hover and selected carry the tint):\n  "
        + "\n  ".join(found)
    )


# ---------------------------------------------------------------------------
# 5. The palette carries every action
# ---------------------------------------------------------------------------

#: Chords that only mean something inside one editing surface or one running
#: thing, so a palette row (which runs from anywhere) would do nothing or
#: the wrong thing. Anything else must be in the palette.
CONTEXTUAL_CHORDS = {
    "palette": "the palette itself",
    "findAnything": "the other palette; Find anything lists the same commands",
    "search": "focuses the search box of the tab you are on",
    "undo": "acts on the last change of the surface in front",
    "redo": "acts on the last undone change of the surface in front",
    "save": "saves whichever editor has focus",
    "selectionActions": "needs a text selection",
    "editorMenu": "needs a focused editing surface",
    "inlineAi": "needs a focused textarea",
    "stopAI": "only means something while an answer is streaming",
    "agentMode": "a switch on the Chat tab",
    "attachNote": "clips the note in front to the next question",
    "whiteboard": "opens the Boards sub-tab; Go to Library and New whiteboard board are its palette doors",
}


def _palette_source() -> str:
    text = frontend_text("settings-panes.js")
    start = text.index("function paletteCommands(")
    return text[start : text.index("\n}\n", start)]


def test_every_tab_button_has_a_go_to_row_in_the_palette():
    tabs = re.findall(r'data-tab="([a-z-]+)"', _markup())
    assert len(tabs) >= 7, tabs
    source = _palette_source()
    missing = [tab for tab in tabs if not re.search(rf'\btab:\s*"{tab}"', source)]
    assert not missing, f"tabs with no 'Go to' row in paletteCommands: {missing}"


def test_every_shortcut_is_in_the_palette_or_says_why_not():
    table = frontend_text("settings-wiring.js")
    block = table[table.index("const DEFAULT_SHORTCUTS = {") :]
    block = block[: block.index("\n};\n")]
    chords = re.findall(r"^  (\w+): \{ keys: ", block, flags=re.M)
    assert len(chords) >= 25, chords
    in_palette = set(re.findall(r'\bchord:\s*"(\w+)"', _palette_source()))
    missing = [c for c in chords if c not in in_palette and c not in CONTEXTUAL_CHORDS]
    assert not missing, (
        f"shortcuts with no palette row (add one with `chord: \"id\"`, or name why it "
        f"cannot be a command in CONTEXTUAL_CHORDS): {missing}"
    )
    stale = [c for c in CONTEXTUAL_CHORDS if c not in chords]
    assert not stale, f"CONTEXTUAL_CHORDS names a shortcut that no longer exists: {stale}"
    both = [c for c in CONTEXTUAL_CHORDS if c in in_palette]
    assert not both, f"in the palette now, so no longer contextual: {both}"
