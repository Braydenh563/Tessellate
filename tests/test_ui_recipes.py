"""New UI goes through DESIGN.md's recipe index, and drift is a ratchet.

The owner: "all the ui issues and stuff with popup menus, ui not matching
and more happen when new features are added or changed because you don't
follow design.md". Two things a diff cannot show and a review misses:

1. A glass surface that is not on the `[data-glass="off"]` list stays
   glassy with the setting off, and blurs at a radius of its own. Every
   selector that declares a backdrop-filter must be on that list or in the
   families DESIGN.md names.
2. A menu built by hand instead of `kebabMenu()` positions itself, clamps
   itself and closes itself differently from every other menu in the app,
   and that is where "the menu is crushed" reports come from. The count of
   hand-built `role="menu"` elements per file may only fall.

Both are ratchets: the known drift is frozen here so the lint starts green;
a fix removes an entry, a new offender fails the build.
"""

from __future__ import annotations

import re
from html.parser import HTMLParser
from pathlib import Path
from tests._app_js import app_js_family, app_js_text, frontend_text, with_pieces

ROOT = Path(__file__).resolve().parent.parent
CSS = sorted((ROOT / "frontend" / "css").glob("*.css"))
JS = sorted((ROOT / "frontend" / "js").glob("*.js"))

# The families DESIGN.md names as glass on purpose; anything else must be on
# the glass-off list by its own name.
GLASS_FAMILIES = {
    ".card", ".glass", "header#top-bar", "#top-bar", ".modal-card", ".space-dialog",
    ".dock-menu", ".action-menu", ".select-menu", ".help-body",
    ".toast", ".command-palette-card", ".scroll-top", ".notes-subtabs", ".library-subtabs",
    ".contents-heading", ".graph-zoom", ".sidebar-panel",
}

# Selectors that blurred before this lint existed and are not yet on the
# list. May only shrink: fix one by adding it to the `[data-glass="off"]`
# list in 03-dashboard-widgets.css (or by removing its blur) and delete it
# here. Never add to it.
KNOWN_GLASS_DRIFT = set()


def _rules(css: str):
    css = re.sub(r"/\*.*?\*/", "", css, flags=re.S)
    for match in re.finditer(r"([^{}]+)\{([^{}]*)\}", css):
        yield match.group(1).strip(), match.group(2)


def _glass_off_names() -> set[str]:
    css = (ROOT / "frontend" / "css" / "03-dashboard-widgets.css").read_text(encoding="utf-8")
    names = set()
    for selector, body in _rules(css):
        if 'data-glass="off"' in selector and "backdrop-filter: none" in body:
            for part in selector.split(","):
                part = part.strip()
                tail = part.split("]")[-1].strip()
                if tail:
                    names.add(tail.split()[0].split(":")[0])
    return names


def _leading_name(selector: str) -> str:
    selector = selector.strip()
    if selector.startswith("@"):
        return ""
    token = re.split(r"[\s>+~:\[]", selector, maxsplit=1)[0]
    return token or selector


def test_every_blurred_surface_is_on_the_glass_off_list_or_in_a_named_family() -> None:
    allowed = _glass_off_names() | GLASS_FAMILIES | KNOWN_GLASS_DRIFT
    offenders = []
    for path in CSS:
        for selector, body in _rules(path.read_text(encoding="utf-8")):
            if "backdrop-filter:" not in body or "backdrop-filter: none" in body:
                continue
            for part in selector.split(","):
                name = _leading_name(part)
                if not name or name.startswith("@") or name.startswith(":root"):
                    continue
                full = part.strip()
                if any(fam in full for fam in GLASS_FAMILIES):
                    continue
                if name in allowed or any(n in full for n in allowed):
                    continue
                offenders.append(f"{path.name}: {full}")
    assert offenders == [], (
        "a blurred surface that is not on the [data-glass=off] list (DESIGN.md, "
        "Turning it off) or in a named family: " + "; ".join(sorted(set(offenders)))
    )


# Hand-built menus per file, frozen. `kebabMenu()` in app.js is the recipe;
# the two canvases draw their own because they float over a canvas that has
# no DOM under the pointer.
HAND_BUILT_MENUS = {"app.js": 4, "graph-canvas.js": 1, "whiteboard.js": 1}


def test_hand_built_menus_do_not_multiply() -> None:
    counts = {}
    for path in JS:
        n = path.read_text(encoding="utf-8").count('setAttribute("role", "menu")')
        if n:
            #: The pieces of the old app.js count as app.js (tests/_app_js.py):
            #: a menu moving between them is not a new menu.
            name = "app.js" if app_js_family(path) else path.name
            counts[name] = counts.get(name, 0) + n
    for name, n in counts.items():
        assert n <= HAND_BUILT_MENUS.get(name, 0), (
            f"{name} builds {n} menus by hand; the recipe is kebabMenu(items, label) "
            "in app.js (DESIGN.md, the recipe index)"
        )


#: Past this many rows a menu is a list you have to read rather than a set of
#: choices you can see, and DESIGN.md's recipe says it is grouped. Five is
#: where the app's own menus sit: measured on the branch head, the ones that
#: are not grouped are all four rows or fewer, and the one that was ten
#: (the table cell's) is the case that asked for the rule.
MENU_GROUP_CEILING = 5


def test_a_long_kebab_menu_is_grouped() -> None:
    """Ten undifferentiated rows is a list, not a menu.

    The table cell's menu covered rows, columns, alignment and the whole
    table in one run of ten, and finding "Align centre" in it meant already
    knowing the order. `kebabMenu` draws a hairline wherever an item's `group`
    changes; this is the ratchet that a command table long enough to need that
    actually declares it.

    Counted on the *table* rather than on the rendered menu, because the menu
    exists only in a browser and this suite cannot see the DOM. A command list
    is a JavaScript array literal of objects each carrying `id:`, which is a
    shape this file can count without running anything.
    """
    docs = (ROOT / "frontend" / "js" / "documents.js").read_text(encoding="utf-8")
    table = docs[docs.index("const DOC_TABLE_COMMANDS = ["):]
    table = table[: table.index("\n];")]
    rows = re.findall(r'^\s{2}\{\n\s+id: "([a-z-]+)",\n\s+group: "([a-z]+)",', table, re.M)
    ids = re.findall(r'^\s+id: "([a-z-]+)",$', table, re.M)
    assert len(ids) > MENU_GROUP_CEILING, (
        "this ratchet is about a menu past the ceiling; the table cell's menu "
        f"is now {len(ids)} rows, so either it shrank or the shape it is "
        "counted by changed"
    )
    assert len(rows) == len(ids), (
        f"{len(ids) - len(rows)} of the table cell menu's {len(ids)} commands "
        "carry no `group`, so kebabMenu draws them as one undifferentiated "
        "list (DESIGN.md, the recipe index: a menu past five rows is grouped)"
    )
    assert len(set(g for _, g in rows)) > 1, "one group over the whole menu groups nothing"
    #: And the recipe has to be able to draw it, which is two lines away in
    #: another file: the separator element and the stylesheet rule for it.
    app = app_js_text()
    assert 'rule.className = "menu-sep"' in app and 'role", "separator"' in app, (
        "kebabMenu no longer draws a separator between groups"
    )
    css = (ROOT / "frontend" / "css" / "02-chat-graph.css").read_text(encoding="utf-8")
    assert ".action-menu > .menu-sep" in css, (
        "the separator has no rule, so a grouped menu draws a zero-height gap"
    )


def test_a_pointer_anchored_menu_is_the_recipe() -> None:
    """A right-click or long-press menu is `openMenuAtPoint`, not a new shape.

    DESIGN.md's recipe index gains a row with the link context menu (INBOX
    182). The failure it guards against is the one the kebab ratchet above
    guards against one step earlier: a second surface that wants a menu where
    the pointer is, writing its own host, its own clamp and its own closing
    rule. The recipe lives in app.js and every `.pointer-menu-host` in the
    frontend comes from it.
    """
    app = app_js_text()
    assert "function openMenuAtPoint(" in app, (
        "the pointer-anchored menu recipe has gone from app.js; DESIGN.md's "
        "recipe index still points at openMenuAtPoint"
    )
    builders: dict[str, int] = {}
    for path in JS:
        name = "app.js" if app_js_family(path) else path.name
        n = path.read_text(encoding="utf-8").count('className = "pointer-menu-host"')
        builders[name] = builders.get(name, 0) + n
    offenders = {name: n for name, n in builders.items() if n and name != "app.js"}
    assert not offenders, (
        f"{offenders} build a pointer-menu host of their own; the recipe is "
        "openMenuAtPoint(items, ariaLabel, x, y) in app.js (DESIGN.md, the recipe index)"
    )
    assert builders.get("app.js", 0) == 1, (
        f"app.js builds {builders.get('app.js', 0)} pointer-menu hosts; one recipe, one host"
    )


# A sheet is `openSheet()` in app.js (DESIGN.md, "A sheet"). Two predate the
# recipe and are frozen here with their reason: the three sidebars become edge
# sheets below 600 (`.sidebar-sheet-open`) and the graph's dock becomes
# `.graph-popup-sheet`. Each of those brought its own scrim, its own closing
# behaviour and its own bottom inset, which is exactly the drift the recipe
# ends, so the list may shrink and never grow.
HAND_BUILT_SHEETS = {"sidebar-sheet-open", "graph-popup-sheet"}

# The recipe's own classes, including the two a `variant` produces: `openSheet`
# takes one word and stamps `sheet-<word>` on the overlay and
# `sheet-card-<word>` on the card, which is how a sheet that has to sit
# somewhere else (Atlas, in the corner, INBOX 224) stays the one recipe rather
# than becoming a third hand-built sheet. A new variant adds its two names here
# and nothing else; the test below is what keeps that true.
SHEET_RECIPE = {
    # The Guide above 600: no scrim, presses pass through (openSheet `modal: false`).
    "sheet-modeless",
    "sheet-overlay",
    "sheet-card",
    "sheet-head",
    "sheet-title",
    # The one line of state under a title (openSheet's `sub`).
    "sheet-sub",
    "sheet-close",
    "sheet-list",
    "sheet-row",
    "sheet-corner",
    "sheet-card-corner",
    # The note page (UI Phase 11 item 2): full height, a back chevron.
    "sheet-page",
    "sheet-card-page",
    # The way out: `openSheet`'s close adds it for --motion-fast, then removes
    # the overlay (no exit under reduced motion).
    "sheet-leaving",
}


def test_only_the_recipe_stamps_a_sheet_variant() -> None:
    """A variant class may only ever be written by `openSheet`.

    Otherwise the variant is the loophole: any file could paint `sheet-corner`
    onto a div of its own and inherit none of the scrim, the tier, the head
    with its X, Escape or the backdrop press.
    """
    for path in JS:
        js = path.read_text(encoding="utf-8")
        for match in re.findall(r'"sheet-(?:card-)?[a-z]+"', js):
            #: "app.js" is the app's code, every piece of it (tests/_app_js.py).
            assert app_js_family(path), f"{path.name} writes {match} by hand"
    app = app_js_text()
    assert app.count("sheet-${variant}") == 1
    assert app.count("sheet-card-${variant}") == 1


def test_a_sheet_is_the_recipe_or_one_of_the_two_that_predate_it() -> None:
    found = set()
    for path in CSS:
        css = re.sub(r"/\*.*?\*/", "", path.read_text(encoding="utf-8"), flags=re.S)
        for name in re.findall(r"\.([A-Za-z0-9_-]*sheet[A-Za-z0-9_-]*)", css):
            found.add(name)
    unknown = sorted(found - SHEET_RECIPE - HAND_BUILT_SHEETS)
    assert unknown == [], (
        "a sheet built by hand rather than through `openSheet` (DESIGN.md, "
        '"A sheet"): ' + ", ".join(unknown)
    )


def test_the_sheet_recipe_keeps_its_dialog_semantics_and_its_bottom_inset() -> None:
    """The two halves a hand-built sheet has always got wrong.

    A sheet that is not a modal dialog is a panel a screen reader walks past;
    a sheet with no bottom inset puts its last row under the home indicator on
    every phone with one, which is the only surface in the app that cannot be
    checked in this sandbox at all.
    """
    app = app_js_text()
    opener = app[app.index("function openSheet("):]
    opener = opener[: opener.index("\n}\n")]
    for needed in ('"role", "dialog"', '"aria-modal", "true"', '"Escape"', "wireBackdropClose"):
        assert needed in opener, f"openSheet no longer carries {needed}"

    card = ""
    for path in CSS:
        for selector, body in _rules(path.read_text(encoding="utf-8")):
            if selector.strip() == ".sheet-card":
                card = body
    assert "env(safe-area-inset-bottom" in card, (
        "the sheet's own rule no longer pads its foot with the bottom safe-area inset"
    )


def test_the_corner_sheet_variant_floats_rather_than_leaning_on_an_edge() -> None:
    """The half a corner panel gets wrong (INBOX 270).

    `sheet-corner` is the one variant that is deliberately not an edge sheet:
    above the phone break it hovers in the corner over the app. It inherits
    `.sheet-card`'s bottom-sheet geometry, though, and inheriting it silently
    is how it came to sit 10px from the right of the window and 0px from the
    bottom with two square corners against an edge it was not touching. So the
    floating block has to keep saying all three things: one radius for all four
    corners, the same inset on both edges, and a foot padded like a card rather
    than like a row under a home indicator.
    """
    css = (ROOT / "frontend" / "css" / "08-consistency.css").read_text(encoding="utf-8")
    bodies = [
        body
        for selector, body in _rules(css)
        if selector.strip() == ".sheet-card.sheet-card-corner"
    ]
    assert bodies, "the corner sheet variant has no rule of its own"
    whole = "\n".join(bodies)
    radius = re.findall(r"border-radius:\s*([^;]+);", whole)
    assert radius, "the corner panel no longer states a radius of its own"
    for value in radius:
        assert len(value.split()) == 1, (
            "the corner panel is back to a two-corner radius, which is an edge "
            f"sheet's shape and not a floating panel's: {value.strip()}"
        )
    inline = re.search(r"margin-inline-end:\s*([^;]+);", whole)
    block = re.search(r"margin-block-end:\s*([^;]+);", whole)
    assert inline and block, "the corner panel is leaning on the window's edge again"
    assert inline.group(1).strip() == block.group(1).strip(), (
        "a floating panel has one inset, not one per edge: "
        f"{inline.group(1).strip()} against {block.group(1).strip()}"
    )
    assert "padding-bottom" in whole, (
        "the corner panel kept `.sheet-card`'s safe-area foot, which is an edge "
        "sheet's inset and leaves this one's composer closer to the bottom of "
        "the card than its head is to the top"
    )


# And the two that predate the recipe keep its dismissal even though they do not
# keep its construction (DESIGN.md, "A sheet"): an in-place sheet goes through
# `wireInPlaceSheetDismissal`, so Escape is captured, a press outside closes it
# and focus lands back on the opener. Those three are the half a hand-built
# sheet has always got wrong, and the half that can be shared without moving a
# live subtree in and out of a dialog.
def test_an_in_place_sheet_shares_the_recipe_dismissal() -> None:
    app = app_js_text()
    start = app.index("function wireInPlaceSheetDismissal(")
    body = app[start : app.index("\n}\n", start)]
    for needed in ('"keydown"', '"pointerdown"', "true)", "stopPropagation"):
        assert needed in body, f"wireInPlaceSheetDismissal no longer carries {needed}"
    assert "wireInPlaceSheetDismissal({" in app[app.index("function initSidebarSheetDismissal(") :], (
        "the sidebar sheet has gone back to its own dismissal"
    )


# A fixed set of filter toggles is one well (DESIGN.md, "Two to four toggles
# that belong to one question"), not a row of chips. INBOX 186 is what a row of
# chips looks like once there are four of them at four widths: measured at 820,
# four lines and a 181.2px dock. `.dock-chip-row` was that shape's class and now
# has no user in the page; the count may only stay at zero.
def test_a_fixed_filter_set_is_one_well_rather_than_a_row_of_chips() -> None:
    page = re.sub(
        r"<!--.*?-->", "", (ROOT / "frontend" / "index.html").read_text(encoding="utf-8"), flags=re.S
    )
    assert "dock-chip-row" not in page, (
        "a row of filter chips is back in the page: a filter set that is always "
        "all of its members is `.seg.seg-multi` (DESIGN.md's recipe index), and "
        "a chip is only for a filter you can take off"
    )

    css = "\n".join(path.read_text(encoding="utf-8") for path in CSS)
    bodies = [body for selector, body in _rules(css) if ".seg-multi" in selector]
    assert bodies, ".seg-multi is in DESIGN.md's index but not in the stylesheet"
    # The one property that separates it from `.seg`, and the whole reason the
    # variant exists: `.seg` wraps, and a well in a dock row that wraps is the
    # four-line chip row this replaced.
    assert any("flex-wrap: nowrap" in body for body in bodies), (
        ".seg-multi must declare `flex-wrap: nowrap`: `.seg` itself wraps, and a "
        "wrapping well in a dock row is the shape INBOX 186 reported"
    )


# And the other half of the same recipe, which is behaviour rather than paint:
# a toggle set says which of its members are on. It said so with `aria-pressed`
# per segment while it was a well; since INBOX 214 it is a dock menu of checkbox
# rows, where the state is the checkbox's own and the browser announces it, and
# the caption on the closed button is what says it when the menu is shut.
def test_a_multi_toggle_filter_set_says_which_of_its_members_are_on() -> None:
    #: timeline.js since the Timeline tab was split out of app.js.
    app = (ROOT / "frontend" / "js" / "timeline.js").read_text(encoding="utf-8")
    start = app.index("function renderTimelineKinds(")
    body = app[start : app.index("\n}\n", start)]
    assert 'type = "checkbox"' in body, (
        "renderTimelineKinds builds the rows of a dock menu and each carries a "
        "real checkbox: the state is the control's own, not a class"
    )
    assert "doc-dock-menu-check" in body, (
        "a switch row in a dock menu is `.doc-dock-menu-check`, which is what "
        "keeps the menu open while it is pressed: a menu that shuts on the "
        "click hides the only feedback a switch gives"
    )
    assert "syncTimelineKindsLabel(" in body, (
        "the closed button is the only thing that says what the filter is set "
        "to, so building the rows has to write the caption too"
    )
    #: `change`, not `click`: the checkbox is inside its own <label>, so a press
    #: on the words fires a click on both and a click handler toggles twice.
    handler = app[app.index('$("timeline-kinds")?.addEventListener') :][:200]
    assert handler.startswith('$("timeline-kinds")?.addEventListener("change"'), handler[:80]


# A filter set whose members can outgrow the row it sits in is a dropdown, not
# a well (INBOX 214, the owner: "they clash with the ui at large zoom and they
# dont fit visually"). This is the ratchet on the shape, since the well is the
# thing it would drift back to.
def test_the_timeline_kind_filter_is_one_button_rather_than_four() -> None:
    page = re.sub(
        r"<!--.*?-->", "", (ROOT / "frontend" / "index.html").read_text(encoding="utf-8"), flags=re.S
    )
    start = page.index('id="timeline-kinds-menu"')
    block = page[page.rindex("<details", 0, start) : page.index("</details>", start)]
    assert "dock-menu" in block and "doc-dock-menu-btn" in block, block[:200]
    assert 'id="timeline-kinds-label"' in block, (
        "the button says what the filter is set to, so it needs the span that "
        "carries the state"
    )
    assert 'id="timeline-kinds" class="seg seg-multi"' not in page, (
        "the Timeline's kind filter is a dock menu now, not a `.seg-multi` well: "
        "four glyphs and four words is 441px of a dock row that also holds a "
        "search box, a view switch and Options, which is what INBOX 214 reports"
    )
def test_a_thumb_bar_rides_the_keyboard_inset_it_did_not_measure() -> None:
    """DESIGN.md's recipe for a bar above the on-screen keyboard.

    Two halves, and neither can be seen in this sandbox: headless Chromium has
    no soft keyboard, so what a bar does when one opens is only ever reasoned.

    1. The bar's foot is a `max()` of the platform's own
       `env(keyboard-inset-height)`, the `--keyboard-inset` app.js writes from
       `visualViewport`, and the home-indicator inset. A bar that pads with
       none of them sits under the keys on every phone that has them.
    2. Nothing but `initKeyboardInset` listens to `visualViewport`. The number
       is written once for every surface that wants it; a second listener is
       how two bars end up disagreeing about where the keyboard is by a few
       pixels on every resize, which is the bug this recipe exists to make
       impossible rather than to fix twice.
    """
    feet = []
    for path in CSS:
        for selector, body in _rules(path.read_text(encoding="utf-8")):
            if _leading_name(selector) == ".thumb-bar":
                feet.append((path.name, body))
    assert feet, "no .thumb-bar rule: the recipe's own selector has been renamed"
    padded = [
        body for _, body in feet
        if "var(--keyboard-inset" in body and "env(safe-area-inset-bottom" in body
    ]
    assert padded, (
        ".thumb-bar pads its foot with neither --keyboard-inset nor the "
        "safe-area inset, so it sits under the keyboard and the home indicator"
    )

    listeners = []
    for path in JS:
        text = path.read_text(encoding="utf-8")
        for match in re.finditer(r"visualViewport", text):
            line = text.count("\n", 0, match.start()) + 1
            listeners.append(f"{path.name}:{line}")
    owner = app_js_text()
    body = owner[owner.index("function initKeyboardInset("):]
    body = body[: body.index("\n}\n")]
    assert body.count("visualViewport") == len(listeners), (
        "visualViewport is read outside initKeyboardInset (" + ", ".join(listeners) + "); "
        "read the --keyboard-inset property it writes instead"
    )

    html = (ROOT / "frontend" / "index.html").read_text(encoding="utf-8")
    for match in re.finditer(r"<div[^>]*class=\"[^\"]*thumb-bar[^\"]*\"[^>]*>", html):
        tag = match.group(0)
        assert 'role="toolbar"' in tag and "aria-label=" in tag, (
            "a thumb bar is a labelled toolbar: " + tag[:80]
        )


def test_no_inline_style_attributes_in_the_page() -> None:
    """The CSP rejects them silently (CLAUDE.md, section 6, shape 4)."""
    html = (ROOT / "frontend" / "index.html").read_text(encoding="utf-8")
    assert re.search(r"<[^>]+\sstyle=", html) is None


def test_the_quiet_button_recipe_holds() -> None:
    """The default buttons are quiet, not silver (the owner, 2026-09-27).

    Five screenshots of "grey, bordered, raised boxes": the tonal button's
    12% ink fill under a faint rim. The rest face is `--btn-quiet-bg` and
    the grey is state only; an icon standing alone is a ghost; the stepper
    is a recipe with its role, its name and a named unit between two
    labelled icon buttons.
    """
    css = (ROOT / "frontend" / "css" / "01-forms-settings.css").read_text(encoding="utf-8")
    rules = dict((sel.strip(), body) for sel, body in _rules(css))
    assert "background: var(--btn-quiet-bg)" in rules.get("button.ghost", ""), (
        "button.ghost rests on --btn-quiet-bg; --ghost-btn-bg at rest is the silver slab"
    )
    ghost_icon = next((b for s, b in rules.items() if s.startswith(":is(button, summary).ghost:is(.icon-only, .icon-button)") and ":hover" not in s), "")
    assert "background: transparent" in ghost_icon and "border-color: transparent" in ghost_icon
    stepper = rules.get(".stepper", "")
    assert "background: var(--btn-quiet-bg)" in stepper and "outline-offset: -1px" in stepper, (
        "the stepper is one quiet pill whose hairline is drawn inward, so it is the buttons' height"
    )
    assert "button.ghost:not(.icon-only, .icon-button) > .ph-lead" in rules, (
        "a labelled quiet button's leading icon takes the accent: the cue that tells it from a field"
    )
    html = (ROOT / "frontend" / "index.html").read_text(encoding="utf-8")
    groups = re.findall(r'<div class="stepper"[^>]*>(.*?)</div>', html, re.S)
    assert groups, "no .stepper in the page: Reminders' nudges were the first"
    for tag in re.findall(r'<div class="stepper"[^>]*>', html):
        assert 'role="group"' in tag and "aria-label=" in tag, tag
    for body in groups:
        buttons = re.findall(r"<button[^>]*>", body)
        assert len(buttons) == 2 and 'class="stepper-unit"' in body, body
        for button in buttons:
            assert "aria-label=" in button and "title=" in button and "icon-only" in button, button


def test_the_tonal_button_keeps_its_edge_and_its_lift() -> None:
    """`button.ghost` draws a real border and a real shadow.

    Third pass on one report. "control elements and buttons feel more like
    just shapes with text in them, rather than proper official buttons" was
    answered once with a border and a shadow; a later pass took both off and
    raised the fill instead, on a measurement taken in a *toolbar*; the
    report then came back a third time as "all the buttons need to actually
    look like buttons with affordance, not just shapes with text in them".

    So the base recipe is pinned here. A run of these inside something that
    already frames them (a dock, a card's row actions) is quieted by a more
    specific rule, which is the intended shape and is not what this guards
    against: what it guards against is the base rule being flattened again.
    """
    css = (ROOT / "frontend" / "css" / "01-forms-settings.css").read_text(encoding="utf-8")
    body = ""
    for selector, rule in _rules(css):
        if selector.strip() == "button.ghost":
            body = rule
            break
    assert body, "button.ghost has no rule in 01-forms-settings.css"
    assert "border: 1px solid var(--ghost-btn-border)" in body, (
        "button.ghost must draw a visible hairline: the edge is what makes it "
        "read as a control rather than a tinted shape with text in it"
    )
    assert "box-shadow: var(--shadow-sm)" not in body, (
        "button.ghost must not carry the panel shadow. `--shadow-sm` is seven "
        "times heavier in dark than in light, because a shadow over a near "
        "black page needs to be, and it was sized for a panel: under a 28px "
        "control it measured rgba(0, 0, 0, 0.35) on every button in the top "
        "bar at once, reported as \"the border shadow on elements like these "
        "are too strong\". The edge carries the affordance; the filled tier, "
        "one per surface, is what gets a glow"
    )


def test_the_press_cue_does_not_use_the_transform_property() -> None:
    """`button:active` composes with a button's own placement, never replaces it.

    `transform` is one property holding a list, so a press cue written as
    `transform: translateY(1px)` throws away whatever transform the button
    already had. Plenty of buttons here centre themselves with one
    (`left: 50%; transform: translateX(-50%)`), and every press moved them by
    half their own width: reported once for the lightbox arrows and again,
    measured at 68px, for the chat jump-to-latest pill. Written as `translate`
    and `scale`, which are separate properties, the cue cannot collide with
    anything, including buttons nobody has written yet.
    """
    css = (ROOT / "frontend" / "css" / "01-forms-settings.css").read_text(encoding="utf-8")
    body = ""
    for selector, rule in _rules(css):
        if selector.split(",")[0].strip() == "button:active:not(:disabled)":
            body = rule
            break
    assert body, "the global press cue rule has gone missing"
    assert "transform:" not in body, (
        "the press cue must use `translate`/`scale`, not `transform`: "
        "`transform` replaces a button's own centring and makes it jump"
    )
    # The motion pass (2026-10-05): a scale alone, 0.97, reads as the press.
    assert "scale: 0.97" in body and "translate:" not in body


def test_no_dialog_is_a_direct_child_of_a_page() -> None:
    """A modal `<dialog>` must not be authored inside a `.tab-page`.

    It is drawn in the top layer and centres itself with the UA's
    `position: fixed; inset: 0; width: fit-content; margin: auto`, but a
    direct child of a page also matches the content-column rules
    (`.tab-page > *`: `width: 100%` and a cap; `.tab-page > .card`: a bottom
    margin), which are more specific than the `.space-dialog { margin: auto }`
    that protects every other dialog. The two that were written there opened
    1440px wide against the left edge, reported three times as "the ai edit
    history popover still not centering".

    Asserted on the markup rather than on the CSS, because the two CSS fixes
    both misfire: an opt-out rule has to beat `.tab-page > .card` (0,2,0) and
    then also beats the dialog's own width class, and narrowing the column
    rules with `:not(dialog)` raises their specificity and knocks out
    `.dock-fab` (three phone primary actions went off-screen on that attempt).
    """
    html = (ROOT / "frontend" / "index.html").read_text(encoding="utf-8")
    pages = re.findall(
        r'<div[^>]*class="[^"]*\btab-page\b[^"]*"[^>]*id="(tab-[a-z-]+)"'
        r'|<div[^>]*id="(tab-[a-z-]+)"[^>]*class="[^"]*\btab-page\b[^"]*"',
        html,
    )
    assert pages, "no .tab-page elements found; this lint has lost its subject"
    offenders = []
    for match in re.finditer(r"<dialog[^>]*id=\"([^\"]+)\"", html):
        before = html[: match.start()]
        # The nearest unclosed `.tab-page` opener, if any, is this dialog's page.
        opens = len(re.findall(r'class="[^"]*\btab-page\b', before))
        if not opens:
            continue
        page_start = [m.start() for m in re.finditer(r'class="[^"]*\btab-page\b', before)][-1]
        segment = html[page_start : match.start()]
        # Depth from that opener to the dialog: 1 means direct child.
        depth = segment.count("<div") - segment.count("</div>")
        if depth == 1:
            offenders.append(match.group(1))
    assert offenders == [], (
        "these dialogs are direct children of a page and will take the content "
        "column's width and margins: " + ", ".join(offenders)
    )
def test_a_radial_places_its_slots_without_the_transform_properties() -> None:
    """A ring of actions is placed with `left`/`top`, never with `translate`.

    DESIGN.md's recipe index gained the radial with MINDMAP_PLAN §12.1 item 3
    (the map's node ring). The rule it needs a lint for is the one that is
    invisible in a diff and obvious on screen: the app's press cue is
    `translate` plus `scale` (pinned by the test above), and `translate` is one
    property holding a list, so a slot placed with it is thrown back to the
    ring's centre on every press. Same failure class as the lightbox arrows and
    the chat jump-to-latest pill, both of which were reported before the cue
    was rewritten; this stops the ring re-learning it.
    """
    css = "\n".join((ROOT / "frontend" / "css" / name).read_text(encoding="utf-8") for name in ("07-whiteboard-misc.css", "library-lazy.css"))
    placed = False
    for selector, body in _rules(css):
        if ".wb-map-radial-slot" not in selector:
            continue
        assert "transform:" not in body and "translate:" not in body, (
            f"{selector.strip()} places a radial slot with a transform; the "
            "recipe is `left`/`top` from --wb-radial-r (DESIGN.md, the recipe "
            "index), because the press cue owns `translate`"
        )
        if "left:" in body and "top:" in body:
            placed = True
    assert placed, (
        "the radial recipe has lost its `left`/`top` placement rule; "
        "DESIGN.md's recipe index says a slot is placed that way"
    )


def test_the_radial_band_is_cut_to_its_tiles() -> None:
    """The band under a ring holds its slots rather than a guessed width.

    INBOX 410: with a fixed 3rem band under 7rem pills, every diagonal pill
    hung 32px past the band's outer edge and 28px into its hole. The band is
    now drawn from two edges `wbFitMapRadialBand` measures off the placed
    slots, and the caption hangs under the outer edge; a rule that goes back
    to sizing the band from the radius alone brings the overhang back.
    """
    css = "\n".join((ROOT / "frontend" / "css" / name).read_text(encoding="utf-8") for name in ("07-whiteboard-misc.css", "library-lazy.css"))
    #: The map layer is whiteboard-map.js since the split; read both.
    js = "".join((ROOT / "frontend" / "js" / name).read_text(encoding="utf-8") for name in ("whiteboard.js", "whiteboard-map.js"))
    band = [body for selector, body in _rules(css) if selector.strip() == ".wb-map-radial::before"]
    assert band, "the radial's band rule is gone"
    assert "--wb-radial-outer" in band[0] and "--wb-radial-inner" in band[0], (
        "the band must be drawn from the measured inner and outer edges"
    )
    caption = [body for selector, body in _rules(css) if selector.strip() == ".wb-map-radial-caption"]
    assert caption and "--wb-radial-outer" in caption[0], (
        "the ring's caption hangs under the band's outer edge, not the radius"
    )
    place = js.split("function wbPlaceMapRadial(", 1)[1].split("\n}\n", 1)[0]
    assert "wbFitMapRadialBand(ring)" in place, "placing a ring must fit its band"


def test_the_radial_is_one_ring_cut_into_sectors() -> None:
    """Each action is a sector of the ring, not a button laid on a band.

    The owner, 2026-09-24: "the radial buttons are still clearly separate, I
    want them to be part of the radial, not just buttons sitting ontop of
    it". A slot is a button the size of the ring, clipped to its wedge by the
    path `wbFitMapRadialBand` writes; its face sits at the wedge's middle; the
    ring's own keys walk the sectors. A rule that goes back to sizing a slot
    as a tile, or a fit that stops writing the clip, is the old ring again.
    """
    css = "\n".join((ROOT / "frontend" / "css" / name).read_text(encoding="utf-8") for name in ("07-whiteboard-misc.css", "library-lazy.css"))
    js = "".join((ROOT / "frontend" / "js" / name).read_text(encoding="utf-8") for name in ("whiteboard.js", "whiteboard-map.js"))
    slot = [body for selector, body in _rules(css) if selector.strip() == ".wb-map-radial .wb-map-radial-slot"]
    assert slot, "the sector rule is gone"
    assert "calc(var(--wb-radial-outer) * 2)" in slot[0], "a sector is the whole ring's square, clipped"
    fit = js.split("function wbFitMapRadialBand(", 1)[1].split("\n}\n", 1)[0]
    assert "slot.style.clipPath" in fit and "wbMapRadialSectorPath" in fit, "the fit must cut each slot to its sector"
    assert "--wb-sector-x" in fit and "--wb-sector-y" in fit, "the fit must place each face at its sector's middle"
    html = (ROOT / "frontend" / "index.html").read_text(encoding="utf-8")
    slots = html.count("wb-map-radial-slot")
    assert slots and html.count('class="wb-map-radial-face"') == slots, "every sector draws its icon and word in a face"
    assert 'ring.addEventListener("keydown"' in js, "the ring must answer its own arrows, Enter and Escape"


def test_the_radial_is_a_toolbar_rather_than_a_menu() -> None:
    """A ring claims the role a screen reader can do something with.

    `role="menu"` promises a list walked with the arrow keys; a radial is a
    toolbar arranged in a circle. Claiming the wrong one is worse than
    claiming nothing, and it would also be a hand-built menu, which the
    ratchet above counts.
    """
    html = (ROOT / "frontend" / "index.html").read_text(encoding="utf-8")
    start = html.find('id="wb-map-radial"')
    assert start != -1, "the node radial has gone missing from index.html"
    opening = html[html.rfind("<div", 0, start): html.find(">", start) + 1]
    assert 'role="toolbar"' in opening, (
        "the node radial must be role=toolbar, not a menu (DESIGN.md, the "
        "recipe index)"
    )


def test_every_board_tool_names_its_own_cursor() -> None:
    """A cursor is a promise about what the click will do.

    Reported (INBOX 115): "when Im on the delete tool on the mindmap and
    hover over a mindmap text node, the cursor changes to the grabber hand".
    Two separate causes, both of which this holds shut. The first: a tool
    with no case in `wbCursorForTool` falls through to the `""` Pan returns,
    and `""` means "whatever the CSS says", which for the board container is
    `cursor: grab`. Select was fixed for exactly that once; bucket, sticky
    and text were still falling through three tools later. Measured before
    the fix: six of the eighteen tool/surface pairs showed the open hand
    that means "drag the canvas".
    """
    html = (ROOT / "frontend" / "index.html").read_text(encoding="utf-8")
    js = (ROOT / "frontend" / "js" / "whiteboard.js").read_text(encoding="utf-8")
    tools = set(re.findall(r'data-tool="([a-z-]+)"', html))
    assert len(tools) >= 18, tools
    body = js[js.index("function wbCursorForTool(") : js.index("// The visible half of Select")]
    brushes = set(re.findall(r'"([a-z]+)"', js[js.index("const WB_BRUSH_TOOLS"):js.index("const WB_HIGHLIGHTER_ALPHA")]))
    # The flyout's further shapes are brushes by the spread of their table's
    # keys; the keys are read off the table, so a new one is still checked.
    if "...Object.keys(WB_MORE_SHAPES)" in js[js.index("const WB_BRUSH_TOOLS"):js.index("const WB_HIGHLIGHTER_ALPHA")]:
        more = js[js.index("const WB_MORE_SHAPES"):js.index("const WB_BRUSH_TOOLS")]
        brushes |= set(re.findall(r'^  "(shape-[a-z-]+)": \{', more, re.M))
    # Pan is the one tool that deliberately returns "": the container's own
    # grab/grabbing pair is its cursor, and the comment on that line says so.
    assert 'return ""; // pan' in body
    tools.discard("pan")
    missing = sorted(t for t in tools if t not in brushes and f'"{t}"' not in body)
    assert not missing, f"tools with no cursor of their own: {missing}"


def test_an_item_does_not_promise_a_drag_under_a_tool_that_does_not_drag() -> None:
    """The second cause: every item on the board carries `cursor: grab`
    because Select and Hand really do drag it, and an item's own rule beats
    the tool cursor written inline on the container. Measured before the
    fix with `getComputedStyle(el).cursor`, once per tool over a map node,
    its text and a whiteboard object: 32 of those pairs answered `grab`
    while the click would have deleted, erased, drawn, filled or linked.
    """
    css = "\n".join((ROOT / "frontend" / "css" / name).read_text(encoding="utf-8") for name in ("07-whiteboard-misc.css", "library-lazy.css"))
    guard = (
        '#whiteboard-container:not([data-current-tool="select"])'
        ':not([data-current-tool="pan"])'
    )
    assert guard in css
    rule = css[css.index(guard) : css.index("}", css.index(guard))]
    assert "cursor: inherit" in rule
    for selector in (".wb-object", ".node-card", ".wb-map-text", ".wb-text-content"):
        assert selector in rule, selector


def test_the_boards_selector_says_which_kind_each_board_is() -> None:
    """Reported (INBOX 115): "whiteboards and mindmaps need to be
    differentiable in the boards selector". Measured before: the top bar's
    `#wb-board-select` listed five options reading `Title (N items)`, four of
    them maps, with nothing on any of them saying so, under an aria-label
    that called all five whiteboards.

    MINDMAP_PLAN §5 item 12 already decided the idiom ("a map says it is one,
    in the row", which `mapChip` follows on the timeline, in a note and in the
    chat). A native `<option>` cannot hold that chip's icon, so the group
    heading carries it, the way three other selects in this app already do.
    """
    js = (ROOT / "frontend" / "js" / "whiteboard.js").read_text(encoding="utf-8")
    html = (ROOT / "frontend" / "index.html").read_text(encoding="utf-8")
    body = js[js.index("async function refreshBoardList") : js.index("async function renameCurrentBoard")]
    assert 'createElement("optgroup")' in body
    assert '"Mind maps"' in body and '"Whiteboards"' in body
    select = html[html.index('<select id="wb-board-select"') :]
    select = select[: select.index(">") + 1]
    assert "Which board or map to show" in select
    assert "Which whiteboard to show" not in select
#: A row that says "you are here" and marks it with a class alone.
#: `classList.toggle("is-current-page", …)` is deliberately not matched: that
#: one highlights every row belonging to a page, which is a filter, not a
#: position.
CURRENT_ROW = re.compile(r'classList\.(?:add|toggle)\(\s*"is-current"')


def test_a_row_that_says_where_you_are_also_says_so_to_a_screen_reader() -> None:
    """DESIGN.md's recipe index: where-you-are is `aria-current`, not a colour.

    The document outline is the case that earned the rule. Measured before it
    had one: scrolled to 70% of a 21-heading document, nothing under
    `#doc-outline` carried a current class or `aria-current`, so the panel
    could not answer the one question a table of contents exists to answer.
    The fix is only half a fix if the mark is paint: a fill that no screen
    reader announces, and that one reader in twelve cannot separate from the
    rows around it, is a mark that is not there.

    So the two halves are checked together. The paint hangs off the attribute
    in CSS, which means removing the attribute removes the paint and the two
    cannot drift apart, and every file that adds the class sets the attribute
    beside it.
    """
    css = "\n".join(path.read_text(encoding="utf-8") for path in CSS)
    assert ".outline-link[aria-current]" in css, (
        "the outline's current row must be painted from [aria-current], so the "
        "mark and its announcement are one thing (DESIGN.md, the recipe index)"
    )
    for path in JS:
        text = path.read_text(encoding="utf-8")
        for match in CURRENT_ROW.finditer(text):
            window = text[match.start() : match.start() + 600]
            assert "aria-current" in window, (
                f"{path.name} marks a row as the current one with a class and "
                "never sets aria-current beside it: that mark is a colour, and "
                "a colour is not a position (DESIGN.md, the recipe index)"
            )


def _tool_palettes() -> list[tuple[str, list[str]]]:
    """Every bar built from `.wb-tool-section`, with what sits loose in it.

    Returns (bar name, complaints). A bar is any element with at least one
    `.wb-tool-section` child; a complaint is a control that is not inside a
    `.wb-tool-section-row`, or a section that is not one label and one row.

    Built as a tree rather than judged while walking, because document order
    does not cooperate: a control dropped into a palette *before* its first
    section would be read while nothing yet knows that the element it sits in
    is a palette at all, which is the one arrangement this most needs to
    catch (proved by putting exactly that into the markup and watching a
    stack-walking version of this pass).
    """
    from html.parser import HTMLParser

    html = re.sub(r"<!--.*?-->", "", (ROOT / "frontend" / "index.html").read_text(encoding="utf-8"), flags=re.S)

    class Tree(HTMLParser):
        def __init__(self) -> None:
            super().__init__()
            self.nodes: list[dict] = []
            self.open: list[int] = []
            self.void = {"input", "img", "br", "hr", "meta", "link"}

        def handle_starttag(self, tag, attrs):
            a = dict(attrs)
            node = {
                "index": len(self.nodes),
                "tag": tag,
                "classes": set((a.get("class") or "").split()),
                "id": a.get("id") or "",
                "type": a.get("type") or "",
                "parent": self.open[-1] if self.open else None,
                "children": [],
            }
            index = len(self.nodes)
            self.nodes.append(node)
            if node["parent"] is not None:
                self.nodes[node["parent"]]["children"].append(index)
            if tag not in self.void:
                self.open.append(index)

        def handle_startendtag(self, tag, attrs):
            self.handle_starttag(tag, attrs)

        def handle_endtag(self, tag):
            for i in range(len(self.open) - 1, -1, -1):
                if self.nodes[self.open[i]]["tag"] == tag:
                    del self.open[i:]
                    return

    tree = Tree()
    tree.feed(html)
    nodes = tree.nodes

    def ancestors(index: int):
        while index is not None:
            yield nodes[index]
            index = nodes[index]["parent"]

    bars: dict[str, list[str]] = {}
    palette_ids: set[int] = set()
    for index, node in enumerate(nodes):
        if "wb-tool-section" in node["classes"] and node["parent"] is not None:
            palette_ids.add(node["parent"])
    for index in palette_ids:
        node = nodes[index]
        bars[node["id"] or "." + "-".join(sorted(node["classes"])[:1])] = []

    def name_of(index: int) -> str:
        node = nodes[index]
        return node["id"] or "." + "-".join(sorted(node["classes"])[:1])

    for index, node in enumerate(nodes):
        if "wb-tool-section" in node["classes"] and node["parent"] in palette_ids:
            labels = sum(
                1 for child in node["children"] if "wb-tool-section-label" in nodes[child]["classes"]
            )
            rows = sum(
                1 for child in node["children"] if "wb-tool-section-row" in nodes[child]["classes"]
            )
            if labels != 1 or rows != 1:
                bars[name_of(node["parent"])].append(
                    f"a section with {labels} labels and {rows} rows"
                )
        is_control = node["tag"] in ("button", "select") or (
            node["tag"] == "input" and node["type"] != "hidden"
        )
        if not is_control:
            continue
        chain = list(ancestors(node["parent"]))
        palette = next((a for a in chain if a["index"] in palette_ids), None)
        if palette is None:
            continue
        if not any("wb-tool-section-row" in a["classes"] for a in chain):
            bars[name_of(palette["index"])].append(
                f"{node['id'] or sorted(node['classes']) or node['tag']} is not in a .wb-tool-section-row"
            )
    return sorted(bars.items())

def test_a_tool_palette_is_all_sections_or_none() -> None:
    """A bar of many tools is labelled sections, and nothing loose beside them.

    DESIGN.md's recipe index, the row for a palette of many tools. The
    whiteboard's rail learned this the expensive way (42 icons in one flat
    group, "neither is a design; both are an inventory") and the sketch pad's
    toolbar was reported in exactly the same words: "the quick sketck popup
    controls need a new redesign as they are clumped and ugly". What the
    recipe buys is that a group has a name and a hairline, and what this
    guards is the half-application: one control dropped into the bar beside
    the sections, which is where the next "clumped" report comes from, since
    it belongs to no group and says nothing about itself.

    Both live palettes (`#wb-tool-group`, `#sketch-toolbar`) are read from the
    markup, so a third one joins the rule by being written, not by being
    listed here.
    """
    palettes = _tool_palettes()
    assert palettes, "no tool palette found: this lint is looking at the wrong markup"
    for bar, complaints in palettes:
        assert not complaints, (
            f"{bar}: " + "; ".join(complaints) + " (DESIGN.md, the recipe index: a "
            "palette of many tools is `.wb-tool-section` wrapping a "
            "`.wb-tool-section-label` and a `.wb-tool-section-row`)"
        )


class _PanelHeads(HTMLParser):
    """Every `.panel-head` in the page, with the chips and buttons inside it.

    A stack walker rather than a regex: a head holds nested spans, and what
    matters is which element a button or a chip is *inside*, not which line it
    sits on.
    """

    VOID = {"input", "img", "br", "hr", "meta", "link"}

    def __init__(self) -> None:
        super().__init__()
        self.stack: list[dict] = []
        self.heads: list[dict] = []

    def handle_starttag(self, tag, attrs) -> None:
        a = dict(attrs)
        classes = set((a.get("class") or "").split())
        head = None
        if "panel-head" in classes:
            head = {
                "id": a.get("id") or "",
                "classes": classes,
                "chips": 0,
                "buttons": [],
            }
            self.heads.append(head)
        else:
            for frame in reversed(self.stack):
                if frame["head"] is not None:
                    head = frame["head"]
                    break
        if head is not None and "panel-head" not in classes:
            if "chip" in classes:
                head["chips"] += 1
            if tag == "button":
                head["buttons"].append(
                    {
                        "id": a.get("id") or "(no id)",
                        "classes": classes,
                        "label": a.get("aria-label") or "",
                    }
                )
        if tag not in self.VOID:
            self.stack.append({"tag": tag, "head": head if "panel-head" in classes else None})

    def handle_endtag(self, tag) -> None:
        for index in range(len(self.stack) - 1, -1, -1):
            if self.stack[index]["tag"] == tag:
                del self.stack[index:]
                return


def _panel_heads() -> list[dict]:
    parser = _PanelHeads()
    parser.feed((ROOT / "frontend" / "index.html").read_text(encoding="utf-8"))
    return parser.heads


def test_a_panel_head_is_identity_one_fact_and_actions_that_do_not_wrap() -> None:
    """DESIGN.md's recipe index, the row for a panel head.

    Reported twice about the same head, the Ask sub-tab's "AI answer": first
    "the ai answer with the ai model badge and the retry, copy and dictate read
    out loud buttons are misalligned because of wrap", then, about the tidier
    two-row result that answered it, "these buttons and badges wrap onto a new
    line and I want them restructured some other way".

    The recipe is the dock grammar applied to a panel head: identity, then at
    most one fact, then the actions, and the row does not wrap. What this lint
    holds is the two halves a future head is most likely to get wrong, because
    each of them looks harmless on its own:

    - **One chip.** A head's width is decided by the facts in it, and a second
      variable-length fact is a second thing with no rule about which of them
      gives way, which is precisely how the reported head came apart.
    - **One kind of control.** DESIGN.md, from the HIG: a group is all icons or
      all text, never mixed. The reported head was mixed (Retry and Copy
      carried labels, the speak button did not), and taking the labels off is
      what let the row fit a 356px column at 1024 (measured,
      `scratchpad/ui-sweeps/askhead.js`). An icon with no `aria-label` is not a
      control, so that is checked with it.

    The `nowrap` itself is checked in the stylesheet: it is one declaration and
    it has to be in 08-consistency.css, because `.chat-half h3` sets
    `flex-wrap: wrap` at (0,1,1) and a bare class in an earlier file loses to
    it whatever the source order (measured: the head stayed 88px tall).
    """
    heads = _panel_heads()
    assert heads, "no .panel-head found: this lint is looking at the wrong markup"
    for head in heads:
        name = head["id"] or "+".join(sorted(head["classes"] - {"panel-head"})) or "a .panel-head"
        assert head["chips"] <= 1, (
            f"{name} carries {head['chips']} chips. A panel head states one fact; "
            "a second one is a second claim on a width nobody has ruled on "
            "(DESIGN.md, the recipe index)"
        )
        labelled = [b for b in head["buttons"] if "icon-only" in b["classes"] or "icon-button" in b["classes"]]
        if head["buttons"]:
            assert len(labelled) == len(head["buttons"]), (
                f"{name} mixes icon-only and labelled buttons: "
                + ", ".join(b["id"] for b in head["buttons"] if b not in labelled)
                + " carry words. A group is all icons or all text (DESIGN.md, from the HIG)"
            )
        for button in labelled:
            assert button["label"], (
                f"{name}: {button['id']} is an icon with no aria-label, which is not a control"
            )

    css = (ROOT / "frontend" / "css" / "08-consistency.css").read_text(encoding="utf-8")
    head_rule = next(
        (body for selector, body in _rules(css) if "h3.answer-head" in selector),
        None,
    )
    assert head_rule is not None, (
        "the answer head's rule left 08-consistency.css. It has to be in the last "
        "stylesheet and it has to name the element: `.chat-half h3` sets "
        "flex-wrap: wrap at (0,1,1)"
    )
    assert "flex-wrap: nowrap" in head_rule, (
        "the answer head wraps again. The badge ellipsises; the row does not break"
    )


#: Every list row built on the list-row step, with the container whose rows
#: they are. DESIGN.md's recipe index names the shape; this is what has been
#: brought onto it. A new list joins the map rather than picking its own
#: height, and a row that drops the token fails here.
LIST_ROWS = {
    ".timeline-row": ".timeline-rows",
    ".bookmark-row": ".bookmark-list",
    #: The popup agent's starters (INBOX 231). The grid is both the list and
    #: the rows' only selector, so the container it is spaced by is itself.
    ".command-palette-examples": ".command-palette-examples",
    #: The writing dictionary's words (INBOX 410, the settings-sheet redesign).
    ".doc-dictionary-row": ".doc-dictionary-list",
    #: The Library's Contents outline (INBOX 496, the redesign).
    ".contents-row": ".contents-list",
    #: The model bench's report, one row per model (WORLD_CLASS_PLAN I8).
    ".bench-row": ".bench-results",
    #: The board's Layers tab (WHITEBOARD_PLAN decision 27).
    ".wb-layer-row": ".wb-layers-tree",
    #: The board's named layers above that tree (canvasdepth, INBOX 797).
    ".wb-named-layer": ".wb-named-layer-list",
    #: A meeting's action items, in its sheet (INBOX 644).
    ".meeting-action": ".meeting-actions-list",
    #: Library, Recordings (WORLD_CLASS_PLAN 28.5 row 6).
    ".recording-row": ".recordings-list",
    #: A code file's snippets, in the code panel (INBOX 788).
    ".doc-snippet-row": ".doc-snippet-list",
}


def test_a_list_row_sits_on_the_list_row_tokens() -> None:
    """DESIGN.md's recipe index: a row in a list is `--row-h` and `--row-gap`.

    `--row-h` was declared for the Timeline and nothing else reached for it,
    so the next list picked its own numbers: the Library's saved links stood
    at 67.2px, or 89.2px once a link had a group, in a list whose gap was a
    spacing step chosen by hand. The token exists precisely so that two lists
    in one app do not answer "how tall is a row" differently.

    Both halves are checked, because a row height without the list's own gap
    is half the recipe: the row is the step and the gap between rows is the
    spacing that goes with it.
    """
    css = "\n".join(path.read_text(encoding="utf-8") for path in CSS)
    rows = {
        _leading_name(selector)
        for selector, body in _rules(css)
        if "var(--row-h)" in body
    }
    assert rows == set(LIST_ROWS), (
        f"rules using --row-h: {sorted(rows)}; rows this lint knows about: "
        f"{sorted(LIST_ROWS)}: a new list row joins LIST_ROWS (DESIGN.md, the "
        "recipe index)"
    )
    for row, container in LIST_ROWS.items():
        gaps = [
            body
            for selector, body in _rules(css)
            if _leading_name(selector) == container and "var(--row-gap)" in body
        ]
        assert gaps, (
            f"{row} sits on --row-h but {container} does not space its rows "
            "with --row-gap: the two are one recipe"
        )


#: The facts line: one short statement per fact, dot separated, on one rank.
#: The Files rows earned it, the picture cards and the saved links share it.
#: Each carries `.library-file-meta` for the rank and a handle of its own for
#: whatever its layout needs, so this is the set of handles.
FACTS_LINES = {".library-image-meta", ".bookmark-meta", ".att-card-meta", ".bench-row-meta"}


def test_the_facts_line_is_one_rule_rather_than_three() -> None:
    """DESIGN.md's recipe index: a line of facts is `.library-file-meta`.

    Three surfaces in the Library say several short things about one object:
    a file row (kind, size, pages, added), a picture card (where it is used,
    what was read out of it) and a saved link (the site, the group, the note).
    Each report behind them was the same report, a column of one-line blocks
    each given a row of its own, so they get one answer. A copy of the rule
    under a second name is how the three drift apart again, and a copy always
    starts by restating the size.

    So: one rule sets the rank, every facts line is built by `metaLine()`, and
    a handle may position its line but never resize it.
    """
    css = "\n".join(path.read_text(encoding="utf-8") for path in CSS)
    shared = [
        selector
        for selector, body in _rules(css)
        if _leading_name(selector) == ".library-file-meta" and "font-size" in body
    ]
    assert len(shared) == 1, (
        "the facts line's rank should come from exactly one rule; found "
        f"{len(shared)}: {shared}"
    )
    js = "\n".join(path.read_text(encoding="utf-8") for path in JS)
    for line in FACTS_LINES:
        name = line[1:]
        beside = re.search(rf'"library-file-meta {name}"', js)
        through = re.search(rf'metaLine\([^;]*?"{name}"', js, re.S)
        assert beside or through, (
            f"{line} is a facts line but nothing builds it with the shared "
            "class: either pass the handle to metaLine() or put "
            f'"library-file-meta {name}" on the element, so the rank comes '
            "from the one rule (DESIGN.md, the recipe index)"
        )
    for line in FACTS_LINES:
        for selector, body in _rules(css):
            if _leading_name(selector) == line:
                assert "font-size" not in body, (
                    f"{selector.strip()} sets its own font size: a facts line "
                    "takes the shared rule's rank (DESIGN.md, the recipe index)"
                )


def test_a_facts_line_chip_opens_a_surface_rather_than_the_card() -> None:
    """DESIGN.md's recipe index: a fact that is also the way in is a
    `.library-chip` button, and what it opens is never the card it sits on.

    The report (INBOX 279): "I als want you to better design the bottom text
    for captions and ocr in the image cards in the library images subtab",
    with a screenshot of six rows of chrome under one thumbnail. The reading
    was a `<details>` opening in place, and a 180px picture tile has no place:
    measured at 1440, opening it took the card from 240.7px to 416.3px and the
    grid gives every card in a row the tallest one's height, so one card's
    transcription resized its five neighbours.

    The chip opens the lightbox instead, at the reading, which is the same
    door the tile's own click and the Files row's "Open reading" use. This
    lint holds the two halves that made it right: the control is the app's own
    pressable chip rather than a hand-built one, and the picture card's facts
    line holds no disclosure.
    """
    library = (ROOT / "frontend" / "js" / "library.js").read_text(encoding="utf-8")
    assert 'textChip.className = "library-chip library-image-text-chip"' in library, (
        "the picture card's reading chip is `.library-chip`, the app's own "
        "pressable chip (DESIGN.md, the recipe index)"
    )
    assert "metaRow.append(visionField)" not in library, (
        "the picture card's facts line must not hold a disclosure again: what "
        "it opens has to be a surface with room for a transcription"
    )
    #: The chip's own size, not the facts line's: a rule led by
    #: `.library-image-meta` carrying a font-size is the regression
    #: `test_the_facts_line_is_one_rule_rather_than_three` above describes, and
    #: this is the rule that was written that way first.
    css = "\n".join(path.read_text(encoding="utf-8") for path in CSS)
    for selector, body in _rules(css):
        if "library-image-text-chip" in selector and "font-size" in body:
            assert _leading_name(selector) == ".library-image-text-chip", (
                f"{selector.strip()} sizes the chip from the facts line's handle; "
                "put it on the chip's own class"
            )


def _function_body(text: str, name: str) -> str:
    """The source of one top-level function, from its `function` to the next one.

    Crude on purpose: these lints ask what a named function *mentions*, and a
    brace-matching parse of 11,000 lines of JS to answer that would be a second
    thing to get wrong.
    """
    start = text.index(f"function {name}(")
    after = re.search(r"\n(?:async )?function ", text[start + 1 :])
    return text[start : start + 1 + after.start()] if after else text[start:]


def test_a_list_row_answers_in_place_rather_than_opening_a_popover() -> None:
    """DESIGN.md's recipe index: a row you can act on expands, it does not pop.

    The report that earned the recipe (INBOX 142): "when I click on the issue
    from the suggestions thing, the box just appears right there in my face."
    The writing panel's rows had no answers of their own, so acting on one
    opened the floating word menu: measured at 1440x900, 335px of menu drawn
    over the 297px panel that asked for it, 70% of the window's height spent on
    one misspelled word, with the sentence being discussed behind both.

    Three halves of the fix, each one a thing a later session could undo
    without noticing:

    1. the panel's row builder must not reach for the floating menu again;
    2. the open row has to say so in the markup (`aria-expanded` on the
       control, `aria-current` on the row) and be painted from the attribute,
       or the mark is a colour and a colour is not a position;
    3. the answers must come from the one builder the menu also uses, because
       two sets of the same four actions is how the panel came to have none.
    """
    js = (ROOT / "frontend" / "js" / "documents.js").read_text(encoding="utf-8")
    css = "\n".join(path.read_text(encoding="utf-8") for path in CSS)

    for name in ("docProseGroupList", "docProseRowAnswers"):
        body = _function_body(js, name)
        assert "openDocSuggest" not in body, (
            f"{name} opens the floating word menu: a list row answers inside the "
            "list (DESIGN.md, the recipe index), it does not draw a popover over "
            "the text it is about"
        )

    rows = _function_body(js, "docProseGroupList")
    assert 'setAttribute("aria-expanded"' in rows, (
        "the writing panel's row control must carry aria-expanded: a row that "
        "opens something has to say whether it is open"
    )
    answers = _function_body(js, "docProseRowAnswers")
    assert 'aria-current", "location"' in answers, (
        "the open row must take aria-current=\"location\", the recipe index's "
        "mark for where you are inside a document"
    )
    assert "docSuggestAnswers(" in answers, (
        "the row's answers must come from docSuggestAnswers, the same builder "
        "the word menu uses: a second copy of those actions is how the two "
        "surfaces drifted apart in the first place"
    )
    assert "scrollIntoView(" not in answers, (
        "bring the open row into view with the panel's own scrollTop: "
        "scrollIntoView walks every scrolling ancestor, the page included "
        "(DESIGN.md, the recipe index)"
    )
    assert ".doc-prose-row[aria-current]" in css, (
        "the open row's paint must hang off [aria-current] so the mark and its "
        "announcement are one thing (DESIGN.md, the recipe index)"
    )


def test_every_selection_bar_is_one_sticky_recipe() -> None:
    """DESIGN.md's recipe index: a bar of actions for a selection sticks.

    INBOX 165, verbatim: "I want the selected bars to be sticky to the top of
    the screen when scrolling". Reported against the Library's own bar, and it
    was the same fault on all seven: the bar sits above the list it governs, so
    the moment you scroll far enough to tick a second item the actions for the
    first are off the screen (measured: the Notes bar at y=-465 with its list
    scrolled 677px).

    Two things a later diff could undo without anyone noticing, which is why
    they are a lint rather than a note:

    1. a new selection bar built without `selectbar` scrolls away again, and
       it will look right in every screenshot taken before the list is long
       enough to scroll;
    2. the sticky ground has to be stacked over an opaque base. The tint alone
       is a 14% wash, which reads correctly at rest on a card and turns into a
       window the moment the list moves under it. `.doc-toolbar` was reported
       for exactly that ("the bar is clear so it is hard to see").
    """
    markup = (ROOT / "frontend" / "index.html").read_text(encoding="utf-8")
    library = (ROOT / "frontend" / "js" / "library.js").read_text(encoding="utf-8")
    css = "\n".join(path.read_text(encoding="utf-8") for path in CSS)

    # Every bar in the markup that shows a selection count, by the two id
    # shapes the app uses for them. A bar built in JS is covered below.
    bars = re.findall(r'<div id="([\w-]*(?:selectbar|batch-bar))" class="([^"]*)"', markup)
    assert len(bars) >= 5, f"the selection bars have moved or been renamed: {bars}"
    for name, classes in bars:
        assert "selectbar" in classes.split(), (
            f"#{name} is a bar of actions for a selection and must carry the "
            "`selectbar` class (DESIGN.md, the recipe index): without it the bar "
            "scrolls away from the list it governs"
        )
        assert "library-contextbar" in classes.split(), (
            f"#{name} must wear the one selection-bar strip, not a bare .row: "
            "a selection is a selection wherever you make it"
        )

    assert 'bar.className = "library-contextbar selectbar hidden"' in library, (
        "createLibrarySelectbar builds the Boards and Links bars: they need the "
        "same recipe class as the ones in the markup"
    )

    sticky = re.search(r"\n\.selectbar \{(.*?)\n\}", css, re.S)
    assert sticky, ".selectbar's own rule is missing: the recipe has no sticky half"
    body = sticky.group(1)
    assert "position: sticky" in body, ".selectbar must be sticky (INBOX 165)"
    assert "--selectbar-top" in body, (
        "`top` must come from `--selectbar-top`: two sticky things in one "
        "scroller park in the same band (commit 27167e3), so a bar under a "
        "sub-tab strip has to stop below it"
    )
    assert "linear-gradient(var(--accent-soft), var(--accent-soft))" in body, (
        "the sticky ground must stack the tint over an opaque base: "
        "`--accent-soft` alone is a 14% wash and the list shows straight "
        "through it while it scrolls"
    )


def test_a_viewport_popup_leaves_the_surfaces_that_can_blur() -> None:
    """DESIGN.md's recipe index: a popup placed in window coordinates lives in
    the window's own frame, and proves it landed there.

    The report that earned the recipe (INBOX 168, with a screenshot): the word
    menu for "tets" drawn at the right edge of the window with its column cut
    off past it and its list under the bottom bar. The arithmetic was never
    wrong: `placeDocSuggest` clamps unconditionally, so the menu cannot leave
    the viewport by adding up badly. It was being laid out against something
    that is not the viewport. A `position: fixed` element takes its containing
    block from the nearest ancestor with a `filter`, `transform` or
    `backdrop-filter`, and `:root[data-bg-art="on"]:not([data-glass="off"])
    .card` gives the document card one whenever the background art is on.
    Measured at 1440x900 with the art on: the menu asked for `left 952, top
    322` and drew at `1245..1485, 399`, 45px past the right edge of the window
    and 53px from its word.

    Two halves, either of which a later session could drop without seeing
    anything move on a machine with the art switched off:

    1. the popup leaves the card while it is open and goes back on the way out;
    2. the placement measures what was drawn and corrects the difference, which
       is cause-agnostic: the next property CSS invents that creates a
       containing block is covered the day it ships.
    """
    js = (ROOT / "frontend" / "js" / "documents.js").read_text(encoding="utf-8")
    app = app_js_text()

    lifts = {
        "openDocSuggest": "docLiftToViewport(",
        "renderDocComplete": "docLiftToViewport(",
        "closeDocSuggest": "docReturnFromViewport(",
        "hideDocComplete": "docReturnFromViewport(",
    }
    for name, call in lifts.items():
        assert call in _function_body(js, name), (
            f"{name} must call {call.rstrip('(')}: a popup placed in window "
            "coordinates cannot be a descendant of a surface that blurs "
            "(DESIGN.md, the recipe index)"
        )

    # The placement goes through the helper rather than writing the numbers
    # itself, or the correction below is one function away from the code that
    # needs it.
    place = _function_body(js, "placeDocSuggest")
    assert "docPlaceFixed(" in place and "style.left" not in place, (
        "placeDocSuggest must place the menu through docPlaceFixed, which "
        "checks the menu landed where it was put (DESIGN.md, the recipe index)"
    )

    # The size is read with the menu parked at the band's left edge, never
    # where the last open left it. A `position: fixed` box with `left` set and
    # no `right` is shrink-to-fit against the room to its right, so a menu
    # still standing near the window's right edge measures narrower than it
    # will draw once moved, and the placement is computed from the wrong
    # width (OPEN.md, "The word menu measures its own width before it is
    # placed").
    parked = place.index("docPlaceFixed(")
    assert parked < place.index("offsetWidth"), (
        "placeDocSuggest must park the menu (docPlaceFixed at the edge) "
        "before it reads its width, or a long candidate near the right edge "
        "measures shrunk"
    )

    # Both of the app's viewport popups measure after placing. Compared by
    # position rather than by name: what matters is that the rect is read
    # *after* the first write, which is the whole of the correction.
    for text, name in ((js, "docPlaceFixed"), (app, "clampToolbarMenu")):
        body = _function_body(text, name)
        wrote = body.index(".style.left")
        assert "getBoundingClientRect()" in body[wrote:], (
            f"{name} sets a fixed popup's position and never checks it landed "
            "there: measure the rect after writing and correct by the "
            "difference (DESIGN.md, the recipe index)"
        )


def test_one_writing_finding_is_drawn_by_one_builder() -> None:
    """DESIGN.md's recipe index: the four surfaces of the writing suggestions
    draw one object one way.

    The report (INBOX 142): "the whole editor intelligence and auto correct and
    dictionary stuff needs a whole ux redesign". Four surfaces had grown
    separately and described one finding in three orders under five names. The
    line is built once (`docFindingLine`: dot, words, reason) and the answers
    are built once (`docSuggestAnswers`), so the panel row and the floating menu
    cannot drift apart again by being edited one at a time.
    """
    js = (ROOT / "frontend" / "js" / "documents.js").read_text(encoding="utf-8")

    for name in ("docProseGroupList", "openDocSuggest"):
        assert "docFindingLine(" in _function_body(js, name), (
            f"{name} must draw its finding with docFindingLine: one object, one "
            "drawing, in the panel and in the menu (DESIGN.md, the recipe index)"
        )
    for name in ("docProseRowAnswers", "openDocSuggest"):
        assert "docSuggestAnswers(" in _function_body(js, name), (
            f"{name} must take its answers from docSuggestAnswers: a second copy "
            "of those actions is how the panel came to have none (DESIGN.md, "
            "the recipe index)"
        )
    # The pieces of the line are made in exactly one place. A second
    # `doc-finding-dot` somewhere else is a second drawing of the same object,
    # whatever it looks like on the day it is written.
    for piece in ("doc-finding-dot", "doc-finding-words", "doc-finding-why"):
        assert js.count(f'"{piece}') + js.count(f"`{piece}") == 1, (
            f"{piece} is built in more than one place: a finding is drawn by "
            "docFindingLine alone (DESIGN.md, the recipe index)"
        )

    #: **And the kinds themselves are named in two places that have to agree.**
    #: `docFindingKind` decides which dot and which underline a finding gets;
    #: `DOC_FINDING_GROUPS` decides which heading it is filed under in the
    #: panel. They agree today, and nothing made them: a fourth kind added to
    #: the first alone renders with its own squiggle and then falls into no
    #: group in the panel, which looks like a finding the panel has lost. A
    #: fourth added to the second alone draws an empty heading forever, since
    #: the panel skips a group with no members. Neither failure throws.
    kinds_drawn = set(re.findall(r'return "([a-z]+)";', _function_body(js, "docFindingKind")))
    groups = js[js.index("const DOC_FINDING_GROUPS = ["):]
    kinds_grouped = set(re.findall(r'\["([a-z]+)", "', groups[: groups.index("\n];")]))
    assert kinds_drawn and kinds_grouped, "one of the two finding-kind tables could not be read"
    assert kinds_drawn == kinds_grouped, (
        "docFindingKind draws "
        + ", ".join(sorted(kinds_drawn))
        + " and DOC_FINDING_GROUPS files "
        + ", ".join(sorted(kinds_grouped))
        + ": a kind in one and not the other is either an underline with no "
        "group in the panel or a heading that can never have a member"
    )
    #: The stylesheet is the third place the same three names appear, as the
    #: class `docFindingKind`'s answer is interpolated into
    #: (`cm-finding-${kind}`), so a kind with no rule there is an underline
    #: with no shape and no colour.
    for kind in sorted(kinds_drawn):
        assert f".cm-finding-{kind}" in js, (
            f"the {kind} finding has no underline rule in docCmTheme, so it "
            "draws as plain text while the panel lists it"
        )


#: **A surface says when its data did not arrive, and says it in one way.**
#:
#: Measured with every request failing (`scratchpad/ui-sweeps/vibefail.js`):
#: four surfaces drew their empty state, so a full notebook read "Your notebook
#: is empty", and the dashboard's tiles printed "0 this week" from arrays that
#: were empty because nothing had been read. Both are the app stating a fact
#: about the person's own notes on no evidence, which is the shape the owner
#: described as making an application untrustworthy.
#:
#: The floor rather than an exact list: a surface added later should be wired
#: too, and this fails the moment one is unwired, which is the direction that
#: matters. The names are here so a rename has to come past this test.
FAILING_SURFACES = {
    "frontend/js/app.js": ("notes", "reminders"),
    "frontend/js/timeline.js": ("timeline",),
    "frontend/js/graph.js": ("map",),
    "frontend/js/graph-canvas.js": ("map",),
    "frontend/js/library.js": ("library",),
    "frontend/js/documents.js": ("documents",),
}


def test_every_wired_surface_still_reports_its_own_failures() -> None:
    for name, whats in FAILING_SURFACES.items():
        #: "frontend/js/app.js" is the app's code, every piece of it.
        js = app_js_text() if name == "frontend/js/app.js" else (ROOT / name).read_text(encoding="utf-8")
        for what in whats:
            assert f'"{what}"' in js and "surfaceFailed(" in js, (
                f"{name} no longer reports a failed read for {what!r}: a surface "
                "that cannot read its data must say so rather than draw its empty "
                "state (DESIGN.md, the recipe index)"
            )
        #: Paired, always. A surface that can enter the failed state and never
        #: leave it is worse than one that never enters it: the message stays
        #: over a working surface until the tab is rebuilt.
        assert "surfaceRecovered(" in js or "loadSurface(" in js, (
            f"{name} calls surfaceFailed with nothing that clears it again "
            "(DESIGN.md, the recipe index)"
        )


def test_the_failed_state_is_built_in_exactly_one_place() -> None:
    app = app_js_text()
    assert app.count('classList.add("is-failed")') == 1, (
        "the failed state is drawn by surfaceFailed alone; a second builder is "
        "how the empty states came to disagree in the first place"
    )
# --- two panes showing one document (DESIGN.md, "Two views of one document") --


def test_the_rendered_blocks_carry_the_line_they_came_from() -> None:
    """The split view's scroll map is a contract across two files: app.js's
    `renderMarkdown` writes `data-src-line` on every block it draws, and
    documents.js's `docScrollAnchors` reads it. Neither half is any use alone,
    and the failure when one goes is silent: the map finds no anchors, falls
    back to the scroll fraction, and the panes are a screenful apart again
    with nothing in the console to say why.

    Measured before the stamps existed: on a document of five sections with a
    table, a code fence and a list in each, the preview was 282, 292, 266, 404
    and 550px out at the five headings, growing downwards because every block
    that takes a different amount of room in the two panes shifts everything
    below it. With them: 0, 75, 0, 0, 0, and the 75 is the editor landing 21px
    short of where the probe asked it to scroll, not the map.
    """
    app_js = app_js_text()
    documents_js = (ROOT / "frontend" / "js" / "documents.js").read_text(encoding="utf-8")
    assert "dataset.srcLine = String(" in app_js, (
        "renderMarkdown must stamp each block with the source line it came "
        "from, or the split view has nothing to line its panes up by"
    )
    assert "dataset.srcLine" in documents_js, (
        "documents.js must read the stamps; a stamp nothing reads is dead "
        "markup on every surface that renders markdown"
    )
    anchors = _function_body(documents_js, "docScrollAnchors")
    #: **Rects, never `offsetTop`** (INBOX 281). The mapping was right the
    #: first time and the measurement of where a block sits was not:
    #: `offsetTop` is taken from the nearest positioned ancestor, and measured
    #: on a real document it ran 218px past the truth at 1440, 230px at 1024,
    #: and 146px once the sidebar was collapsed and a positioned `#doc-layout`
    #: appeared in between. Every anchor carried the bias, so the preview sat
    #: that far past the line the source was showing at every position. It is
    #: the rule `setDocPage` already states in app.js.
    #: The comments in that function discuss `offsetTop` at length, which is
    #: the point of them, so the check reads the code with the prose taken out.
    anchor_code = "\n".join(
        line for line in anchors.splitlines() if not line.lstrip().startswith("//")
    )
    assert "offsetTop" not in anchor_code, (
        "docScrollAnchors must not read offsetTop: it is measured from the "
        "nearest positioned ancestor, not from the pane, and the bias between "
        "them lands on every anchor"
    )
    assert "getBoundingClientRect()" in anchor_code and "preview.scrollTop" in anchor_code, (
        "a block's place in the pane is its rect corrected by the pane's own "
        "rect and scroll"
    )
    assert "clientWidth" in anchor_code, (
        "the cache token has to carry both panes' widths: a pane that changes "
        "width rewraps every paragraph in it, and it can do that without "
        "changing either scroll height"
    )
    assert "docPreviewLineShift" in anchors, (
        "the stamps count lines in the string the preview rendered, which has "
        "the title prepended and the frontmatter taken off: the shift has to "
        "be undone or every titled document lines up two lines out"
    )
    assert "lineBlockAt(" in _function_body(documents_js, "docSourceLineTop"), (
        "CodeMirror only renders the lines near the viewport, so coordsAtPos "
        "answers null for exactly the off-screen anchors this table is built "
        "from; lineBlockAt reads the height map, which covers the document"
    )
    sync = _function_body(documents_js, "syncDocScroll")
    assert "docScrollAnchors(" in sync and "docMapThroughAnchors(" in sync, (
        "the sync must go through the anchor map, with the scroll fraction "
        "kept only for the case where there are no anchors to read"
    )


# --- the guided tour (DESIGN.md, "A guided tour of the interface") ------------

TOUR_JS = ROOT / "frontend" / "js" / "tour.js"
TOUR_TABLE = re.compile(r"const TOUR_SECTIONS = \[(.*?)\n\];", re.S)
TOUR_STEP = re.compile(r"\{\s*target: \"([^\"]+)\",\s*side: \"([a-z]+)\",(.*?)\n      \}", re.S)


def _tour_steps() -> list[tuple[str, str, str]]:
    js = TOUR_JS.read_text(encoding="utf-8")
    table = TOUR_TABLE.search(js)
    assert table, "TOUR_SECTIONS not found in tour.js; has the tour's table moved?"
    steps = TOUR_STEP.findall(table.group(1))
    assert steps, "TOUR_SECTIONS declares no steps, or its step shape has changed"
    return steps


def test_every_tour_step_points_at_an_element_that_exists() -> None:
    """A step that names a selector nothing matches is a card pointing at
    nothing, and the app cannot tell you so: `querySelector` answers null and
    the step is silently dropped at runtime.

    The runtime drop is deliberate and is what keeps the tour honest on a
    narrow window (DESIGN.md's row: a hidden element loses its step and the
    counter renumbers). This lint is the other half: dropped because the
    control is hidden *right now* is correct, dropped because somebody renamed
    an id six months ago is a step nobody will ever see again, and only a read
    of the markup can tell the two apart.
    """
    markup = (ROOT / "frontend" / "index.html").read_text(encoding="utf-8")
    ids = set(re.findall(r'\sid="([^"]+)"', markup))
    # The leading id of a compound selector is checked too: a step pointing
    # into a list the tab draws ("#library-grid .library-card-menu > button")
    # has no stable id of its own, but the list it lives in has to exist.
    missing = [
        target
        for target, _side, _rest in _tour_steps()
        if (lead := re.match(r"#([\w-]+)", target)) and lead.group(1) not in ids
    ]
    assert not missing, (
        "tour steps name elements that are not in index.html: "
        f"{sorted(missing)}. A step is a real element plus a sentence "
        "(DESIGN.md, the recipe index)"
    )


def test_every_tour_step_says_where_it_sits_and_what_it_says() -> None:
    """A step is a selector, a side and one sentence, and the side has to be
    one of the four the placer knows how to flip and clamp. A fifth spelling
    would fall through `tourCandidates` to the preferred side alone, which is
    how a card ends up over the thing it is describing."""
    for target, side, rest in _tour_steps():
        assert side in {"top", "bottom", "left", "right"}, (
            f"{target} asks for side {side!r}; the placer knows top, bottom, "
            "left and right"
        )
        assert "title:" in rest and "text:" in rest, (
            f"{target} has no title or no text: a step is an element plus a "
            "sentence (DESIGN.md, the recipe index)"
        )


def test_the_tour_card_is_placed_by_the_measure_and_correct_rule() -> None:
    """DESIGN.md: a popup placed in the window's own coordinates sets its
    position, measures it, and corrects by the difference.

    The same rule `docPlaceFixed` and `clampToolbarMenu` are held to above, and
    for the same measured reason: a `position: fixed` element takes its frame
    from the nearest ancestor carrying a `filter`, and `.card` carries one
    whenever the background art is on, which is how a word menu asked for
    `left: 952` and drew at 1245.

    **The check moved from one frame after the write to every frame the tour
    is up, and this test moved with it** (INBOX 426 y). A single read-back a
    frame later caught a tab switch mid-settle and left its own nudge in
    ("tour-spot asked for 336,275, drew at 1128,4"). `tourPlaceFixed` now
    records the box it asked for, and `tourWatchFrame` measures what was
    drawn on every frame and places again, from a fresh origin, when the two
    differ: the same set, measure, correct, held for as long as it takes.
    """
    js = TOUR_JS.read_text(encoding="utf-8")
    body = _function_body(js, "tourPlaceFixed")
    wrote = body.index(".style.left")
    assert "_tourWant" in body[wrote:], (
        "tourPlaceFixed must record the box it asked for, so what was drawn "
        "can be checked against it (DESIGN.md, the recipe index)"
    )
    watch = _function_body(js, "tourWatchFrame")
    assert "getBoundingClientRect()" in watch and "_tourWant" in watch, (
        "tourWatchFrame must measure what was drawn against what was asked for"
    )
    assert "tourPosition()" in watch, "and place the step again when they differ"
    for name in ("tourPosition", "tourSpotlight"):
        assert "tourPlaceFixed(" in _function_body(js, name), (
            f"{name} must place through tourPlaceFixed, or the correction is "
            "one function away from the code that needs it"
        )


def test_the_tours_dim_never_covers_the_control_it_describes() -> None:
    """The point of the whole surface: the described control is the one bright
    thing on screen.

    A sheet over the page with a highlight drawn on the control is the shape
    this must not become, because the control is then behind a dim layer and
    the tour is the centred slide carousel with extra steps. The cut-out is
    `.tour-spot`: no background of its own and no pointer events, so nothing of
    the tour's is ever drawn on top of the thing being pointed at.

    **The dim moved off this element on 2026-09-21 and this test moved with
    it.** It used to be `.tour-spot`'s own `box-shadow`, spread 100vmax, and
    this test pinned exactly that: an implementation, not the invariant. One
    shadow's reach depends on `vmax` and on its own corner radius inflated by
    the spread, and no probe could read it, which is how the owner came to
    report an undimmed strip three times against a green suite. The dim is now
    the four `.tour-block-panel`s that already tile the window around the hole,
    so what this test asserts is the part that must never change (the spot is a
    hole, not a highlight) plus where the scrim now has to be. Both the old
    shape and a sheet over the whole window still fail it.
    """
    css = "\n".join(path.read_text(encoding="utf-8") for path in CSS)
    rule = re.search(r"\n\.tour-spot \{(.*?)\n\}", css, re.S)
    assert rule, ".tour-spot has no rule; has the tour's cut-out moved?"
    body = rule.group(1)
    assert "background: transparent" in body, (
        ".tour-spot must paint no background: the bright area is the page "
        "itself showing through the hole in the dim"
    )
    assert "pointer-events: none" in body, (
        ".tour-spot must not take pointer events: #tour-block is what stops "
        "the page being used mid-step"
    )
    assert "var(--scrim)" not in body, (
        "the dim must not be cast out of the cut-out again: one shadow's reach "
        "is unmeasurable, which is why the owner reported a lit strip three "
        "times. It belongs on the four .tour-block-panel rectangles"
    )
    panel = re.search(r"\n\.tour-block-panel \{(.*?)\n\}", css, re.S)
    assert panel, ".tour-block-panel has no rule; where is the tour's dim?"
    #: The scrim at 60%: the owner, 2026-10-10, "on the tour it is hard to
    #: see the other features around the things highlighted". Still the
    #: scrim, still on the four panels.
    assert "background: color-mix(in srgb, var(--scrim) 60%, transparent)" in panel.group(1), (
        "the four panels around the hole are the dim, in the app's scrim "
        "colour: they are the rectangles tourdim.js can actually measure"
    )
    block = re.search(r"\n\.tour-block \{(.*?)\n\}", css, re.S)
    assert block and "background: transparent" in block.group(1), (
        "their container must stay transparent, or the dim is a sheet over the "
        "whole window again and the cut-out is a highlight drawn on top of one"
    )


def test_the_tours_dim_leaves_the_control_pressable() -> None:
    """The owner, 2026-09-20: "it doesnt let the user click the highglighted
    items". `#tour-block` was `inset: 0` with a background of its own, and
    `document.elementFromPoint` at the centre of all fifteen steps answered
    `tour-block` rather than the control: the tour pointed at Save and then ate
    the press, which teaches the person that Save is broken.

    The shape that cannot come back is one element over the whole window taking
    presses. The dim is four panels laid out around the hole, and the hole is
    left to the page, so the container itself must take no presses and the
    panels must take them instead.
    """
    css = "\n".join(path.read_text(encoding="utf-8") for path in CSS)
    block = re.search(r"\n\.tour-block \{(.*?)\n\}", css, re.S)
    assert block, ".tour-block has no rule; has the tour's press-catcher moved?"
    assert "pointer-events: none" in block.group(1), (
        ".tour-block spans the window, so it must take no presses itself: the "
        "four .tour-block-panel children take them and the hole between them "
        "is left to the control the step is about"
    )
    panel = re.search(r"\n\.tour-block-panel \{(.*?)\n\}", css, re.S)
    assert panel, (
        ".tour-block-panel has no rule: the dim is four panels around the "
        "hole (DESIGN.md, the recipe index)"
    )
    assert "pointer-events: auto" in panel.group(1), (
        "a .tour-block-panel is the thing that stops the page being used "
        "mid-step, so it has to take presses"
    )
    js = TOUR_JS.read_text(encoding="utf-8")
    panels = _function_body(js, "tourBlockPanels")
    for side in ("tour-block-top", "tour-block-right", "tour-block-bottom", "tour-block-left"):
        assert side in panels, (
            f"tourBlockPanels does not place {side}: all four are laid out "
            "from the cut-out's own rectangle, on every reflow, or the hole "
            "drifts off the control"
        )
    assert "tourBlockPanels(" in _function_body(js, "tourSpotlight"), (
        "the panels are placed by the one function that already runs on every "
        "reflow, or a scroll leaves them where the control used to be"
    )
    markup = (ROOT / "frontend" / "index.html").read_text(encoding="utf-8")
    assert markup.count('class="tour-block-panel"') == 4, (
        "the tour's dim is four panels around the hole, no more and no fewer"
    )


def test_the_tour_card_has_a_visible_way_out() -> None:
    """The owner, 2026-09-20: "it has no visible way to exit or quit it like a
    button or smth so I had to guess by pressing the escape button". Skip and
    Escape both ended the tour already; neither read as the exit, because Skip
    beside Back and Next reads as "not this part". The X in the card's head is
    where every other panel in this app keeps its close, and all three stay:
    they are one act reached three ways."""
    markup = (ROOT / "frontend" / "index.html").read_text(encoding="utf-8")
    close = re.search(r'<button id="tour-close"[^>]*>', markup, re.S)
    assert close, "the tour card has no #tour-close: the way out has to be visible"
    assert "icon-only" in close.group(0) and "ghost" in close.group(0), (
        "#tour-close is the app's own icon-only ghost button, not a new shape"
    )
    assert 'aria-label="Close the tour"' in close.group(0), (
        "an icon-only button says what it does in its accessible name"
    )
    js = TOUR_JS.read_text(encoding="utf-8")
    assert 'getElementById("tour-close")' in js and "tourClose(false)" in js, (
        "#tour-close must be wired to tourClose, or the button is a picture "
        "of a way out"
    )
    assert 'key === "Escape"' in js, "Escape still ends the tour"
    assert 'getElementById("tour-skip")' in js, "Skip stays: it is the same act"


def test_a_tour_step_waits_for_the_tab_it_switched_to() -> None:
    """A tab switch is not finished when `switchTab` resolves: the tab's own
    content is fetched after it, and for a beat the element the step names is
    in the DOM at zero height. Measuring once and dropping the step then is the
    owner's "it doesnt automatically switch pages on different steps" seen from
    outside: the steps that would have moved the tour quietly stop existing.

    And the guard that decides whether to switch at all reads the markup, not
    `localStorage`: a restore or a history step leaves the stored name and the
    painted tab disagreeing, and the tour then skips the switch.
    """
    js = TOUR_JS.read_text(encoding="utf-8")
    show = _function_body(js, "tourShow")
    assert "await tourWaitForTarget(" in show, (
        "tourShow must wait for the step's target before judging it missing, "
        "or a tab that loads its content costs every step inside it"
    )
    wait = _function_body(js, "tourWaitForTarget")
    assert "tourVisible(" in wait and "tourFrame(" in wait, (
        "the wait polls per frame for a visible target; a frame is when "
        "layout has settled"
    )
    assert "TOUR_WAIT_MS" in wait, "the wait has to end: a target that never arrives costs its step"
    navigate = _function_body(js, "tourNavigate")
    assert "tourActiveTab()" in navigate, (
        "which tab is showing is asked of the markup (tourActiveTab), never "
        "of localStorage alone, or the switch is skipped on a disagreement"
    )
    active = _function_body(js, "tourActiveTab")
    assert "#tab-bar" in active, "tourActiveTab reads the pressed tab button"


def test_the_cut_out_is_never_drawn_where_it_cannot_be_seen() -> None:
    """INBOX 280, the owner at about 2000x1140: "this happens when I press next
    on the welcome tour", with the whole page dimmed except a strip about 100px
    wide at the right edge, no card and nothing highlighted.

    The dim is the cut-out's own `box-shadow`, so a cut-out placed outside the
    window darkens everything and highlights nothing. It got there through the
    invalid-value trap CLAUDE.md names: with a target off the right edge,
    `left` clamps to the target and `right` clamps to the window, so
    `right - left` is **negative**, `width: -994px` is dropped as invalid, and
    the element silently keeps the width it had on the previous step. Measured
    at 2000x1140 with the target moved to x 3000: the cut-out was placed at
    2994 carrying the previous step's 708px width.

    Two rules come out of it, and both are here because neither is visible in
    the output of the other: the box is checked before it is written, and a
    step whose control is not really on screen is dropped rather than drawn.
    """
    js = TOUR_JS.read_text(encoding="utf-8")
    spot = _function_body(js, "tourSpotlight")
    assert "if (width < 1 || height < 1)" in spot, (
        "tourSpotlight must check the clamped box before writing it: a "
        "negative width is invalid CSS, is dropped, and leaves the previous "
        "step's size on an element that has moved"
    )
    assert "tourClearSpotlight()" in spot and "return false" in spot, (
        "a box that cannot be drawn draws no cut-out at all, rather than one "
        "in the wrong place"
    )
    assert "return true" in spot, "and the caller has to be told which happened"

    position = _function_body(js, "tourPosition")
    assert "tourSpotlight(" in position and "if (!lit)" in position, (
        "tourPosition must place the card differently when there is no "
        "cut-out: beside nothing is not a position"
    )

    show = _function_body(js, "tourShow")
    usable = _function_body(js, "tourUsable")
    assert "tourUsable(el)" in show and "tourOnScreen(el)" in usable, (
        "a step whose control is not on screen after the wait is dropped, so "
        "the counter renumbers and the tour moves to one that can be pointed "
        "at (DESIGN.md, the recipe index)"
    )
    reflow = _function_body(js, "tourReflow")
    assert "tourOnScreen(" in reflow, (
        "and a control that leaves the window under the tour costs its step "
        "too, or the card hangs on beside a rectangle that has gone"
    )

    on_screen = _function_body(js, "tourOnScreen")
    assert "clientWidth" in on_screen and "clientHeight" in on_screen, (
        "on screen is measured against the window, not against the document"
    )
    assert "TOUR_ON_SCREEN_MIN" in on_screen, (
        "a few pixels inside the edge is not something to point at; the "
        "threshold is named so it can be argued with"
    )


def test_a_tour_step_with_nothing_to_point_at_is_dropped() -> None:
    """A control hidden by a responsive rule, or gone from the markup, must
    cost its step rather than leave a card anchored to a zero-sized box in the
    corner of the window. Dropping it is also what keeps "3 of 7" true: the
    counter is drawn from the run's own steps, which shrink with it. Since
    the sections chain (the owner, 2026-09-23), it counts the current
    section's steps in the run, so "Graph, 2 of 4" is still a count of cards
    that will really be shown."""
    js = TOUR_JS.read_text(encoding="utf-8")
    show = _function_body(js, "tourShow")
    assert "tourVisible(" in show and "splice(" in show, (
        "tourShow must check the element is visible and drop the step when it "
        "is not (DESIGN.md, the recipe index)"
    )
    render = _function_body(js, "tourRender")
    assert "tourSectionPlace(run)" in render, (
        "the counter must be drawn from the run's own steps, or it promises "
        "steps the tour has already dropped"
    )
    place = _function_body(js, "tourSectionPlace")
    assert "run.steps.filter(" in place and "sectionId" in place, (
        "the per-section count is the run's steps in this section, not the "
        "table's: a dropped step must leave its section's count"
    )


def test_a_tour_steps_second_control_exists_and_says_where_it_went() -> None:
    """On a phone Settings and Timeline live in More, and a step naming the
    gear or the Timeline tab was dropped mid-run there, renumbering the
    counter under the person (measured 2026-09-23 at 390x844: 1 of 15, then
    4 of 14, then 10 of 13). A step's `or` is the control it moved behind, and
    its `orText` is what the card says while pointing at that one instead: a
    card that describes a gear while lighting a button labelled More is the
    tour describing UI that is not there."""
    js = TOUR_JS.read_text(encoding="utf-8")
    table = TOUR_TABLE.search(js).group(1)
    markup = (ROOT / "frontend" / "index.html").read_text(encoding="utf-8")
    ids = set(re.findall(r'\sid="([^"]+)"', markup))
    ors = re.findall(r'\bor: "([^"]+)",\s*orText: "([^"]+)"', table)
    assert len(ors) == len(re.findall(r"\bor: \"", table)), (
        "every step with an `or` control carries an `orText` right after it"
    )
    assert ors, "Settings and Timeline need their phone controls (More)"
    for selector, text in ors:
        assert selector.startswith("#") and selector[1:] in ids, (
            f"the `or` control {selector} is not in index.html"
        )
        # More for the phone's tab overflow and a dock's ⋯; the others (the
        # whiteboard's Tools opener, the reminder form's sheet) are checked by
        # the sweep, which reads each card's words beside the control it lit.
        if selector in ("#phone-more-btn", "#library-boards-more"):
            assert "More" in text, f"{selector}'s words must say the control is in More: {text!r}"
    assert "run.step.orText" in _function_body(js, "tourRender"), (
        "tourRender shows `orText` when the step is pointing at its `or` control"
    )
    assert "tourResolve(" in _function_body(js, "tourReflow"), (
        "a resize across the phone breakpoint moves the step between its two "
        "controls rather than dropping it"
    )


def test_the_tour_closes_what_is_open_and_will_not_point_under_it() -> None:
    """The fault behind "completely broken on all the slides except the first
    one" (the owner, 2026-09-23), measured before this: with the Atlas guide,
    the command palette, the features browser or the shortcut sheet open, all
    four basics steps had the overlay on top of their control, so the hole in
    the dim showed the overlay. Laid out and inside the window were both true;
    in front was not."""
    js = TOUR_JS.read_text(encoding="utf-8")
    clear = _function_body(js, "tourClearTheWay")
    for closer in ("closeSettingsModal", "closePalette", "closeFeatures", "closeShortcuts", ".sheet-close"):
        assert closer in clear, f"tourClearTheWay must close what {closer} closes"
    assert "tourClearTheWay(step)" in _function_body(js, "tourNavigate"), "every step clears the way first (keeping Settings only for a Settings step)"
    assert "tourClearTheWay()" in _function_body(js, "openTour"), "and so does opening the tour"
    usable = _function_body(js, "tourUsable")
    assert "tourCovered(el)" in usable, "a control with something drawn over it is not usable"
    covered = _function_body(js, "tourCovered")
    assert "elementsFromPoint" in covered and "#tour-block" in covered, (
        "covered is asked of what is on top, skipping the tour's own layers"
    )


def test_the_tour_count_is_settled_before_the_first_card() -> None:
    """A chrome step (no tab) that is not laid out now never will be during
    this run, so it is left out before the count is written: the counter says
    the same total from the first card to the last."""
    js = TOUR_JS.read_text(encoding="utf-8")
    body = _function_body(js, "openTour")
    assert "step.tab || step.notes || tourVisible(tourResolve(step).el)" in body


def test_typing_in_the_lit_control_is_not_a_tour_key() -> None:
    """The hole is the page and the capture box step invites typing: the
    arrows and Enter inside a field outside the card belong to the field."""
    js = TOUR_JS.read_text(encoding="utf-8")
    start = js.index('document.addEventListener(\n  "keydown"')
    handler = js[start : js.index("true\n);", start)]
    assert "isContentEditable" in handler and "TEXTAREA" in handler and '!target.closest("#tour-card")' in handler


def test_the_tour_is_switched_on_and_its_doors_are_live() -> None:
    """The owner switched the tour off on 2026-09-21 until it was fixed; it is
    on again, and every door reads the one flag rather than being disabled on
    its own (the About button was the door that got left open last time)."""
    js = TOUR_JS.read_text(encoding="utf-8")
    assert re.search(r"^const TOUR_ENABLED = true;$", js, re.M), "TOUR_ENABLED must be true"
    app = app_js_text()
    assert re.search(r"aboutTour\.disabled = true", app), "About's door is still guarded by the flag"
    guard = app[: app.index("aboutTour.disabled = true")].rsplit("\nif (", 1)[1]
    assert "TOUR_ENABLED" in guard, "About's button is disabled only when the flag is off"
    assert "if (!TOUR_ENABLED)" in _function_body(js, "renderTourReplay"), (
        "the replay strip is disabled only when the flag is off"
    )


def test_a_new_tour_section_needs_no_new_code() -> None:
    """One table, or the replay strip and the tour disagree about what exists.

    DESIGN.md's row says a new subject is a section in TOUR_SECTIONS and never
    a second tour. That only holds while everything that offers the tour reads
    that table: the Settings buttons, and the run itself.
    """
    js = TOUR_JS.read_text(encoding="utf-8")
    for name in ("renderTourReplay", "tourStepsFor"):
        assert "TOUR_SECTIONS" in _function_body(js, name), (
            f"{name} must build itself from TOUR_SECTIONS, so a section added "
            "to that table arrives with no markup and no handler to write"
        )


def _tour_sections() -> dict[str, list[tuple[str, str, str]]]:
    """Each section's id, mapped to its steps as `_tour_steps` reads them."""
    table = TOUR_TABLE.search(TOUR_JS.read_text(encoding="utf-8")).group(1)
    starts = [(m.start(), m.group(1)) for m in re.finditer(r'\n  \{\n    id: "([a-z]+)",', table)]
    out = {}
    for i, (start, section_id) in enumerate(starts):
        end = starts[i + 1][0] if i + 1 < len(starts) else len(table)
        out[section_id] = TOUR_STEP.findall(table[start:end])
    return out


def test_every_main_feature_has_a_tour_section_that_walks_into_it() -> None:
    """The owner, 2026-09-23: "they dont guide me through the other main
    features". A section per feature, three to five cards on its own
    controls, and a section that names a tab has to switch to it: the old
    sections pointed at the tab *buttons* and described what was behind
    them."""
    sections = _tour_sections()
    for wanted in ("basics", "notes", "chat", "graph", "library", "boards", "maps",
                   "timeline", "reminders", "settings", "status"):
        assert wanted in sections, f"the tour has no {wanted!r} section"
    for section_id, steps in sections.items():
        # A pair of `media` steps is one card on either side of a breakpoint.
        wide = [s for s in steps if "(max-width" not in s[2]]
        assert 3 <= len(wide) <= 5, f"{section_id} has {len(wide)} cards; a section is three to five"
        for target, _side, rest in steps:
            assert "#tab-btn-" not in target, (
                f"{section_id} points at a tab button ({target}); a section "
                "walks into its feature and points at the feature's controls"
            )
            text = re.search(r'\btext: "([^"]+)"', rest).group(1)
            assert len(text) <= 140, f"{target}: one or two short sentences, not {len(text)} characters"


def test_the_tours_sections_chain_into_each_other() -> None:
    """The owner: "If I want to do the other sections of the tour, I have to
    go into the help settings and click the other tour section buttons". A
    run starts at a section and carries on through every later one; the last
    card of a section says "Next: <section>" beside a Finish."""
    js = TOUR_JS.read_text(encoding="utf-8")
    steps_for = _function_body(js, "tourStepsFor")
    assert "TOUR_SECTIONS.slice(from)" in steps_for, (
        "a run started at a section includes every section after it"
    )
    render = _function_body(js, "tourRender")
    assert "`Next: ${place.next}`" in render and '"Finish"' in render, (
        "the last card of a section offers the next one by name, and Finish"
    )
    skip = js[js.index('getElementById("tour-skip").addEventListener'):]
    skip = skip[: skip.index(");\n") + 3]
    assert "atSectionEnd" in skip and "tourClose(" in skip, (
        "Finish ends the tour as finished (remembered, with its toast), Skip as skipped"
    )


def test_the_tour_never_makes_a_board_or_a_map() -> None:
    """Never create data: a tour that walks into mind maps opens the newest
    one there is, and in a notebook with none it points at New mind map and
    says what that makes. So nothing on the tour's way to a board writes."""
    js = TOUR_JS.read_text(encoding="utf-8")
    for name in ("tourWhiteboard", "tourContext", "tourPrepareSection", "tourNavigate"):
        body = _function_body(js, name)
        for writer in ("method:", "POST", "wbCreateBoard", "createBoard"):
            assert writer not in body, f"{name} must only read ({writer!r} found)"
    sections = _tour_sections()
    map_steps = [rest for target, _side, rest in sections["maps"] if 'wb: "map"' in rest]
    assert map_steps and all('need: "map"' in rest for rest in map_steps), (
        "every step that opens a map needs one to exist"
    )
    needs = _function_body(js, "tourPrepareSection")
    assert "TOUR_NEEDS" in needs, "a section's needs are settled before its first card"


# --- the phone top bar (UI_MODERNISATION_PLAN Phase 11 item 1) ---------------
#
# Below 600 the four everyday-and-session squares (theme, settings, lock,
# quit) become the rows of one `kebabMenu`, so the bar is three controls and
# fits 320 (it was six, and scrolled the page sideways by one button). The
# suite cannot measure that; `scratchpad/ui-sweeps/phonehead.js` does. What
# it can check is that the arrangement is the recipe's: the menu is built by
# `kebabMenu`, the swap is one stylesheet band, and nothing the desktop has
# is dropped rather than moved.

def test_the_phone_top_bar_menu_is_the_kebab_recipe_and_hides_nothing():
    app = app_js_text()
    start = app.index("function initPhoneHeaderMore()")
    body = app[start : app.index("initPhoneHeaderMore();", start)]
    assert "kebabMenu(" in body, "the phone header menu must be the kebabMenu recipe"
    for verb in ("toggleTheme()", "openSettingsModal()", "lockNow()", "quitApp()"):
        assert verb in body, f"the phone header menu lost {verb}, which the desktop bar has"

    css = (ROOT / "frontend" / "css" / "10-responsive.css").read_text(encoding="utf-8")
    band = css[css.index("Phase 11 item 1: the phone top bar") :]
    band = band[: band.index("}\n}") + 3]
    assert "@media (max-width: 599.98px)" in band
    for ident in ("#theme-btn", "#settings-btn", "#lock-btn", "#quit-btn"):
        assert ident in band, f"{ident} is not swapped for the menu on a phone"
    assert "#header-more" in band


def test_every_sidebar_gets_the_phone_opener_from_the_one_function():
    """Phase 11 items 2 and 3: below 600 the sidebar rail goes and each
    sidebar is opened from a `.dock-nav` button in its own head, mounted by
    `mountPhoneSidebarOpeners` for every id in `SIDEBAR_IDS`. A fourth
    sidebar added without a row here would keep a rail on the phone that
    the other three no longer have."""
    app = app_js_text()
    ids = re.search(r"const SIDEBAR_IDS = \[([^\]]*)\]", app)
    assert ids, "SIDEBAR_IDS is not where this lint expects it"
    sidebars = set(re.findall(r'"([^"]+)"', ids.group(1)))
    rows = re.search(r"const PHONE_SIDEBAR_OPENERS = \[(.*?)\n\];", app, re.S)
    assert rows, "PHONE_SIDEBAR_OPENERS is missing"
    covered = set(re.findall(r'aside: "([^"]+)"', rows.group(1)))
    assert covered == sidebars, f"sidebars without a phone opener: {sorted(sidebars - covered)}"
    css = (ROOT / "frontend" / "css" / "10-responsive.css").read_text(encoding="utf-8")
    band = css[css.index("Phase 11 items 2 and 3: no rail on a phone") :]
    for ident in sidebars:
        assert f"#{ident}:not(.sidebar-sheet-open)" in band, f"#{ident} keeps its rail on a phone"


def test_the_row_swipe_presses_the_rows_own_actions():
    """Phase 11 item 2, the HIG rule: a swipe action matches the row's menu.
    The swipe may only reach the star button the row shows and the one bin
    function the row menu's own item calls; a swipe that grew an action of
    its own would be the third copy of a verb, and the first one nobody can
    see."""
    app = app_js_text()
    start = app.index("function initRowSwipe(list, actions)")
    body = app[start : app.index("// --- the note page", start)]
    assert '".favourite-btn"' in body
    assert "binNoteWithUndo(" in body
    assert 'input[type="checkbox"]' in body, "the reminder swipe presses the row's own Done"
    assert "fetch(" not in body and "api(" not in body, "the swipe calls the row's actions, never the API"
    menu = app[app.index('label: "ph:trash Move to bin"') :][:200]
    assert "binNoteWithUndo(" in menu, "the menu row and the swipe must call the same function"
    assert "favourite-btn" in app[app.index("function favouriteButton(") :][:800]


def test_every_right_click_menu_has_a_long_press_twin():
    """Phase 11 item 9: a finger has no second button, so every contextmenu
    listener in app.js, documents.js, graph-canvas.js and whiteboard.js is
    matched by a `wireLongPress` call opening the same thing. Counted per
    file, since the two are always written side by side. graph-canvas.js
    joined the count with Phase 11 item 4 (the hold that opens the node menu,
    and arms the lasso on the empty map) and whiteboard.js with item 7.

    whiteboard.js has a fifth right-click, bound through d3 as
    `.on("contextmenu.wbctx")` on a selection that is rebound on every
    render, and it keeps its own hold for that reason: d3's namespaced `.on`
    replaces a listener per rebind, while `addEventListener` would stack one
    per render. It is not counted here because the pattern above does not
    match it, which is the honest state of it rather than an oversight.
    """
    #: whiteboard-map.js since the mind map layer was split out of
    #: whiteboard.js (2026-09-24); its node and edge menus came with it.
    for name in ("app.js", "documents.js", "graph-canvas.js", "whiteboard.js", "whiteboard-map.js"):
        text = frontend_text(name)
        right_clicks = len(re.findall(r'addEventListener\(\s*"contextmenu"', text))
        #: The selection bubble's return is not a menu: a finger already has the
        #: system's own selection bar, and the helper steps aside for touch.
        right_clicks -= text.count('addEventListener("contextmenu", selectionRestoreOnContextMenu)')
        calls = len(re.findall(r"\bwireLongPress\(", text))
        holds = calls - (1 if name == "app.js" else 0)  # app.js holds the definition
        assert right_clicks == holds, f"{name}: {right_clicks} right-click menus, {holds} long-press twins"

def test_a_selection_bubble_returns_on_one_right_click_helper():
    """Owner 2026-10-11: a dismissed selection bubble comes back on a right-click
    of the selection. One helper owns it; a bubble is built in two files only."""
    selection = frontend_text("selection.js")
    assert len(re.findall(r'addEventListener\(\s*"contextmenu"', selection)) == 1
    assert 'addEventListener("contextmenu", selectionRestoreOnContextMenu)' in selection
    body = selection[selection.index("function selectionRestoreOnContextMenu(") :][:1800]
    for needle in ("defaultPrevented", '"touch"', "selectionBarShow(", "syncSelectionPopup()", "event.preventDefault()"):
        assert needle in body, needle
    builders = sorted(
        p.name
        for p in (ROOT / "frontend" / "js").glob("*.js")
        if re.search(r'className = "selection-(?:popup|bar) ', p.read_text(encoding="utf-8"))
    )
    assert builders == ["editor.js", "selection.js"], f"a new selection bubble must be shown by selectionRestoreOnContextMenu: {builders}"
    assert "selectionRestoreOnContextMenu" in (ROOT / "docs" / "DESIGN.md").read_text(encoding="utf-8")


# A `<details>` in index.html that heads no named family: prose disclosures in
# the Help guide, the chat's thinking boxes and the like, which take their
# summary from their own surroundings. Frozen, like the hand-built menus
# above: a folded group of settings is `details.settings-fold`, and a new
# unnamed one is a second disclosure shape nobody styled.
BARE_DISCLOSURES = 14

# The families 08-consistency.css dresses as "a heading with a chevron" rather
# than as a control in a row. Every one of its four disclosure rules has to
# name the same set: a family on the flat rule but not the chevron rule is a
# fold with no disclosure mark, and one on the chevron rule but not the hover
# rule loses its pointer feedback.
FOLD_RULES = (
    "> summary:not(.icon-only):not(.icon-button) {",
    "> summary::-webkit-details-marker",
    "> summary:not(.icon-only):not(.icon-button)::before",
    "> summary:not(.icon-only):not(.icon-button):hover",
)


def _fold_families(css: str, marker: str) -> set[str]:
    """The container classes named on the rule `marker` belongs to.

    The selector list runs from the end of whatever came before (a rule's
    closing brace) to this rule's opening one, with its own comments taken
    out: a comment above these rules quotes selectors while explaining them.
    """
    hit = css.index(marker)
    brace = css.index("{", hit)
    start = max(css.rfind("}", 0, hit), css.rfind("*/", 0, hit)) + 1
    block = re.sub(r"/\*.*?\*/", "", css[start:brace], flags=re.S)
    return set(re.findall(r"\.([a-z-]+)(?=(?:\[open\])? (?:details )?> summary)", block))


def test_a_folded_settings_group_is_keyed_and_remembered() -> None:
    """A whole Settings group that folds carries a unique key (DESIGN.md).

    `wireSettingsFolds` keeps each fold's open state under its
    `data-fold-key`, so a key used twice would open and close two groups
    together, and a keyed `<details>` outside the fold recipe would have no
    chevron. Each long pane's first group starts open, so a pane never opens
    on nothing but closed rows.
    """
    raw = (ROOT / "frontend" / "index.html").read_text(encoding="utf-8")
    markup = re.sub(r"<!--.*?-->", "", raw, flags=re.S)
    keyed = re.findall(r"<details([^>]*data-fold-key=\"([^\"]+)\"[^>]*)>", markup)
    keys = [key for _, key in keyed]
    assert len(keys) == len(set(keys)), f"a fold key used twice: {sorted(keys)}"
    for attrs, key in keyed:
        assert "settings-fold" in attrs, f"{key}: a keyed fold is `details.settings-fold`"
    firsts: dict[str, bool] = {}
    for attrs, key in keyed:
        pane = key.split("-")[0]
        firsts.setdefault(pane, " open" in attrs)
    assert all(firsts.values()), f"a pane whose first fold starts closed: {firsts}"
    js = with_pieces("settings.js")
    assert "wireSettingsFolds();" in js, "the folds' open state is remembered by wireSettingsFolds"


def test_a_folded_group_of_settings_is_the_shared_disclosure_recipe() -> None:
    """One fold, dressed in one place (DESIGN.md, the recipe index).

    The graph's display options panel grew back past its own cap (655px of
    list in a 488px box at 1440x900) and three of its six sections are set
    once and then left. Folding them is the recipe the Settings screen
    already has, `details.settings-fold`, and the point of this lint is that
    the next surface that needs a fold reaches for the same three words
    instead of writing a fourth summary of its own.
    """
    css = (ROOT / "frontend" / "css" / "08-consistency.css").read_text(encoding="utf-8")
    families = [_fold_families(css, marker) for marker in FOLD_RULES]
    for marker, named in zip(FOLD_RULES[1:], families[1:]):
        assert named == families[0], (
            f"the disclosure rule at `{marker}` names {sorted(named)} while the "
            f"flat-summary rule names {sorted(families[0])}; a fold family on one "
            "rule and not another is a fold with no chevron or no hover "
            "(DESIGN.md, the recipe index)"
        )
    assert "settings-fold" in families[0]

    raw = (ROOT / "frontend" / "index.html").read_text(encoding="utf-8")
    markup = re.sub(r"<!--.*?-->", "", raw, flags=re.S)
    bare = 0
    graph_folds = 0
    for attrs in re.findall(r"<details([^>]*)>", markup):
        found = re.search(r'class="([^"]*)"', attrs)
        classes = set(found.group(1).split()) if found else set()
        if "graph-options-fold" in classes:
            graph_folds += 1
            assert "settings-fold" in classes, (
                "a fold in the graph's options panel is the shared "
                "`details.settings-fold` recipe, not a shape of its own"
            )
        if not classes - {"hidden"}:
            bare += 1
    assert bare <= BARE_DISCLOSURES, (
        f"{bare} `<details>` elements in index.html name no family; a folded "
        "group of settings is `details.settings-fold` (DESIGN.md, the recipe "
        "index), and this count may only fall"
    )
    assert graph_folds == 5, (
        "the graph options panel's five tuned-once sections (Physics, Display, "
        "Filter, Groups, Minimap) are folds; see GRAPH_PLAN.md, 'Decision made, 2026-09-20', "
        "'Decision made, 2026-10-04: a Filter fold' "
        "and 'Decision made, 2026-10-04: a Display fold'"
    )


#: **A grip that scales with `--wb-inv-zoom` carries its own anchor**
#: (INBOX 278). `.wb-sketch-rotate-handle` and `.wb-rotate-handle-stem` are
#: scaled by `1 / k` in 07-whiteboard-misc.css so a grip stays one size to the
#: hand, and that rule deliberately leaves `transform-box` at its `view-box`
#: default, which means the origin has to come from the code that knows the
#: board coordinates. The group selection's grip was added without one and the
#: scale resolved about the view box's origin instead: measured at board
#: (680, 1344) at 0.5x and (170, 336) at 2x for a box whose top centre is
#: (340, 672), which is the owner's "off to the top left or right, or below the
#: top border".
#:
#: The count, rather than the proximity: the group's origin is set in
#: `layoutGroupChrome`, which sits above the element it anchors, so "within N
#: lines of the class" would fail on the code that is correct. One
#: `transform-origin` per grip drawn is the invariant, and a fifth grip added
#: without one breaks this.
GRIP_CLASSES = ("wb-rotate-handle-stem", "wb-sketch-rotate-handle")


def test_every_inverse_scaled_grip_sets_its_own_anchor():
    js = (ROOT / "frontend" / "js" / "whiteboard.js").read_text(encoding="utf-8")
    drawn = sum(js.count(f'"{name}"') for name in GRIP_CLASSES)
    anchored = js.count('.style("transform-origin"')
    assert drawn == 4, (
        f"whiteboard.js draws {drawn} inverse-scaled rotate grips, not the 4 "
        "this lint was measured against (one stem and one knob for a single "
        "shape, one of each for a group selection); count the new one and give "
        "it an anchor before raising this"
    )
    assert anchored >= drawn, (
        f"{drawn} rotate grips are drawn and {anchored} anchors are set: a grip "
        "scaled by `--wb-inv-zoom` with no `transform-origin` is scaled about "
        "the SVG view box's origin and leaves the box it belongs to "
        "(INBOX 278, WHITEBOARD_PLAN)"
    )

    css = "\n".join((ROOT / "frontend" / "css" / name).read_text(encoding="utf-8") for name in ("07-whiteboard-misc.css", "library-lazy.css"))
    rule = css.split(".wb-sketch-rotate-handle,\n.wb-rotate-handle-stem {")[1].split("}")[0]
    assert "scale(var(--wb-inv-zoom))" in rule, (
        "the grip rule this lint guards is gone or renamed; the lint and the "
        "rule move together"
    )
    assert "transform-box" not in rule, (
        "this rule keeps `transform-box` at its `view-box` default on purpose, "
        "because the origin is a pair of board coordinates the drawing code "
        "sets; a `fill-box` here would make those origins mean something else"
    )


#: The canvas grips this recipe covers (DESIGN.md, "A grip you drag on a
#: canvas"). Named rather than discovered by pattern, because the point of the
#: list is that a new grip is added to it deliberately: a grip that nobody
#: thought about is exactly the one that ends up a 4px target at 0.3 zoom, or
#: invisible and still eating the press meant for the line under it.
CANVAS_GRIPS = (
    ".wb-resize-handle",
    ".wb-link-endpoint-handle",
    ".wb-link-bend-handle",
    ".wb-link-waypoint-handle",
    ".wb-link-waypoint-add",
    ".wb-link-label-handle",
    ".wb-clone-grip",
    ".wb-map-edge-handle",
)


def test_every_canvas_grip_is_one_size_to_the_hand():
    """A grip is a constant size on screen, whatever the board's zoom is.

    The rule and its reason are written out above the rules themselves in
    07-whiteboard-misc.css, after a link's bend grip was measured at 24px
    across at 2x against the 12px it is at 1x. This is that paragraph as a
    lint, so the next grip added is measured against it rather than after it.
    """
    css = "\n".join((ROOT / "frontend" / "css" / name).read_text(encoding="utf-8") for name in ("07-whiteboard-misc.css", "library-lazy.css"))
    missing = [
        grip for grip in CANVAS_GRIPS
        if "scale(var(--wb-inv-zoom))" not in _rules_for(css, grip)
    ]
    assert missing == [], (
        "these canvas grips scale with the board instead of staying one size "
        "to the hand: " + ", ".join(missing)
    )


def test_a_grip_that_is_invisible_does_not_take_the_pointer():
    """An invisible grip with `pointer-events: auto` swallows the press meant
    for whatever is under it. It has happened twice on the map alone: the
    mid-line `+` in front of a line's hit stroke (it forwards the gesture now),
    and the waypoint grip on the same point as that `+`. So a grip that is
    drawn at `opacity: 0` declares `pointer-events: none` in the same rule, and
    opts back in only where it is revealed.

    A rule inside `@starting-style` is not a drawn state: it is where a fade
    in begins for a grip that has just been revealed (the card grips are
    `display: none` at rest, `tests/test_board_pan_layers.py`), and that grip
    is revealed, so it takes the pointer on purpose. Those blocks are left out
    of the read rather than given a `pointer-events` that would never apply."""
    css = "\n".join((ROOT / "frontend" / "css" / name).read_text(encoding="utf-8") for name in ("07-whiteboard-misc.css", "library-lazy.css"))
    css = re.sub(r"@starting-style\s*\{(?:[^{}]*\{[^{}]*\})*[^{}]*\}", "", css)
    offenders = []
    for grip in CANVAS_GRIPS:
        for rule in _rule_bodies(css, grip):
            if re.search(r"opacity:\s*0\s*;", rule) and "pointer-events: none" not in rule:
                offenders.append(grip)
    assert offenders == [], (
        "these grips are drawn invisible and still take the pointer: "
        + ", ".join(sorted(set(offenders)))
    )


def _rule_bodies(css: str, selector: str) -> list[str]:
    """Every rule body whose selector list names this class exactly.

    Comments are stripped first, and that is not tidiness: this stylesheet
    explains itself at length, and a comment that mentions a `{` (or sits
    between two selectors in one list, as the grip rule's own does) makes a
    brace-counting parse read the file as a different file.
    """
    css = re.sub(r"/\*.*?\*/", "", css, flags=re.S)
    bodies = []
    for match in re.finditer(r"([^{}]+)\{([^{}]*)\}", css):
        selectors = [part.strip() for part in match.group(1).split(",")]
        if any(part.split(":")[0].split(" ")[-1] == selector for part in selectors):
            bodies.append(match.group(2))
    return bodies


def _rules_for(css: str, selector: str) -> str:
    return "\n".join(_rule_bodies(css, selector))


def test_the_boards_menu_bar_gets_its_roles_and_its_keyboard_from_one_place() -> None:
    """A `role="menu"` with no `role="menuitem"` in it is an empty menu.

    The board's menus are written in index.html rather than built by
    `kebabMenu`, and that is deliberate: their rows are not all commands (the
    View menu holds a colour input, a grid select and four switches, which a
    command list cannot carry). The cost of writing a menu in markup is that
    its ARIA is written 76 times or not at all, and it was not at all:
    measured on the branch head with `scratchpad/ui-sweeps/wbtopbar.js`, all
    five top-bar menus opened with `role="menu"` and nought `role="menuitem"`
    in them, and ArrowDown moved no focus in any of them.

    So the roles come from one function at boot and the keyboard from the same
    one every other menu in the app uses. This is the ratchet on both: a menu
    added to this bar next year is stamped and wired by the same loop, and a
    role hand-written into the markup would be the drift that starts the next
    one.
    """
    html = (ROOT / "frontend" / "index.html").read_text(encoding="utf-8")
    board = (ROOT / "frontend" / "js" / "whiteboard.js").read_text(encoding="utf-8")
    app = app_js_text()

    menus = re.findall(r'<div id="(wb-[a-z-]+-menu)" class="wb-board-menu', html)
    assert len(menus) >= 5, (
        f"only {len(menus)} `.wb-board-menu` in the markup; the bar's five "
        "menus and the context bar's are the shape this ratchet counts"
    )
    assert 'role="menuitem"' not in html, (
        "a menu row carries a hand-written role in index.html; the roles come "
        "from wbStampMenuRoles so one place decides (DESIGN.md, the recipe index)"
    )
    assert "function wbStampMenuRoles(" in board, "wbStampMenuRoles is gone"
    for shape in ('".wb-menu-item"', '".wb-menu-section"'):
        assert shape in board, f"wbStampMenuRoles no longer stamps {shape}"
    assert "wbStampMenuRoles(menu)" in board and "wireMenuKeyboard(menu, toggle)" in board, (
        "the board's menus are not stamped and wired from the one loop over "
        "`.wb-board-menu-wrap`, so a menu added to the bar gets neither"
    )
    assert '> [role="group"] > [role="menuitem"]' in app, (
        "wireMenuKeyboard no longer looks inside a `role=\"group\"`, so every "
        "menu written in markup loses its arrow keys silently"
    )


def test_a_notice_is_the_recipe_and_not_a_second_private_box() -> None:
    """DESIGN.md's recipe index, added 2026-09-21 with CHAT_PLAN Phase 1's
    low-support line.

    The app had exactly one "something worth knowing about what is on screen"
    box, `.reindex-stale`, built inline with its own border, padding, radius
    and ground. When a second surface needed the same thing there was nothing
    to reuse, which is how a third and a fourth get drawn by hand and the
    owner's "all the ui issues happen when new features are added" happens
    again.

    So: the recipe exists, it has exactly two tones, and nothing redraws it.
    """
    css = "\n".join(path.read_text(encoding="utf-8") for path in CSS)
    rule = re.search(r"\n\.notice \{(.*?)\n\}", css, re.S)
    assert rule, ".notice has no rule; DESIGN.md's recipe index names it"
    body = rule.group(1)
    for declaration in ("border-radius: var(--radius-md)", "background: var(--accent-soft)"):
        assert declaration in body, f".notice must carry `{declaration}`"
    assert re.search(r"\n\.notice-warn \{", css), (
        "the warn tone is `.notice-warn`, an edge rather than a fill"
    )
    warn = re.search(r"\n\.notice-warn \{(.*?)\n\}", css, re.S).group(1)
    assert "background" not in warn, (
        "`.notice-warn` sets an edge, never a fill: a filled warning band over "
        "an answer reads as a failed answer, and it is not one"
    )
    #: A third tone would need a rule for when to use it, and DESIGN.md has
    #: none. The index says two.
    tones = set(re.findall(r"\n\.notice-([a-z]+) \{", css))
    assert tones == {"warn"}, f"two tones and no more; found {sorted(tones)}"

    #: And the box that used to be a class of one now uses it. This is what
    #: keeps the recipe honest: a recipe with one caller is a private box with
    #: a general name.
    html = (ROOT / "frontend" / "index.html").read_text(encoding="utf-8")
    assert re.search(r'id="reindex-stale"[^>]*class="[^"]*\bnotice\b', html), (
        "`#reindex-stale` was the app's only notice-shaped box and must be "
        "drawn by the recipe, not beside it"
    )
    stale = re.search(r"\n\.reindex-stale:not\(\.hidden\) \{(.*?)\n\}", css, re.S)
    assert stale, ".reindex-stale has no rule"
    for gone in ("border:", "border-radius:", "background:"):
        assert gone not in stale.group(1), (
            f"`.reindex-stale` still sets `{gone}` itself; the recipe draws it now"
        )


def test_an_embedded_board_is_the_one_preview_renderer_and_leaves_a_tombstone() -> None:
    """A board inside a note is drawn once, and never disappears silently.

    INBOX 309 put another of this app's surfaces inside somebody's text, which
    is the third place a board's miniature is drawn (the Library card and the
    dashboard row are the other two). MINDMAP_PLAN §5 item 12 already says why
    that has to go through one renderer: "the app's recurring failure is the
    same object drawn five ways", and the two that existed had already drifted
    into one with edges and labels and one without.

    The second half is the decision recorded in DOCUMENTS_PLAN's "Decisions
    made": a board deleted after somebody put it in a note takes a paragraph
    of that note with it, and a card that renders as nothing teaches the
    reader that the note was always like that. So the reference carries the
    board's title, and a reference that resolves to nothing draws a tombstone
    saying what was there.
    """
    app = app_js_text()
    editor = (ROOT / "frontend" / "js" / "editor.js").read_text(encoding="utf-8")
    css = "\n".join(path.read_text(encoding="utf-8") for path in CSS)

    assert "function boardEmbedElement(" in app and "function boardEmbedFill(" in app, (
        "the board object's card is no longer built in one place"
    )
    # The picture comes from the shared renderer, not from a second SVG builder
    # hand-written for notes.
    fill = app.split("function boardEmbedFill(", 1)[1].split("\nfunction ", 1)[0]
    assert 'mapPreview(board, { size: "card" })' in fill, (
        "the note's board object draws its own miniature instead of calling "
        "mapPreview: DESIGN.md's recipe index says there is one preview renderer"
    )
    assert "createElementNS" not in fill, (
        "the note's board object builds SVG of its own; the picture is "
        "mapPreview's, and a second builder is how the two came to disagree"
    )
    assert "board-embed-gone" in fill and "board-embed-gone" in css, (
        "the tombstone is gone: a deleted board would take the note's "
        "paragraph with it and say nothing (DOCUMENTS_PLAN, decisions made)"
    )
    # One spelling of the reference, shared by both doorways.
    assert "function boardEmbedMarkdown(" in app, "the reference is no longer written in one place"
    assert app.count("`![[${isMap ? \"map\" : \"board\"}:") == 1, (
        "the board reference is spelled in more than one place; the \"/\" menu "
        "and the board's own \"Add to a note\" both go through boardEmbedMarkdown"
    )
    assert "boardEmbedMarkdown(" in editor and "boardEmbedMarkdown(" in app, (
        "a doorway writes its own form of the reference"
    )
    # The whole card is the control, not a link beside a picture.
    assert ".board-embed-open" in css, "the board object's button has no rules of its own"


def test_every_status_bar_control_has_a_way_in_on_a_phone() -> None:
    """Below 600 the status bar is not on screen (INBOX 392, UI_MODERNISATION_PLAN
    Phase 11 item 12): `dockPhoneStatus` moves Back, Undo and the AI dot into
    the header and every other control is a row of the header's menu
    (`PHONE_STATUS_ROWS`). A control added to the bar later with neither would
    exist on a desktop and not on a phone, which Phase 11's decision forbids
    ("nothing is hidden that the desktop has"). The notes count and the
    palette hint, hidden below 720 by the bar's own band, and the clock, a
    desktop opt-in, are the named exceptions."""
    html = (ROOT / "frontend" / "index.html").read_text(encoding="utf-8")
    app = app_js_text()
    footer = re.search(r'<footer[^>]*id="status-bar".*?</footer>', html, flags=re.S)
    assert footer, "the status bar is gone from index.html"
    ids = set(re.findall(r'<button[^>]*\bid="([^"]+)"', footer.group(0)))
    rows = re.search(r"const PHONE_STATUS_ROWS = \[(.*?)\];", app, flags=re.S)
    assert rows, "PHONE_STATUS_ROWS is gone from app.js"
    in_menu = set(re.findall(r'id: "([^"]+)"', rows.group(1)))
    docker = app.split("function dockPhoneStatus", 1)[1][:2000]
    for name in ("status-back", "status-undo", "ai-status"):
        assert f'$("{name}")' in docker, f"{name} is no longer moved into the phone header"
    moved = {"status-back", "status-undo", "ai-status"}
    exceptions = {"status-notes", "status-command", "status-clock"}
    # The transient ones bring the bar itself back while they show.
    responsive_css = (ROOT / "frontend" / "css" / "10-responsive.css").read_text(encoding="utf-8")
    transient = {name for name in ids if f"#{name}:not(.hidden" in responsive_css}
    assert "status-task" in transient, "a running job no longer brings the phone's status bar back"
    # The agent's runs do not (INBOX 430, the owner: "hide the agent-runs bar
    # on phones and fold its count into More"): their count is More's badge
    # and their way in is More's "Agent activity" row.
    assert "status-activity" not in transient, "the agent's runs bring the phone's status bar back again"
    # Four are rows of the tab bar's More sheet already, which is their way in.
    more = app.split("function openPhoneMoreSheet", 1)[1][:5000]
    in_more = {"status-reminders", "status-agent", "status-guide", "status-activity"}
    assert '"Agent activity"' in more and '$("status-activity")?.click()' in more, (
        "More no longer holds the agent's runs, their only way in on a phone"
    )
    assert '"reminders"' in app.split("const PHONE_MORE_TABS", 1)[1][:200], (
        "Reminders left the More sheet, and the status bar's count was its phone way in"
    )
    for word in ("Ask the agent", "Guide"):
        assert f'"{word}"' in more, f"'{word}' left the More sheet; give its status control a header row"
    missing = sorted(ids - in_menu - moved - exceptions - transient - in_more)
    assert not missing, (
        f"status-bar controls with no way in on a phone: {missing}; add each to "
        "PHONE_STATUS_ROWS (app.js), which makes it a row of the header menu"
    )
    responsive = (ROOT / "frontend" / "css" / "10-responsive.css").read_text(encoding="utf-8")
    assert "--status-bar-h: 0px" in responsive, (
        "the phone band no longer takes the status bar's height back"
    )


def test_a_menu_behind_a_button_is_an_action_sheet_on_a_phone() -> None:
    """DESIGN.md, "A menu behind a button": below 600 both ⋯ builders open the
    sheet recipe through `openKebabSheet` (INBOX 392: "a bottom sheet instead
    of a popover"). A third builder, or one of these two losing the branch,
    would put a popover back on a phone for that one menu."""
    app = app_js_text()
    for builder in ("function kebabMenu(", "function entryOverflowMenu("):
        body = app.split(builder, 1)[1][:3000]
        assert "PHONE_ACTION_SHEET" in body and "openKebabSheet(" in body, (
            f"{builder.split('(')[0][9:]} no longer opens as an action sheet below 600"
        )
    sheet = app.split("function openKebabSheet(", 1)[1][:2500]
    assert "openSheet(" in sheet and "has-submenu" in sheet, (
        "openKebabSheet no longer uses the sheet recipe, or closes on a group's own row"
    )


def test_a_coarse_pointer_gets_the_touch_floor_at_every_width() -> None:
    """DESIGN.md, "Hit targets": the 44px floor follows the pointer, not only
    the width (INBOX 392). Measured with a touch context at 1024x768 before:
    search boxes, sub-tabs and dock buttons at 36px and the status bar's items
    at 28, because every floor was written for `max-width: 819.98px` and an
    iPad in landscape is 1024. The `:root` token and the dock's own floor are
    the two a regression would lose first."""
    touch_query = "@media (max-width: 819.98px), (pointer: coarse)"
    shell = "\n".join((ROOT / "frontend" / "css" / name).read_text(encoding="utf-8") for name in ("07-whiteboard-misc.css", "library-lazy.css"))
    token = re.search(r"@media[^{\n]*\{\s*:root\s*\{\s*--target-min:\s*2\.75rem;", shell)
    assert token and token.group(0).startswith(touch_query), (
        "the 44px --target-min is no longer declared for a coarse pointer at every width"
    )
    dock = re.search(r"@media[^{\n]*\{\s*\.dock button,", shell)
    assert dock and dock.group(0).startswith(touch_query), (
        "the dock's 44px floor is width-only again; a finger at 1024 gets 36px controls"
    )


def test_every_icon_only_button_meets_the_touch_floor() -> None:
    """The icon-only floor, app-wide (uipolish-0924 item 3, OPEN.md 0.3.3).

    A button with an icon and no words is only recognisable in a browser (its
    words are an aria-label, its markup an `<i>` beside text nodes a selector
    cannot see), so the measurement is `scratchpad/ui-sweeps/iconfloor.js`,
    in `gate.sh --sweeps`: every icon-only button on every tab, a document, a
    board and Settings, in a touch context, none under 44px (296 measured at
    1024, 106 at 390, 0 under). What this holds statically is that the sweep
    stays in the gate, and the one it found: the toast's close, a bare
    `button` that no class floor reached (20x20 before)."""
    gate = (ROOT / "scripts" / "gate.sh").read_text(encoding="utf-8")
    sweeps = re.search(r"for s in ([^;]+); do step \"sweep-\$s\"", gate)
    assert sweeps and "iconfloor" in sweeps.group(1).split(), "iconfloor.js left the --sweeps list"
    css = (ROOT / "frontend" / "css" / "02-chat-graph.css").read_text(encoding="utf-8")
    block = re.search(
        r"@media \(max-width: 819\.98px\), \(pointer: coarse\) \{\s*\.toast-close \{([^}]*)\}", css
    )
    assert block, "the toast's close lost its touch floor"
    assert "min-width: var(--target-min)" in block.group(1)
    assert "min-height: var(--target-min)" in block.group(1)


def test_code_diagnostics_are_drawn_in_the_apps_ink() -> None:
    """A syntax error in a code document is the recipe DESIGN.md names (INBOX
    392): CodeMirror's linter and completion list, restyled in `docCmTheme`
    onto the app's tokens. The library's own lint and completion styles are
    fixed colours (#d11, a red SVG squiggle, white on #17c), right on a white
    page and wrong on the dark one; the underline is the prose findings'
    shape so an error in code and a misspelling in prose are one idea."""
    #: documents.js (the theme) and documents-code.js (docCodeTools, split
    #: out of documents.js on 2026-09-24), joined.
    docs = "\n".join(
        (ROOT / "frontend" / "js" / name).read_text(encoding="utf-8")
        for name in ("documents.js", "documents-code.js")
    )
    theme = docs.split("function docCmTheme(CM) {", 1)[1].split("\nfunction ", 1)[0]
    for selector in (
        '".cm-lintRange-error"',
        '".cm-lint-marker-error"',
        '".cm-diagnostic-error"',
        '".cm-tooltip-autocomplete ul li[aria-selected]"',
    ):
        assert selector in theme, f"docCmTheme no longer restyles {selector}"
    # The lint block of the theme, from its heading to the next one, with
    # its comments taken out: the comments name the library's own colours on
    # purpose, to say why they are restated.
    lint = theme.split("a code file's diagnostics and completions", 1)[1].split("--- Live preview", 1)[0]
    code = "\n".join(line for line in lint.splitlines() if not line.strip().startswith("//"))
    assert not re.search(r"#[0-9a-fA-F]{3,8}\b", code), (
        "a hex colour in the code diagnostics' theme: use the app's tokens"
    )
    assert 'backgroundImage: "none"' in code, (
        "the library's baked-in red squiggle is back under the app's own underline"
    )
    # The tools are for code only, and Plain turns them off.
    tools = docs.split("function docCodeTools(CM) {", 1)[1].split("\n}\n", 1)[0]
    assert "type.previewable" in tools and 'docView === "plain"' in tools, (
        "the code tools no longer stand down for prose and for Plain"
    )
    # Never by running the file.
    region = docs.split("// Code documents as a code editor", 1)[1].split("function docCmExtensions(CM)", 1)[0]
    region = "\n".join(line for line in region.splitlines() if not line.strip().startswith("//"))
    assert "new Function" not in region and "eval(" not in region, (
        "a code check that executes the file: the CSP forbids it and it is not a check"
    )


def test_an_icon_picker_keeps_its_name_and_hides_its_word_by_clipping() -> None:
    """The note strip's colour pickers are icons with a caret (the owner, at
    the 1184px desktop window: "Preview" wrapped alone onto a second row).
    The word leaves the row but not the accessibility tree: it is clipped,
    never `display: none`, and the opener's name is the select's own
    aria-label. The worded buttons follow the same rule where they go
    icon-only."""
    app = app_js_text()
    enhance = app.split("function enhanceSelect(select) {", 1)[1].split("\nfunction ", 1)[0]
    assert "select.dataset.selectIcon" in enhance and "select-opener-icon" in enhance, (
        "enhanceSelect no longer draws the icon face data-select-icon asks for"
    )
    css = "\n".join(p.read_text(encoding="utf-8") for p in CSS)
    for selector in (".select-opener-icon .select-value {", ".note-toolbar .toolbar-word {"):
        assert selector in css, f"{selector} has no rule"
        body = css.split(selector, 1)[1].split("}", 1)[0]
        assert "clip-path" in body and "display: none" not in body, (
            f"{selector} must clip the word, not remove it: it is the control's name"
        )
    page = (ROOT / "frontend" / "index.html").read_text(encoding="utf-8")
    bar = page.split('id="note-toolbar"', 1)[1].split('id="entry-content"', 1)[0]
    assert bar.count('data-select-icon="') == 2, "the note strip's colour pickers are words again"
    for select in re.findall(r"<select[^>]*data-select-icon[^>]*>", bar):
        assert "aria-label=" in select and "title=" in select, (
            "an icon picker needs an aria-label (its name) and a title (its hover text)"
        )


#: **The segmented-control radius table** (DESIGN.md, "Segmented controls";
#: OPEN.md's App wide row). Measured 2026-09-21 and again 2026-09-23: five
#: track radii in the app and none of them written down, so each new toggle
#: picked one. The table names them, and this holds every rule that rounds a
#: track to one of its rows, so a sixth cannot appear by a new rule reaching
#: for whatever token was nearest. The value maps to the one context it is
#: allowed in (None: anywhere).
SEG_TRACK_RADII = {
    "var(--radius-choice)": None,  # a choice control
    "var(--radius-strip)": None,  # a sub-tab strip
    "var(--radius-pill)": ".chat-dock-controls",  # the chat dock, a row of pills
    "var(--radius-md)": ".dock",  # in a bar the control takes the bar's corner
    "0": ".doc-sidebar-tabs",  # a full-bleed strip
}


def _seg_track_names() -> set[str]:
    names = {
        ".seg",
        ".seg-compact",
        ".segmented-control",
        ".notes-subtabs",
        ".library-subtabs",
        ".doc-sidebar-tabs",
        ".ocr-rail-switch",
    }
    page = (ROOT / "frontend" / "index.html").read_text(encoding="utf-8")
    for tag in re.findall(r"<[a-z]+\s[^>]*>", page):
        classes = re.search(r'class="([^"]*)"', tag)
        ident = re.search(r'\sid="([^"]+)"', tag)
        if (
            classes
            and ident
            and re.search(r"(?<![\w-])(seg|segmented-control)(?![\w-])", classes.group(1))
        ):
            names.add("#" + ident.group(1))
    return names


#: INBOX 665 (the owner: "i dont really like these multi pill elements exept
#: in some small cases like the little view mode 2 pill ones"). A `.seg` well
#: of four or more choices written in index.html, each with where its
#: conversion is placed (archive/agent-remaining/seg665-1006.md). The list may only
#: shrink: a new well of four is a `<select>` or previews (DESIGN.md).
SEG_OF_FOUR_PLACED: dict[str, str] = {
    #: Empty since libr-1011 (ledger row 1234): the Attach picker's five sources
    #: were the one well of four that stayed (INBOX 670); INBOX 715 ("i dont
    #: like pills like that in popups") is later, and they are a
    #: `.tabs-line.popup-kinds` strip carrying their counts now.
}


class _SegWells(HTMLParser):
    """Every `.seg` / `.segmented-control` in the page with its option count."""

    def __init__(self) -> None:
        super().__init__()
        self.depth = 0
        self.open: list[list] = []
        self.found: dict[str, int] = {}

    def handle_starttag(self, tag, attrs):
        a = dict(attrs)
        if tag == "input":
            if a.get("type") == "radio" and self.open:
                self.open[-1][2] += 1
            return
        if tag in ("br", "img", "meta", "link"):
            return
        self.depth += 1
        classes = (a.get("class") or "").split()
        if tag == "div" and ("seg" in classes or "segmented-control" in classes) and "tabs-line" not in classes:
            self.open.append([self.depth, a.get("id") or ".".join(classes), 0])
        elif tag == "button" and self.open and self.depth == self.open[-1][0] + 1:
            self.open[-1][2] += 1

    def handle_endtag(self, tag):
        if tag in ("input", "br", "img", "meta", "link"):
            return
        if self.open and self.open[-1][0] == self.depth:
            _, name, count = self.open.pop()
            self.found[name] = count
        self.depth -= 1


def test_a_pill_well_holds_two_or_three_choices() -> None:
    """DESIGN.md's `.seg` row (INBOX 665): a well is for two or three short
    choices always in view. Measured before by `scratchpad/seg665_inventory.py`:
    25 wells in the page, four of them four or five wide, plus the map topic
    bar's eight selects drawn as wells of three to thirteen. The two the owner
    named among the threes (Questions' state, AI skills' kinds) are selects."""
    html = (ROOT / "frontend" / "index.html").read_text(encoding="utf-8")
    html = re.sub(r"<!--.*?-->", "", html, flags=re.S)
    wells = _SegWells()
    wells.feed(html)
    wide = {name for name, count in wells.found.items() if count >= 4}
    assert wide <= set(SEG_OF_FOUR_PLACED), f"a new pill well of four or more: {sorted(wide - set(SEG_OF_FOUR_PLACED))}"
    for name in ("questions-state", "skills-kind", "font-seg", "density-seg", "graph-layout"):
        assert name not in wells.found, f"#{name} is a select (INBOX 665, 670), not a well"
        assert f'<select id="{name}"' in html


def test_font_and_density_are_lists_that_keep_their_handlers() -> None:
    """INBOX 670: Settings, Appearance, Font and Density were wells of four.
    Each is a `<select>` (ids kept) that writes the same setting as before,
    and `renderAppearance` sets the list from the stored value."""
    html = (ROOT / "frontend" / "index.html").read_text(encoding="utf-8")
    font = html[html.index('<select id="font-seg"') :]
    font = font[: font.index("</select>")]
    assert re.findall(r'value="(\w+)"', font) == ["system", "serif", "mono", "arial", "readable"]
    density = html[html.index('<select id="density-seg"') :]
    density = density[: density.index("</select>")]
    assert re.findall(r'value="(\w+)"', density) == ["auto", "comfortable", "compact", "spacious"]
    js = with_pieces("settings.js")
    assert '$("font-seg").addEventListener("change"' in js and 'prefs.set("font", e.target.value)' in js
    assert '$("density-seg").addEventListener("change"' in js
    assert '$("font-seg").value = appearancePref("font")' in js
    assert '$("density-seg").value = prefs.get("density", null) || "auto"' in js
    assert "#font-seg button" not in js and "#density-seg button" not in js


def test_the_suggestions_inbox_kinds_are_a_list_with_counts() -> None:
    """INBOX 670: the inbox's four kinds, each carrying a count, were a
    `.seg` well (the shape INBOX 665 took away from Questions). One select,
    `#inbox-kind`, its rows "Links (3)"; the arrows of the list replace the
    tabs' own, and the panes follow the value."""
    js = (ROOT / "frontend" / "js" / "suggestions-inbox.js").read_text(encoding="utf-8")
    assert 'document.createElement("select")' in js and 'kind.id = "inbox-kind"' in js
    assert "inbox-seg" not in js and 'className = "seg' not in js and '"tablist"' not in js
    assert 'kind.addEventListener("change"' in js and "inboxShow(kind.value)" in js
    assert "option.dataset.label" in js, "the counts ride on the select's rows"
    css = "\n".join(p.read_text(encoding="utf-8") for p in CSS)
    assert ".inbox-seg" not in css
    reveal = (ROOT / "frontend" / "js" / "reveal-targets.js").read_text(encoding="utf-8")
    assert "#inbox-tab-" not in reveal


def test_a_visual_choice_is_a_row_of_previews() -> None:
    """DESIGN.md "A visual choice in a popup" (INBOX 665). Measured before
    with `seg665-probe.js` at 1440 on a themed map: the Shape door 333px with
    Box and Fill wrapping to 103px rows, the Text door's icons to three lines.
    After: every row 32px, one line, the door 155px. The rows are previews in
    one label column, the follow choice a trailing reset, never a well."""
    wm = frontend_text("whiteboard-map.js")
    assert "wbMapChoiceRow" not in wm and "wb-map-choices" not in wm
    assert '"seg wb-map-theme-scope"' not in wm
    for name in ("function wbMapPickRow(", "function wbMapSizeStepper(", "function wbMapMarkerGlyph("):
        assert name in wm
    seg = wm[wm.index("function wbMapMarkerSeg(") :]
    seg = seg[: seg.index("\n}\n")]
    assert 'className = "seg"' not in seg and '"wb-map-picks"' in seg
    css = "\n".join(p.read_text(encoding="utf-8") for p in CSS)
    picks = css[css.index(".wb-map-picks {") :]
    assert "flex-wrap: nowrap;" in picks[: picks.index("}")]
    assert "grid-template-columns: 5rem minmax(0, 1fr);" in css


def test_a_segmented_track_is_rounded_by_the_table() -> None:
    names = _seg_track_names()
    offenders = []
    for path in CSS:
        for selector, body in _rules(path.read_text(encoding="utf-8")):
            radius = re.search(r"(?<![\w-])border-radius\s*:\s*([^;]+)", body)
            if not radius or selector.startswith("@"):
                continue
            value = " ".join(radius.group(1).replace("!important", "").split())
            for part in selector.split(","):
                part = " ".join(part.split())
                #: The last compound is the element the rule rounds: `.seg
                #: button` rounds a segment, which is not what this table is
                #: about, and `.dock .seg` rounds a track.
                last = re.split(r"\s*[\s>+~]\s*", part)[-1]
                #: `.seg::before` is a box drawn inside the track (the
                #: selection indicator, INBOX 459 (2)), rounded like the
                #: segment it sits on; it is not the track.
                if "::" in last:
                    continue
                if not set(re.findall(r"[.#][\w-]+", last)) & names:
                    continue
                if value not in SEG_TRACK_RADII:
                    offenders.append(f"{path.name}: {part} -> {value}")
                    continue
                scope = SEG_TRACK_RADII[value]
                if scope and scope not in part:
                    offenders.append(f"{path.name}: {part} -> {value} (only under {scope})")
    assert not offenders, (
        "a segmented track rounded off the table (DESIGN.md, 'Segmented controls'):\n  "
        + "\n  ".join(offenders)
    )


#: **Where a control may still be a capsule** (DESIGN.md, "Pills are rare, and
#: never dashed"; INBOX 394 h). Every other rule that rounds a control to
#: `--radius-pill` fails `test_a_control_is_a_pill_only_where_named`. The key
#: is the selector as it is written, the value is why it earns the shape.
PILL_CONTROLS = {
    ".icon-btn": "a round icon button is a circle, not a pill",
    ".lightbox-close": "a round button over a photo",
    ".lightbox-nav": "a round button over a photo",
    ".chat-jump-latest": "floats over the thread, the floating-action shape",
    ".dock-fab": "the floating action button",
    ".chat-dock-controls select": "the chat composer's row is pills (the radius table)",
    ".chat-dock-controls>.chat-tool-group>button": "the chat composer's row is pills",
    ".chat-dock-controls .chat-dock-more>button": "the chat composer's row is pills",
    ".chat-dock-controls .seg": "the chat composer's row is pills",
    ".chat-dock-controls .seg button": "the chat composer's row is pills",
    ".chat-context-pill": "the context meter in the chat composer's row",
    "#notif-btn.has-unread::after": "an unread dot",
    ".notif-unread-chip": "a count badge",
    ".selection-bar button": "a floating bar over a canvas",
    ".wb-context button": "the board's floating context bar",
    ".wb-map-strip>button.icon-only": "a round icon button in the map's floating strip",
    '.wb-map-node[data-shape="pill"]': "a node shape the person picked",
    "#entry-list .link-connection>.menu-wrap>button": "the round kebab inside a connection",
    ".entry-links>button.ghost.entry-links-more": "one more link pill in the row of link pills (INBOX 592)",
    ".stepper>.stepper-btn": "a round minus or plus inside the stepper's pill (DESIGN.md 'Stepper')",
    "#reminder-due-row>details>summary": "Quick set beside the steppers: one corner per row, as the chat composer's (INBOX 464 (17))",
    "body .chip.item-label": "the status label: a tinted pill without an edge, the owner's decision (INBOX 553 (c))",
    ".entry-meta .chip.item-label": "the status label on a note line, the same pill (INBOX 553 (c))",
}

_PILL_CONTROL = re.compile(
    r"(?<![\w-])(button|summary|select)(?![\w-])"
    r"|chip|pill|btn|toggle|\.seg(?![\w-])|-close|-nav\b|jump|fab"
)


def test_a_control_is_a_pill_only_where_named() -> None:
    offenders = []
    for path in CSS:
        for selector, body in _rules(path.read_text(encoding="utf-8")):
            radius = re.search(r"(?<![\w-])border-radius\s*:\s*([^;]+)", body)
            if not radius or not re.search(r"radius-pill|\b9{3,}px", radius.group(1)):
                continue
            for part in selector.split(","):
                part = " ".join(part.split())
                last = re.split(r"\s*[\s>+~]\s*", part)[-1]
                if not _PILL_CONTROL.search(last):
                    continue
                if re.sub(r"\s*>\s*", ">", part) not in PILL_CONTROLS:
                    offenders.append(f"{path.name}: {part}")
    assert not offenders, (
        "a control drawn as a capsule outside PILL_CONTROLS (DESIGN.md, 'Pills are "
        "rare'): use --radius-md for a button or a navigation row, --radius-sm for a "
        "label, or add it with its reason:\n  " + "\n  ".join(offenders)
    )


def test_no_control_marks_itself_with_a_dashed_edge() -> None:
    """A dashed edge is an empty slot; the dashboard's skill pills wore one to
    say "this runs something", which read as a drop zone (INBOX 394 h)."""
    css = "\n".join(p.read_text(encoding="utf-8") for p in CSS)
    for selector, body in _rules(css):
        if ".quick-link" in selector:
            assert "dashed" not in body, f"{selector} is dashed again"


def test_a_template_preview_is_the_page_the_row_would_make() -> None:
    """DESIGN.md's recipe for a dialog of choices that each make something:
    the preview is drawn by the function that creates the thing, so it cannot
    describe a template differently from what it is, and it is inert and
    hidden from a screen reader, which has each row's own hint."""
    docs = (ROOT / "frontend" / "js" / "documents.js").read_text(encoding="utf-8")
    body = _function_body(docs, "showDocTemplatePreview")
    assert "docTemplateFill(template)" in body and "renderMarkdown(" in body
    page = (ROOT / "frontend" / "index.html").read_text(encoding="utf-8")
    pane = re.search(r'<div id="doc-template-preview"[^>]*>', page)
    assert pane and 'aria-hidden="true"' in pane.group(0) and "inert" in pane.group(0)


def test_the_table_s_two_named_radii_are_tokens() -> None:
    tokens = (ROOT / "frontend" / "css" / "00-tokens-shell.css").read_text(encoding="utf-8")
    assert "--radius-choice:" in tokens and "--radius-strip:" in tokens
    design = (ROOT / "docs" / "DESIGN.md").read_text(encoding="utf-8")
    assert "--radius-choice" in design and "--radius-strip" in design



def test_a_search_and_read_pane_is_one_field_one_list_and_one_scroller() -> None:
    """DESIGN.md's recipe index, the row for a side pane that searches and
    reads (the chat tab's Web panel).

    The owner, 2026-09-24: "the web browser sidebar needs a major improved
    modern and professional redesign". Measured before
    (`scratchpad/ui-sweeps/webpanel.js`): four boxed controls above the
    results in two heights and two radii, the engine's state as a chip with a
    worded Stop on its own row, and the page text in a bordered box that
    scrolled inside a column that scrolled too. Each of those is the kind of
    thing the next change puts back one piece at a time, so each is held here:

    - the head is a `.panel-head` whose one fact is the engine dot, carrying
      its words as a title and an accessible name, never a chip;
    - the field is one well holding the glyph, the input and at most Stop,
      which starts hidden (Enter searches; there is no Search button);
    - the reader text draws no box and does not scroll: the reader is the
      pane's one scroller.
    """
    page = (ROOT / "frontend" / "index.html").read_text(encoding="utf-8")
    start = page.index('<aside id="web-panel"')
    panel = page[start : page.index("</aside>", start)]

    head = re.search(r'<h3 class="panel-head web-panel-head">(.*?)</h3>', panel, re.S)
    assert head, "the Web panel's head left the `h3.panel-head` recipe"
    assert 'class="chip' not in head.group(1), "the engine state is a dot, not a chip"
    dot = re.search(r'<span id="web-engine-dot"[^>]*>', head.group(1))
    assert dot and 'role="img"' in dot.group(0) and "aria-label=" in dot.group(0) and "title=" in dot.group(0), (
        "the engine dot carries its words as a title and an accessible name: colour is never the only signal"
    )

    field = re.search(r'<div class="web-search-field"[^>]*>(.*?)</div>', panel, re.S)
    assert field, "the search field is one `.web-search-field` well"
    buttons = re.findall(r"<button\b[^>]*>", field.group(1))
    assert len(buttons) == 1 and 'id="web-stop"' in buttons[0] and "hidden" in buttons[0], (
        "the field holds one button, Stop, hidden until something is loading; Enter searches"
    )
    assert 'id="web-go"' not in page, "a Search button beside the field is the form this replaced"

    css = "\n".join(p.read_text(encoding="utf-8") for p in CSS)
    for selector, body in _rules(css):
        parts = [" ".join(p.split()) for p in selector.split(",")]
        if any(p.endswith(".web-reader-text") for p in parts):
            assert not re.search(r"overflow-y\s*:\s*(auto|scroll)", body), (
                f"{selector}: the reader text scrolls again; the reader is the pane's one scroller"
            )
            assert not re.search(r"(?<![\w-])border\s*:\s*(?!0|none)", body), (
                f"{selector}: the reader text is boxed again; a page is prose, not a field"
            )


def test_the_persons_mark_is_one_builder_and_one_painter() -> None:
    """DESIGN.md's recipe index, "A mark generated from a name".

    The local profile's mark is deterministic from the display name, so the
    person must draw the same mark in the chat, the Settings head and the
    profile's head. A second builder, a holder the painter cannot find, or a
    surface back on a generic glyph is how they would come to disagree after
    a rename.
    """
    app = app_js_text()
    html = (ROOT / "frontend" / "index.html").read_text(encoding="utf-8")
    #: The builder is avatars.js's since the faces were split out of app.js.
    avatars = (ROOT / "frontend" / "js" / "avatars.js").read_text(encoding="utf-8")
    assert avatars.count("function nameMark(") == 1, "the name mark is no longer drawn in one place"
    for path in JS:
        if path.name != "avatars.js":
            assert "function nameMark(" not in path.read_text(encoding="utf-8"), (
                f"{path.name} draws a second name mark"
            )
    painter = app.split("function paintUserMarks(", 1)[1].split("\nfunction ", 1)[0]
    assert "[data-user-mark]" in painter and "nameMark(seed" in painter, (
        "paintUserMarks no longer redraws every holder of the person's mark"
    )
    # Both heads are holders the painter can find.
    assert 'id="profile-avatar" data-user-mark=' in html, "the profile head's mark is not painted"
    assert re.search(r'id="settings-profile-btn"[^>]*>\s*<span[^>]*data-user-mark=', html), (
        "the Settings head's mark is not painted"
    )
    # The chat's own bubble is a holder too, and never the old glyph.
    #: Built by `userMarkEl`, which Chat's bubbles and the popup agent's share.
    bubble = app.split("function addBubble(", 1)[1].split("\nfunction ", 1)[0]
    mark = app.split("function userMarkEl(", 1)[1].split("\nfunction ", 1)[0]
    assert "userMarkEl()" in bubble and "dataset.userMark" in mark and "nameMark(userMarkSeed()" in mark, (
        "the user's chat bubble no longer carries the profile's mark"
    )
    palette = (ROOT / "frontend" / "js" / "palette.js").read_text(encoding="utf-8")
    assert "userMarkEl()" in palette, "the popup agent's bubble lost the profile's mark"
    assert '"ph:user"' not in bubble, "the user's chat bubble went back to a generic glyph"
    # Painted when the preferences arrive and after a save.
    assert app.count("paintUserMarks();") >= 3, "the person's mark is not repainted on load and save"


def test_a_whole_window_mode_leaves_one_fading_dock_with_a_way_out() -> None:
    """DESIGN.md's recipe for a surface given the whole window (the documents
    editor's focus mode, INBOX 425 i).

    Four things a later edit could quietly break, each of which the owner
    would only find by being stuck in the mode:

    1. The floating dock is a labelled toolbar on the glass-panel recipe and
       carries a worded Exit, so the way out is always a visible control and
       never only a key.
    2. Its idle state changes opacity and pointer events, nothing else: a fade
       that moved or resized the dock would be a layout change on every wake.
    3. The fade stops under reduced motion.
    4. Escape asks before it leaves: bubble phase, not already spent by the
       editor (`defaultPrevented`), and not while a dialog is open over the
       page (`activeOverlay`). The first version listened in the capture
       phase and left the mode underneath an open slash menu.
    """
    html = (ROOT / "frontend" / "index.html").read_text(encoding="utf-8")
    tag = re.search(r"<div[^>]*id=\"doc-focus-bar\"[^>]*>", html)
    assert tag, "the focus mode's floating dock is gone"
    assert 'role="toolbar"' in tag.group(0) and "aria-label=" in tag.group(0)
    assert "card glass" in tag.group(0), "the floating dock is not the glass-panel recipe"
    bar = html[tag.start(): html.index("\n    </div>", tag.start())]
    assert re.search(r'id="doc-focus-exit"[^>]*>.*Exit</button>', bar, flags=re.S), (
        "the floating dock has no worded Exit"
    )

    idle = []
    reduced = False
    for path in CSS:
        text = path.read_text(encoding="utf-8")
        for selector, body in _rules(text):
            if "doc-focus-idle" in selector and "doc-focus-bar" in selector:
                idle.append(body)
        stripped = re.sub(r"/\*.*?\*/", "", text, flags=re.S)
        for block in re.finditer(r"@media \(prefers-reduced-motion: reduce\) \{(.*?)\n\}", stripped, flags=re.S):
            if "doc-focus-bar" in block.group(1) and "transition: none" in block.group(1):
                reduced = True
    assert idle, "no idle rule for the floating dock"
    for body in idle:
        props = {p.split(":")[0].strip() for p in body.split(";") if ":" in p}
        assert props <= {"opacity", "pointer-events"}, f"the idle dock changes more than its opacity: {props}"
    assert reduced, "the floating dock's fade has no reduced-motion block"

    docs = (ROOT / "frontend" / "js" / "documents.js").read_text(encoding="utf-8")
    handler = docs.split('if (event.key !== "Escape" || event.defaultPrevented) return;', 1)
    assert len(handler) == 2, "focus mode's Escape no longer checks that the editor did not spend it"
    body = handler[1].split("});", 1)[0]
    assert "docFocusOn()" in body and "activeOverlay()" in body, (
        "focus mode's Escape no longer asks whether a dialog is open over the page"
    )


def test_a_citation_mark_previews_its_source_on_the_help_popover_recipe() -> None:
    """DESIGN.md, "A preview of a cited source" (INBOX 80). A mark's press
    used to call `flashEntry` and leave the chat; it now opens a peek, built
    as a `.help-popover` placed by `placeHelpPopover`, so the peek cannot
    grow a shell, caret or tier of its own. Measured by
    `scratchpad/ui-sweeps/citepeek.js` at 1440 and 390."""
    source = (ROOT / "frontend" / "js" / "capture-ask.js").read_text(encoding="utf-8")
    marker = source[source.index("function citationMarker(") :]
    marker = marker[: marker.index("\n}\n")]
    assert "flashEntry(" not in marker, "a citation mark navigates on its own press again"
    assert "openCitationPeek(link" in marker
    peek = source[source.index("function openCitationPeek(") :]
    peek = peek[: peek.index("\n}\n")]
    assert '"help-popover citation-peek"' in peek, "the peek is not a help popover"
    assert "placeHelpPopover(panel, link)" in peek, "the peek places itself instead of through the popover's placement"
    assert "document.body.appendChild(panel)" in peek, "the peek must leave for <body>, or a card's filter clips it"
    assert "openNoteAtPassage(source.noteId" in peek, "the peek has no way to the note"
    for path in CSS:
        for selector, body in _rules(path.read_text(encoding="utf-8")):
            if "citation-peek" in selector:
                for prop in ("z-index", "box-shadow", "backdrop-filter", "position"):
                    assert f"{prop}:" not in body, f"{selector} sets its own {prop}: the shell is the help popover's"


#: **The rich picker** (DESIGN.md's recipe index, "A list of choices picked by
#: typing or browsing"). The "/" menu's rows, taken out of editor.js so every
#: picker draws the same row (the owner: "I reallllllyyyy like the design of
#: this popup panel menu for the / commands. can we do more similar design
#: styles elsewhere in the app??"). The anatomy's classes are stamped by
#: rich-picker.js and nowhere else, so a picker cannot hand-roll a row that
#: looks nearly like one.
RICH_PICKER_PARTS = ("row", "tile", "keys", "group", "label", "about", "text", "hit", "preview-head")

#: The pickers that draw through the recipe: (file, function).
RICH_PICKERS = [
    ("editor.js", "editorRenderMenu"),
    ("app-palette.js", "renderPalette"),
    ("library.js", "openLibraryCreatePicker"),
    ("chord-guide.js", "chordGuideGroup"),
    ("selection.js", "pickerListbox"),
]


def _notes_picker_body() -> str:
    """`pickNotesDialog`, now at the end of whiteboard.js's moved block: it ends
    where the next function, an `async` one, begins."""
    text = frontend_text("whiteboard.js")
    start = text.index("function pickNotesDialog(")
    return text[start : text.index("\nasync function addBoardToNote(", start)]


def test_every_notebook_picker_is_the_picker_dialog() -> None:
    """INBOX 548: the "choose from your notebook" dialogs share one shell on
    the dialog recipes (`pickerDialog`: the head with its X, the search field
    well, the dialog foot), never the confirm alert's card and a bare input."""
    source = frontend_text("selection.js")
    shell = _function_body(source, "pickerDialog")
    for part in ("dialogHead(", '"search-field"', "space-dialog"):
        assert part in shell, part
    head = _function_body(source, "dialogHead")
    assert '"dialog-head"' in head and '"dialog-head-btn"' in head and '"dialog-head-title"' in head
    #: pickNotesDialog moved to whiteboard.js, its only caller (search-boot-1005).
    for picker in ("pickEntryDialog", "pickLibraryItemDialog", "pickNotesDialog", "pickMediaDialog"):
        body = _notes_picker_body() if picker == "pickNotesDialog" else _function_body(source, picker)
        assert "pickerDialog(" in body, picker
        assert "confirm-card" not in body and "confirm-text" not in body, picker
    assert "notePickerRow(" in _notes_picker_body()


def test_a_picker_row_never_shrinks_and_its_sources_span_the_dialog() -> None:
    """INBOX 572 (the owner: "this whole popup panel is cooked"). The list is
    a column flex box of one fixed height, so with more rows than fit every
    row shrank to the target floor (28px measured with 25 notes) while its
    32px tile stayed whole and hung over the next row's title. A row never
    shrinks and has one height; the sources are a full-width `.tabs-line.popup-kinds`
    strip carrying their counts; the source is remembered; a title
    is clipped by the row's width (CSS), never by a character count."""
    rows = _css_block(".entry-pick-card > .entry-pick-list > li")
    assert "flex: none" in rows
    rich = _css_block(".entry-pick-list > .entry-pick-row")
    assert "height: var(--pick-row-h)" in rich
    seg = _css_block(".entry-pick-card > .picker-kinds")
    assert "align-self: stretch" in seg and "overflow-x: auto" in seg
    tab = _css_block(".entry-pick-card > .picker-kinds > button")
    assert "flex: 1 1 auto" in tab and "min-width: 0" in tab
    source = frontend_text("selection.js")
    body = _function_body(source, "pickLibraryItemDialog")
    assert "seg-count" in body and "pickerRememberedSource" in body
    assert 'seg.className = "tabs-line popup-kinds picker-kinds"' in body
    assert "noteLabel(row, 70)" not in _function_body(source, "libraryPickLabel")


#: Script-built dialogs that still open on the confirm alert's `confirm-head`
#: (a question and its answers, which DESIGN.md exempts): may only fall. A
#: dialog that is not a question takes `dialogHead` (selection.js; INBOX 548).
CONFIRM_HEAD_DIALOGS = {"app.js": 1}


def test_a_script_built_dialog_opens_with_the_dialog_head() -> None:
    counts = {}
    for path in JS:
        n = path.read_text(encoding="utf-8").count('"row confirm-head"')
        if n:
            counts[path.name] = n
    assert counts == CONFIRM_HEAD_DIALOGS, (
        f"confirm-head dialogs are now {counts}: a new dialog takes dialogHead(title, close); "
        "a converted one lowers CONFIRM_HEAD_DIALOGS"
    )

#: Lists that still build their own `role="option"` rows. May only fall:
#: convert one to `richPickerRow` and lower its count here (the test fails
#: until you do, so the ratchet cannot silently loosen). The ones meant to
#: stay are not pickers of this shape: the document's word completion is an
#: inline ghost of the next word, the enhanced select is a `<select>`'s own
#: list, and a space's icon choice is a grid of glyphs. The Manage categories
#: panel left this list for a grid (INBOX 433: an option may not hold its ⋯).
#: The board library's tiles are the same shape as a space's icons: a grid of
#: pictures you place, walked in two directions, each opening its menu by
#: right-click or Shift+F10 rather than holding a ⋯ (WHITEBOARD_PLAN decision
#: 25; DESIGN.md, "A grid of things you place"). The icon and emoji picker is
#: the third grid of glyphs (MINDMAP_PLAN decision 43; DESIGN.md, "An icon or
#: an emoji, picked or dragged"): its tiles are dragged as well as picked.
HAND_BUILT_OPTION_ROWS = {"documents.js": 1, "icon-picker.js": 1, "sheets-selects.js": 1, "search.js": 1, "spaces-find.js": 1, "whiteboard-library.js": 1}


def test_only_the_rich_picker_stamps_its_anatomy() -> None:
    stamp = re.compile(
        r"""(?:className\s*[=+]|classList\.(?:add|toggle)\()[^;\n]*["'`][^"'`]*\brich-picker-(?:"""
        + "|".join(re.escape(part) for part in RICH_PICKER_PARTS)
        + r""")\b"""
    )
    for path in JS:
        if path.name == "rich-picker.js":
            continue
        for number, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
            assert not stamp.search(line), (
                f"{path.name}:{number} stamps a rich picker class by hand; build the row with "
                "richPickerRow / richPickerGroup / richPickerPreview (rich-picker.js)"
            )


def test_every_rich_picker_draws_its_rows_through_the_recipe() -> None:
    for name, function in RICH_PICKERS:
        body = _function_body(frontend_text(name), function)
        assert "richPickerRow(" in body, f"{name} {function} no longer draws its rows with richPickerRow"


def test_a_palette_keycap_names_a_real_shortcut() -> None:
    """A palette row's keycap is read from the shortcut registry by name
    (`chord`), so a row naming a chord that does not exist draws no key at
    all, silently. Every name has to be in `DEFAULT_SHORTCUTS`."""
    app = app_js_text()
    table = app[app.index("const DEFAULT_SHORTCUTS = {") :]
    table = table[: table.index("\n};")]
    registry = set(re.findall(r"^\s{2}(\w+): \{ keys:", table, re.M))
    commands = _function_body(app, "paletteCommands")
    chords = re.findall(r'chord: "(\w+)"', commands)
    assert len(chords) >= 10, f"only {len(chords)} palette rows say their chord"
    missing = sorted(set(chords) - registry)
    assert not missing, f"palette rows name chords the registry does not have: {missing}"


def test_hand_built_option_rows_do_not_multiply() -> None:
    option = re.compile(r"""setAttribute\("role", "option"\)|\.role\s*=\s*["']option["']""")
    counts = {}
    for path in JS:
        if path.name == "rich-picker.js":
            continue
        n = len(option.findall(path.read_text(encoding="utf-8")))
        if n:
            counts[path.name] = n
    for name, n in counts.items():
        assert n <= HAND_BUILT_OPTION_ROWS.get(name, 0), (
            f"{name} builds {n} role=option rows by hand; a list of choices picked by typing or "
            "browsing is the rich picker (richPickerRow, rich-picker.js; DESIGN.md's recipe index)"
        )
    assert counts == HAND_BUILT_OPTION_ROWS, (
        f"a list moved to the rich picker: lower HAND_BUILT_OPTION_ROWS to {counts}"
    )


# A dialog's head (DESIGN.md, "A dialog's head"; INBOX 431 f): title, its
# '?' beside it, then icon-only actions with Close last, all
# `.dialog-head`/`.dialog-head-actions`/`.dialog-head-btn`. Rolled out to
# doc-ai (the reference), Notifications, Earlier versions, Connections, the
# bin, Keyboard shortcuts, Tools & features, Meeting notes, Improve writing,
# Quick sketch and now Settings (`settings-close` kept its outer
# `.row.space-between`, the width-breakpoint rule's own selector, and only
# grew a `.dialog-head-actions` wrapper around the button itself, so the
# 10-responsive.css rule needed no change). Empty on purpose: the next
# offender is a real one.
DIALOG_HEAD_TEXT_CLOSE_DRIFT: set[str] = set()


def test_a_dialog_head_close_is_the_icon_recipe_not_a_text_button() -> None:
    """A modal head's Close is the recipe's icon-only ghost X, not a plain
    word. `skill-run-cancel` and `chat-compress-cancel` are not dialog heads
    (a form's Cancel and an inline panel's Cancel) and are not counted."""
    html = (ROOT / "frontend" / "index.html").read_text(encoding="utf-8")
    offenders = set(re.findall(r'<button id="([a-z0-9-]+-close)" class="ghost small">Close</button>', html))
    unknown = sorted(offenders - DIALOG_HEAD_TEXT_CLOSE_DRIFT)
    assert unknown == [], (
        f"{unknown} closes a dialog with a text button instead of the "
        "dialog-head recipe's icon-only ghost X (DESIGN.md, \"A dialog's head\")"
    )
    assert offenders <= DIALOG_HEAD_TEXT_CLOSE_DRIFT, (
        "a text Close button was fixed: shrink DIALOG_HEAD_TEXT_CLOSE_DRIFT to match"
    )


def test_the_dialog_head_button_recipe_has_one_shared_definition() -> None:
    """The doc-ai panel's head used to size its buttons with its own
    surface-scoped rule (`.doc-ai-card .doc-ai-head-btn.ghost`); that fork is
    exactly what the shared `.dialog-head-btn` recipe replaces, so it must
    not come back, in doc-ai's file or anywhere else."""
    for path in CSS:
        css = re.sub(r"/\*.*?\*/", "", path.read_text(encoding="utf-8"), flags=re.S)
        assert ".doc-ai-head" not in css, (
            f"{path.name} still styles .doc-ai-head*; the recipe is the shared "
            ".dialog-head/.dialog-head-actions/.dialog-head-btn (08-consistency.css)"
        )
    consistency = (ROOT / "frontend" / "css" / "08-consistency.css").read_text(encoding="utf-8")
    assert "--dialog-head-btn-size" in consistency
    assert ".dialog-head-btn.ghost" in consistency, (
        "the shared dialog-head-btn sizing rule has moved or gone missing"
    )
    assert ":focus-visible" in consistency[consistency.index("dialog-head") :], (
        "the dialog-head recipe lost its visible :focus-visible ring"
    )


def test_every_dialog_head_action_carries_the_recipe_class() -> None:
    """A button inside `.dialog-head-actions`, or the '?' sitting directly in
    `.dialog-head`, is unstyled without `.dialog-head-btn`: the shared rule
    is ancestor-scoped (three classes deep, to outrank
    `button.small.icon-only`'s padding), so a button that forgets the class
    renders with the wrong padding and no ring, silently."""
    html = (ROOT / "frontend" / "index.html").read_text(encoding="utf-8")
    for match in re.finditer(r'<span class="[^"]*dialog-head-actions[^"]*">(.*?)</span>', html, re.S):
        for btn in re.finditer(r"<button\b[^>]*>", match.group(1)):
            assert "dialog-head-btn" in btn.group(0), (
                f"a button in a .dialog-head-actions group is missing dialog-head-btn: {btn.group(0)[:80]}"
            )


def test_a_field_is_the_button_s_shape():
    """Fields, selects and the custom select's opener take the button's corner.

    The consistency pass (scratchpad/ui-sweeps/consistency.js, 1093, 1440 and
    390): fields came out at two radii, 6.4px (`--radius-lg`, the base rule)
    and 5.6px (`calc(var(--radius) * 0.7)`, on no tier, from a later global
    rule), beside 4.8px buttons, so a filter and its New button, or magic add
    and Add, were two shapes; the header's icon buttons sat at 2px, the
    concentric corner of a shell that no longer exists. Now every control
    outside a bar is on a tier and fields match buttons.
    """
    text = "\n".join(p.read_text(encoding="utf-8") for p in CSS)
    assert "calc(var(--radius) * 0.7)" not in re.sub(r"/\*.*?\*/", "", text, flags=re.S)
    forms = (ROOT / "frontend" / "css" / "01-forms-settings.css").read_text(encoding="utf-8")
    base = next(body for sel, body in _rules(forms) if 'input[type="datetime-local"]' in sel and "box-sizing: border-box" in body)
    assert "border-radius: var(--radius-md)" in base
    misc = "\n".join((ROOT / "frontend" / "css" / name).read_text(encoding="utf-8") for name in ("07-whiteboard-misc.css", "library-lazy.css"))
    opener = next(body for sel, body in _rules(misc) if sel.strip() == ".select-opener")
    assert "border-radius: var(--radius-md)" in opener


def test_a_dialog_head_title_out_ranks_the_card_heading_margin():
    """`.card h2` (0,1,1) kept its bottom margin over `.dialog-head-title`
    (0,1,0), so every recipe dialog's title sat 4.8px above its buttons'
    centre line (scratchpad/ui-sweeps/dialogheads.js). The reset needs two
    classes."""
    consistency = (ROOT / "frontend" / "css" / "08-consistency.css").read_text(encoding="utf-8")
    rule = next(body for sel, body in _rules(consistency) if ".dialog-head > .dialog-head-title" in sel)
    assert "margin: 0" in rule


# --- one popup, three tiers (INBOX 456; DESIGN.md, "A popup window or panel") ---
# The owner: "make sure all the popup windows and panels are the same design
# and style." Measured with scratchpad/ui-sweeps/popupinv.js (42 surfaces, 1440
# and 390, light and dark): the dialogs shared a shell; the heads did not (a
# 12px uppercase title, a worded Cancel where the recipe has the X, a 28px X
# beside a 32px one) and the panels came in three radii and four paddings.

# Closes that are not a popup's: an in-page panel (a column, a sidebar, a bar)
# or a search's own clear. They keep their own 28px ghost until their panels
# are folded into the recipe. May only shrink.
IN_PAGE_CLOSE_DRIFT = {
    "ask-history-close", "notes-rail-close", "web-panel-close", "doc-find-close",
    "wb-search-close", "wb-empty-hint-close", "global-find-close",
}


def test_every_popup_close_is_the_dialog_head_button() -> None:
    """A `*-close` icon button in index.html is `.dialog-head-btn`, which is
    what makes it 32px (44 on touch), quiet, ringed on focus and at the same
    corner of every popup. Before: twelve popups drew a 28px or 36px X of their
    own beside a 32px one."""
    html = (ROOT / "frontend" / "index.html").read_text(encoding="utf-8")
    offenders = set()
    for m in re.finditer(r'<button\b[^>]*\bid="([a-z0-9-]+-close)"[^>]*>', html):
        if "dialog-head-btn" not in m.group(0):
            offenders.add(m.group(1))
    unknown = sorted(offenders - IN_PAGE_CLOSE_DRIFT)
    assert unknown == [], (
        f"{unknown} closes a popup without `dialog-head-btn` (DESIGN.md, \"A dialog's head\")"
    )
    assert offenders >= IN_PAGE_CLOSE_DRIFT, (
        "an in-page close joined the recipe: shrink IN_PAGE_CLOSE_DRIFT to match"
    )


def test_every_small_dialog_opens_with_the_dialog_head() -> None:
    """Each `<dialog class="card space-dialog">` names itself in a
    `.dialog-head` (title, then a Close) rather than a bare `h3`, which the
    eyebrow rule drew at 12px uppercase beside the 16px head of every other
    dialog."""
    html = (ROOT / "frontend" / "index.html").read_text(encoding="utf-8")
    dialogs = re.findall(r"<dialog\b[^>]*space-dialog[^>]*>(.*?)</dialog>", html, re.S)
    #: 12 since the Tensions dialog became the suggestions sheet (KG9).
    assert len(dialogs) >= 12, "the small dialogs moved: this lint is looking at the wrong markup"
    for body in dialogs:
        first = body.lstrip()[:400]
        assert 'class="dialog-head' in first, f"a small dialog opens without .dialog-head: {first[:120]!r}"
        head = body[body.index('class="dialog-head') :][:1800]
        assert "dialog-head-title" in head, f"a small dialog's head has no .dialog-head-title: {head[:120]!r}"
        assert "dialog-head-btn" in head and "ph-x" in head, f"a small dialog's head has no Close: {head[:120]!r}"


def test_a_sheet_s_head_and_close_are_the_dialog_head_recipe() -> None:
    """`openSheet` is the one builder of sheets; its head, title and X are the
    recipe's classes, so every sheet's close is the dialog head's close."""
    text = (ROOT / "frontend" / "js" / "phone-shell.js").read_text(encoding="utf-8")
    start = text.index("function openSheet(")
    body = text[start : start + 6000]
    assert 'head.className = "sheet-head dialog-head"' in body
    assert 'title.className = "sheet-title dialog-head-title"' in body
    assert "dialog-head-btn sheet-close" in body


def test_the_dialog_head_title_is_one_size_whatever_tag_carries_it() -> None:
    """`.card h3` is the 12px uppercase eyebrow; a head written as `h3` or
    `strong` was a different surface (Quick note measured 12px uppercase beside
    Earlier versions' 16px)."""
    consistency = (ROOT / "frontend" / "css" / "08-consistency.css").read_text(encoding="utf-8")
    rule = next(body for sel, body in _rules(consistency) if sel.strip() == ".dialog-head .dialog-head-title")
    assert "font-size: var(--text-body)" in rule
    assert "text-transform: none" in rule


# The dialog and sheet shells, then the panels: one radius token each. The last
# declaration in file order is the one that paints (the stylesheets are
# concatenated 00 to 10), so that is the one asserted.
DIALOG_TIER = {"modal-card", "space-dialog", "sheet-card", "sheet-card-corner", "command-palette-card",
               "finder-card", "confirm-card"}
PANEL_TIER = {"notif-panel", "note-picker-panel", "agent-monitor", "graph-popup", "graph-new", "tour-card",
              "wb-navigator"}


def _last_radius_by_class() -> dict[str, str]:
    last: dict[str, str] = {}
    for path in CSS:
        for selector, body in _rules(path.read_text(encoding="utf-8")):
            m = re.search(r"(?<![\w-])border-radius:\s*([^;]+);", body)
            if not m:
                continue
            for part in selector.split(","):
                tail = re.split(r"[\s>+~]+", part.strip())[-1].split(":")[0]
                if re.search(r"[#\[]", tail):
                    continue
                for cls in re.findall(r"\.([\w-]+)", tail):
                    if cls in DIALOG_TIER | PANEL_TIER:
                        last[cls] = m.group(1).strip()
    return last


def test_dialogs_and_panels_share_one_radius_token() -> None:
    """Dialogs, sheets and panels are `--radius` (a sheet's bottom corners 0);
    only the anchored popover shell is `--radius-lg`. The notifications panel
    sat in the popover shell and drew 6.4px beside every other panel's 8px."""
    last = _last_radius_by_class()
    allowed = re.compile(r"(var\(--radius\)|0)( (var\(--radius\)|0))*")
    bad = {cls: value for cls, value in last.items() if not allowed.fullmatch(value)}
    assert bad == {}, f"a dialog or panel has its own corner: {bad}"
    assert "notif-panel" in last and "agent-monitor" in last
    misc = "\n".join((ROOT / "frontend" / "css" / name).read_text(encoding="utf-8") for name in ("07-whiteboard-misc.css", "library-lazy.css"))
    shell = next(body for sel, body in _rules(misc) if ".help-popover" in sel and ".action-menu" in sel and "border-radius" in body)
    assert "border-radius: var(--radius-lg)" in shell, "the popover shell's corner moved off --radius-lg"


def test_the_panel_tier_is_padded_by_one_token() -> None:
    """The floating panels (notifications, agent activity, the node popup, the
    tour's card, the board overview) are padded `--panel-pad`; they were
    9.6, 12.8, 16 and 8px."""
    consistency = (ROOT / "frontend" / "css" / "08-consistency.css").read_text(encoding="utf-8")
    assert "--panel-pad: var(--space-5)" in consistency
    rule = next(body for sel, body in _rules(consistency) if ".card.agent-monitor" in sel and ".notif-panel" in sel)
    assert "padding: var(--panel-pad)" in rule
    chat = (ROOT / "frontend" / "css" / "04-chat-dock-appearance.css").read_text(encoding="utf-8")
    assert "--graph-popup-pad: var(--panel-pad)" in chat
    assert "note-picker-panel" in next(sel for sel, _ in _rules(consistency) if ".card.agent-monitor" in sel)
    assert "padding: var(--panel-pad)" in re.search(r"\.note-picker-panel \{[^}]*\}", chat).group(0)


def test_the_attach_picker_is_a_panel_on_the_dialog_recipe() -> None:
    """INBOX 467, the owner: the Attach picker "need[s] a redesign to be
    consistent with the others". Its head is the dialog head, its segment the
    app's `.seg`, its rows the name over one muted line with the category as a
    dot and quiet text (never a filled badge), its footer the dialog footer
    recipe (`.space-dialog-actions`, a ghost then the one filled action)."""
    html = (ROOT / "frontend" / "index.html").read_text(encoding="utf-8")
    start = html.index('id="note-picker-panel"')
    panel = html[start : html.index('id="chat-model-panel"', start) if 'id="chat-model-panel"' in html[start:] else start + 6000]
    assert 'class="dialog-head"' in panel and "dialog-head-btn" in panel
    assert 'class="tabs-line popup-kinds note-picker-sources"' in panel
    assert 'class="row space-dialog-actions note-picker-foot"' in panel
    assert 'id="note-picker-clear" class="ghost"' in panel and 'id="note-picker-done" class="accent"' in panel
    js = (ROOT / "frontend" / "js" / "chat-attach.js").read_text(encoding="utf-8")
    assert 'cat.className = "chip"' not in js and 'kind.className = "chip"' not in js, (
        "a picker row's category or kind is quiet text on the second line, not a filled chip"
    )
    assert "note-picker-category" in js and "paintCategoryDot(cat, entry.category)" in js


def test_the_search_field_input_beats_the_global_field_rule() -> None:
    """INBOX 485, the owner: "there is an overlapping textbox??". The input
    inside a `.search-field` well turned its own box off with one class
    (0,1,0), which lost to the global `input[type="search"]` rule (0,1,1)
    whenever the field was not focused: a 42px bordered box drawn 5px above
    the 32px well. The reset is two classes, for rest, hover and focus."""
    css = "\n".join(path.read_text(encoding="utf-8") for path in CSS)
    rules = [(sel, body) for sel, body in _rules(css) if "search-field-input" in sel]
    selectors = [sel for sel, _ in rules]
    reset = next(sel for sel, body in rules if "border: 0 none" in body)
    for state in ("", ":hover", ":focus"):
        assert f".search-field > .search-field-input{state}" in reset, f"the reset misses {state or 'rest'}"
    assert not any(re.fullmatch(r"\.search-field-input(:\w+)?", part.strip()) for sel in selectors for part in sel.split(",")), (
        "a one-class `.search-field-input` rule loses to `input[type=search]`; write `.search-field > .search-field-input`"
    )


def test_the_attach_panel_rows_are_one_renderer_with_keys() -> None:
    """INBOX 485, the owner: "that whole panel needs to be better redesigned".
    Every source draws its rows through `notePickerRow` (a leading tile or the
    picture, the name over one muted line, a check at the right, the real
    checkbox visually hidden), pictures are a grid, and the keys walk it:
    arrows, Home and End, Enter is Done, the tabs' arrows switch source."""
    js = (ROOT / "frontend" / "js" / "chat-attach.js").read_text(encoding="utf-8")
    # The list renderer is lazy (attach-to.js, op4-1005); the row is lazy too
    # (pick-row.js), named by the attachTo and library bundles.
    lazy = (ROOT / "frontend" / "js" / "attach-to.js").read_text(encoding="utf-8") + "\nfunction "
    render = _function_body(lazy, "renderNotePickerList")
    assert "async function renderNotePickerList" not in js
    assert "notePickerRow(shape, row)" in render and "renderNotePickerOtherSource" not in js
    row_js = (ROOT / "frontend" / "js" / "pick-row.js").read_text(encoding="utf-8") + "\nfunction "
    row = _function_body(row_js, "notePickerRow")
    assert '"visually-hidden note-picker-box"' in row and "richPickerTile(" in row and "note-picker-check" in row
    assert "grid: true" in _function_body(js, "notePickerShape")
    keys = _function_body(js, "notePickerKeydown")
    for key in ("ArrowDown", "ArrowUp", "ArrowLeft", "ArrowRight", "Home", "End", "Enter"):
        assert f'"{key}"' in keys, f"the Attach panel lost its {key}"
    wiring = (ROOT / "frontend" / "js" / "wiring.js").read_text(encoding="utf-8")
    assert "notePickerKeydown(event)" in wiring
    # The two image tables number their rows separately: a note's picture is
    # sent as a file, never as a media upload id.
    shape = _function_body(js, "notePickerShape")
    assert 'row.store === "file") return attachLibraryFile(' in shape
    html = (ROOT / "frontend" / "index.html").read_text(encoding="utf-8")
    assert 'data-help-for="note-picker-help"' in html and 'id="note-picker-help"' in html


def test_enter_on_an_attach_row_ticks_it_and_keeps_focus() -> None:
    """INBOX 1300 C09: arrows down the list then Enter did nothing the owner
    expected (it closed the panel as Done with the row unticked). Enter on a
    row ticks it like Space; Enter in the search field is still Done."""
    js = (ROOT / "frontend" / "js" / "chat-attach.js").read_text(encoding="utf-8")
    keys = _function_body(js, "notePickerKeydown")
    enter = keys[keys.index('event.key === "Enter"', keys.index("if (at < 0) return;")) :]
    enter = enter[: enter.index("} else if")]
    assert "target.click()" in enter and "note-picker-done" not in enter


def test_the_attach_picker_rows_show_what_they_hold() -> None:
    """UI_MODERNISATION_PLAN, "the picker's other four sources have no
    thumbnail" (op4-1005): a map's row draws the map (`mapPreview` at its row
    size), a PDF's row its first page where the server can draw one, a
    document's row its kind (prose, table, code); all inside the one 2rem
    tile, so a row's height is unchanged, and a page that fails to load
    puts the glyph back."""
    js = app_js_text()
    shape = _function_body(js, "notePickerShape")
    assert 'face: (row) => mapPreview(row, { size: "row" })' in shape
    assert "row.has_pages ? notePickerPage(" in shape
    assert '"ph:file-code"' in shape and '"ph:table"' in shape
    row = _function_body(js, "notePickerRow")
    assert "face: shape.face?.(row)" in row
    assert 'tile.addEventListener("error"' in row and "tile.replaceWith(richPickerTile(" in row
    css = (ROOT / "frontend" / "css" / "05-sidebars-themes.css").read_text(encoding="utf-8")
    assert ".rich-picker-tile-face > :is(img, svg)" in css


def test_every_dialog_dims_the_page_with_the_one_scrim_token() -> None:
    """The dim behind a dialog is `var(--scrim)`. It was four values (a literal
    `rgba(10, 12, 18, 0.45)` on the 26 modal dialogs, `rgba(10, 12, 24, 0.45)`
    on three more, the token on the popup agent and nothing at all on Find
    anything, whose `.lock-overlay` painted the opaque page and hid the app)."""
    for path in CSS:
        for selector, body in _rules(path.read_text(encoding="utf-8")):
            m = re.search(r"(?<![\w-])background:\s*([^;]+);", body)
            if m and re.search(r"rgba\(\s*10,\s*12,\s*(18|24)", m.group(1)):
                raise AssertionError(f"{path.name}: {selector!r} dims with a literal; use var(--scrim)")
    misc = "\n".join((ROOT / "frontend" / "css" / name).read_text(encoding="utf-8") for name in ("07-whiteboard-misc.css", "library-lazy.css"))
    rule = next(body for sel, body in _rules(misc) if ".command-palette-overlay" in sel and ".finder-overlay" in sel)
    assert "background: var(--scrim)" in rule, "Find anything must dim the app like the popup agent does, not replace it"


def test_a_hovered_row_keeps_its_hint_readable():
    """A settings row's hover is `--row-hover-bg`, never the pressed button
    tone: `--ghost-btn-bg-hover` put the row's muted hint at 3.85:1 in light
    and 3.23:1 in dark (scratchpad/ui-sweeps/rowhover.js); the chosen row's
    20% accent hover put it at 4.12:1. Now 4.77:1 and 5.29:1 at worst."""
    text = "\n".join(p.read_text(encoding="utf-8") for p in CSS)
    tokens = (ROOT / "frontend" / "css" / "00-tokens-shell.css").read_text(encoding="utf-8")
    assert tokens.count("--row-hover-bg:") == 3, "light, dark and the system-dark block"
    for selector in ('.setting-check:has(input[type="checkbox"]:checked):hover', "  .check-row:hover", "  .setting-check:hover"):
        #: The rule may carry the hover's focus twin after it (Phase 13 decision 15).
        m = re.search(re.escape(selector) + r"(?:,\s*[^{,]+)*\s*\{([^}]*)\}", text)
        assert m, selector
        body = m.group(1)
        assert "var(--row-hover-bg)" in body and "--ghost-btn-bg-hover" not in body, selector


def test_no_glassmorphism_generator_shadow():
    """Shadows are cast in the app's ink, never the blue-violet
    `rgba(31, 38, 135, ...)` glassmorphism generators print by default, a
    recognisable tell of a generated interface (scratchpad/ui-sweeps/devibe.js
    found it on every floating action button, blurred 40px)."""
    text = "\n".join(p.read_text(encoding="utf-8") for p in CSS)
    code = re.sub(r"/\*.*?\*/", "", text, flags=re.S)
    assert not re.search(r"rgba\(\s*31,\s*38,\s*135", code)


# ---- A choice among colours: the swatch picker (INBOX 441 (4)) -------------


def test_a_swatch_is_drawn_only_by_the_swatch_picker() -> None:
    """DESIGN.md "A choice among colours": one builder, `swatchPicker`
    (categories-panel.js), a radiogroup whose every swatch names itself and
    whose arrows move the choice. A second hand-built row of colour dots would
    bring back the accent swatches' problems (no name, no keys, no ring)."""
    for path in JS:
        text = path.read_text(encoding="utf-8")
        if path.name == "categories-panel.js":
            continue
        assert "swatch-option" not in text, f"{path.name} builds a swatch by hand; use swatchPicker"
    body = _function_body(frontend_text("categories-panel.js"), "swatchPicker")
    assert 'setAttribute("role", "radiogroup")' in body
    assert 'setAttribute("role", "radio")' in body
    assert 'setAttribute("aria-label"' in body, "a swatch with no name says nothing to a screen reader"
    assert 'setAttribute("aria-checked"' in body
    for key in ("ArrowRight", "ArrowLeft", "ArrowUp", "ArrowDown", "Home", "End"):
        assert key in body, f"the swatch picker does not answer {key}"
    assert ".style.setProperty(" in body and "style=" not in body, "paint through the CSSOM, not style="


def test_a_swatch_shows_focus_and_its_choice_without_colour() -> None:
    css = re.sub(r"/\*.*?\*/", "", "\n".join(p.read_text(encoding="utf-8") for p in CSS), flags=re.S)
    focus = [b for sel, b in _rules(css) if ".swatch-option:focus-visible" in sel]
    assert focus and "outline" in focus[0], "a swatch needs a visible focus ring"
    checked = [b for sel, b in _rules(css) if '.swatch-option[aria-checked="true"]' in sel and "box-shadow" in b]
    assert checked, "the checked swatch must be a shape (a ring), not only a colour"


def test_the_colour_item_is_on_a_categorys_menu_and_loads_lazily() -> None:
    notes = frontend_text("notes-list.js")
    assert "pickCategoryColour(meta)" in notes
    assert '"pickCategoryColour"' in (ROOT / "frontend" / "js" / "app.js").read_text(encoding="utf-8")


# --- a Settings section's own index, and the setting search (INBOX 444) ----------


def _css_block(selector: str) -> str:
    """The body of the first rule whose selector is exactly this one."""
    css = re.sub(r"/\*.*?\*/", "", "\n".join(p.read_text(encoding="utf-8") for p in CSS), flags=re.S)
    match = re.search(re.escape(selector) + r"\s*\{([^{}]*)\}", css)
    assert match, f"no rule for {selector}"
    return match.group(1)


def test_a_settings_pane_lists_its_groups_in_the_sidebar() -> None:
    """DESIGN.md, "A long Settings section's index" (INBOX 622). The pane's
    group links are the sidebar's second level under the pane's own link, not
    a strip in the pane that scrolls sideways. The pane's dock still sticks
    (`position: sticky`) on `--modal-bg-opaque`, never a tint alone; the links
    are the Quiet tier (no fill at rest) and the one you are in is painted from
    `aria-current` with a weight step and an accent rail, not a class and not a
    second fill beside the pane's own."""
    bar = _css_block("#settings-modal .settings-section > .dock")
    assert "position: sticky" in bar and "var(--modal-bg-opaque)" in bar
    link = _css_block("#settings-nav .settings-nav-group")
    assert "background: transparent" in link and "box-shadow: none" in link
    current = _css_block('#settings-nav .settings-nav-group[aria-current="location"]')
    assert "var(--accent)" in current and "font-weight: 650" in current
    assert "--accent-surface" not in current and "background" not in current
    code = (ROOT / "frontend" / "js" / "settings-find.js").read_text(encoding="utf-8")
    assert "scrollIntoView" not in re.sub(r"//.*", "", code), "scroll the pane's own scrollTop"
    assert code.count('"settings-nav-groups"') >= 1 and "aria-current" in code


def test_the_setting_search_results_are_quiet_rows() -> None:
    """The results are rows in a list the search field frames, so no row is a
    filled button: one name over one line saying where it is."""
    row = _css_block(".settings-result")
    assert "--accent-surface" not in row and "box-shadow" not in row
    assert "flex-direction: column" in row


def test_a_model_card_is_the_surface_three_tile_with_one_primary_action() -> None:
    """DESIGN.md, "A model you can download, install or use". The card sits on
    the surface-3 tier inside the group's surface-2 and draws no border (the
    border budget), and the code that builds it makes one primary action and
    never a filled button of its own choosing: the filled tier is for the
    group's starting pick."""
    card = _css_block(".model-card")
    assert "var(--surface-3)" in card
    assert "border: 1px solid transparent" in card
    code = (ROOT / "frontend" / "js" / "settings-models.js").read_text(encoding="utf-8")
    assert code.count('classList.add("model-card-primary")') == 1, "one primary action per card"
    assert "const filled = !!model.recommended || !!model.custom;" in code
    assert "innerHTML" not in code
    # Fit is the server's verdict, never recomputed in the page.
    assert "fit_for" not in code and "FITS_BELOW" not in code


class _SettingsFilledButtons(HTMLParser):
    """Counts the filled buttons written into each Settings section's markup:
    a `<button>` that is not ghost, a link, an icon, a switch, part of a
    segmented well, hidden, or a card/tile/swatch that only looks like one."""

    QUIET = {"ghost", "linklike", "icon-only", "icon-button", "hidden", "doc-dock-menu-item"}
    WELLS = {"seg", "segmented-control", "accent-swatches", "theme-presets", "theme-grid"}
    VOID = {"area", "base", "br", "col", "embed", "hr", "img", "input", "link", "meta", "source", "track", "wbr"}

    def __init__(self) -> None:
        super().__init__()
        self.stack: list[tuple[str, set[str], str | None]] = []
        self.filled: dict[str, list[str]] = {}

    def handle_starttag(self, tag, attrs):
        a = dict(attrs)
        classes = set((a.get("class") or "").split())
        section = a.get("id") if tag == "section" and "settings-section" in classes else None
        if tag == "button":
            owner = next((s for _, _, s in reversed(self.stack) if s), None)
            in_well = any(c & self.WELLS for _, c, _ in self.stack)
            looks_like = any(k in c for c in classes for k in ("card", "tile", "swatch", "color"))
            if owner and not in_well and not looks_like and not classes & self.QUIET \
                    and a.get("role") != "switch":
                self.filled.setdefault(owner, []).append(a.get("id") or "?")
        if tag not in self.VOID:
            self.stack.append((tag, classes, section))

    def handle_endtag(self, tag):
        for i in range(len(self.stack) - 1, -1, -1):
            if self.stack[i][0] == tag:
                del self.stack[i:]
                return


def test_a_settings_section_has_at_most_one_filled_button() -> None:
    """DESIGN.md's button ramp: the filled tier is the one action a surface is
    for, one per page. Import & export carried five (Export full backup, Find
    duplicates, both Imports, Back up now), Appearance four, Personas and
    What it learned two each (INBOX 437 (4)); every other action on a
    Settings page is the tonal `ghost`."""
    parser = _SettingsFilledButtons()
    parser.feed((ROOT / "frontend" / "index.html").read_text(encoding="utf-8"))
    assert parser.filled, "the parser found no Settings sections"
    over = {s: ids for s, ids in parser.filled.items() if len(ids) > 1}
    assert not over, f"more than one filled button on a Settings page: {over}"


def test_a_facts_row_opens_its_lists_below_itself() -> None:
    """DESIGN.md, "A row of facts about a card where some facts open a list"
    (INBOX 450). The skill card's steps and tools are toggles in the facts row
    whose panels sit after the row, so opening one never reflows the row; no
    `<details>` is built into it; every fact is one height; and the cards are
    dealt into columns rather than laid in a grid whose rows stretch."""
    code = (ROOT / "frontend" / "js" / "library.js").read_text(encoding="utf-8")
    start = code.index("function skillCard(")
    card = code[start:code.index("\n}\n", start)]
    assert 'createElement("details")' not in card, "a facts row toggle is a button, not a <details>"
    assert '"ghost small skill-fact skill-fact-toggle"' in card
    assert 'setAttribute("aria-controls"' in card and 'setAttribute("aria-expanded"' in card
    assert "card.append(facts, ...panels)" in card, "the panels follow the row, never sit inside it"
    assert "--skill-fact-h" in _css_block(".skill-card")
    facts = _css_block(".skill-card .skill-card-facts > :is(.chip, button).skill-fact")
    assert "height: var(--skill-fact-h)" in facts and "white-space: nowrap" in facts
    render = code[code.index("function renderSkillCards("):]
    assert "skillColumnCount(grid)" in render[:4000], "skill cards are dealt into columns"
    assert "display: flex" in _css_block(".skills-grid")


def test_one_builder_draws_a_thinking_fold() -> None:
    """INBOX 457, the owner: "make sure all the thinking boxes are the same
    style and consistent". Five surfaces drew the model's reasoning and no two
    matched (Chat's caret-triangle fold, the popup agent's monospace tool-chip
    box, Ask's dashed "Model's thinking", the Guide's smaller copy, the writing
    room's "What Atlas was thinking"). `thinkingFold` (chat-agent.js) is the
    one builder; a second one, a fold in the markup, or a stylesheet giving
    one surface's body its own look fails here."""
    js = {path.name: path.read_text(encoding="utf-8") for path in JS}
    fold_classes = [
        (name, m.group(0))
        for name, text in js.items()
        for m in re.finditer(r'className\s*=\s*"[^"]*\b(?:thinking-fold|step-thinking|cmd-palette-thinking|help-chat-think|thinking-text)\b[^"]*"', text)
    ]
    #: The builder, plus Agent Activity's run row, which borrows the old
    #: disclosure look for a run (not reasoning) and says so in its class.
    allowed = {
        ("chat-agent.js", 'className = "agent-step thinking-fold"'),
        ("agent-activity.js", 'className = "agent-step step-thinking agent-run-step"'),
    }
    assert set(fold_classes) == allowed and len(fold_classes) == len(allowed), (
        f"a thinking fold built outside thinkingFold: {sorted(set(fold_classes) - allowed)}"
    )
    bodies = [name for name, text in js.items() for _ in re.finditer(r'className\s*=\s*"thinking"', text)]
    assert bodies == ["chat-agent.js"], f"the reasoning body is built in {bodies}"
    #: Every surface that shows reasoning asks the builder.
    for name, call in (
        ("chat-agent.js", "const el = thinkingFold();"),
        ("palette.js", "thinkingBox = thinkingFold();"),
        ("help-chat.js", "const think = thinkingFold();"),
        ("capture-ask.js", 'thinkingFoldIn(thinkingHost)'),
        ("writing-desk.js", 'thinkingFoldIn(thinkingHost)'),
    ):
        assert call in js[name], f"{name} no longer draws its reasoning with the one fold"
    html = re.sub(r"<!--.*?-->", "", (ROOT / "frontend" / "index.html").read_text(encoding="utf-8"), flags=re.S)
    assert not re.search(r"<details[^>]*>\s*<summary[^>]*>[^<]*thinking", html, flags=re.I), (
        "a thinking fold written into index.html instead of built by thinkingFold"
    )
    assert 'class="thinking' not in html
    #: One look: the body has one rule and no surface restyles it.
    selectors = [sel for path in CSS for sel, _ in _rules(path.read_text(encoding="utf-8"))]
    body_rules = [s for s in selectors if re.search(r"\.thinking(?![\w-])", s)]
    assert body_rules == [".thinking"], f"the thinking body is restyled per surface: {body_rules}"
    stale = [s for s in selectors if re.search(r"#thinking-box|#draft-thinking|help-chat-think|cmd-palette-thinking|thinking-text", s)]
    assert not stale, f"a surface's own thinking style came back: {stale}"


def test_a_managed_list_row_shows_its_count_as_quiet_text_never_a_pill() -> None:
    # INBOX 466, the owner: "it is wierd with all these numbers floating in
    # the manage categories popup". The count follows the name as muted text
    # ("Hobbies · 10"); a pill's ground, radius and padding do not come back.
    body = _css_block(".manage-cat-count")
    for banned in ("background", "border-radius", "padding", "min-width", "text-align: center"):
        assert banned not in body, f"the count is a pill again: {banned}"
    assert "color: var(--muted)" in body
    sheet = (ROOT / "frontend" / "css" / "04-chat-dock-appearance.css").read_text(encoding="utf-8")
    name = re.search(r"^\.manage-cat-name \{([^{}]*)\}", sheet, re.M).group(1)
    assert "flex: 0 1 auto" in name, "the name hugs its text so the count sits after it"
    design = (ROOT / "docs" / "DESIGN.md").read_text(encoding="utf-8")
    assert "never a pill: INBOX 466" in design


def test_an_assistant_head_asks_one_function_for_its_face() -> None:
    """INBOX 463 (2), the owner: "the user should be able to customise the
    assistant/ai chat message bubbles across all chat interfaces to be either
    atlas or the animated app logo". Appearance, Assistant avatar (`atlas`, the
    default, or `emblem`) is read by `assistantAvatar` (chat-agent.js) and
    nowhere else: every head of the app's own voice paints through it, so one
    setting changes them all and a new surface cannot draw a face of its own
    that ignores it."""
    js = {path.name: path.read_text(encoding="utf-8") for path in JS}
    #: Atlas's drawing calls belong to the decider, atlas.js and avatars.js
    #: (their own files), the welcome card's large greeting and Settings' find
    #: row (a result's icon, not a reply head).
    allowed = {"atlas.js", "avatars.js", "chat-agent.js", "settings-wiring.js", "onboarding.js", "settings-panes.js"}
    strays = [
        name
        for name, text in js.items()
        if name not in allowed and re.search(r"\batlas(?:Avatar|Draw|Mark)\(", re.sub(r"(?m)^\s*//.*$", "", text))
    ]
    assert not strays, f"a head draws Atlas on its own, ignoring Assistant avatar: {strays}"
    chat = js["chat-agent.js"]
    assert len(re.findall(r"\batlas(?:Avatar|Draw)\(size", chat)) == 2, "Atlas is drawn in assistantAvatar alone"
    #: Each reply head's holder is painted by the persona painter, which sends
    #: the app's own voice through the decider.
    for name, call in (
        ("chat-agent.js", "paintPersonaAvatar(avatar,"),
        ("palette.js", "paintPersonaAvatar(agentAvatar,"),
    ):
        assert call in js[name], f"{name}'s reply head no longer asks paintPersonaAvatar"
    assert "paintAssistantAvatar(host, size)" in js["atlas.js"], "the guide and agent heads skip the setting"
    assert "paintAssistantAvatar(mark," in js["help-chat.js"], "the guide sheet's head skips the setting"
    #: INBOX 471: Ask's answer, the writing room's draft and the guide's chat
    #: rows wear the same reply head (the face, then the name), painted through
    #: the same function, so the setting and its live repaint reach them.
    index_html = (ROOT / "frontend" / "index.html").read_text(encoding="utf-8")
    assert index_html.count("data-assistant-head") == 2, "Ask's answer and the draft each carry one static head holder"
    assert re.search(r'class="answer-title msg-role msg-role-assistant">\s*<span class="msg-avatar" data-assistant-head', index_html)
    assert re.search(r'<label for="draft-text"[^>]*>.{0,80}msg-avatar" data-assistant-head', index_html)
    assert "paintAssistantAvatar(holder, 20)" in chat[chat.index("function paintAssistantHeads") :][:200]
    #: `assistantHeadRow` moved to help-chat.js (lazy) with its only callers (Brief 101a).
    assert "paintAssistantAvatar(avatar, 20)" in js["help-chat.js"][js["help-chat.js"].index("function assistantHeadRow") :][:600]
    assert "paintAssistantHeads()" in js["navigation.js"], "a section change fills the static heads"
    guide = js["help-chat.js"]
    assert guide.count("assistantHeadRow(GUIDE_NAME)") == 4, "a guide row, its pending row, the streamed one and the revealed one each open with the head"
    #: The setting: a default, a control, a live repaint and a reset.
    settings = js["settings.js"]
    assert '"assistant-avatar": "atlas"' in settings
    assert "repaintAssistantAvatars()" in settings[settings.index('$("assistant-avatar").addEventListener') :][:300]
    index = (ROOT / "frontend" / "index.html").read_text(encoding="utf-8")
    assert 'id="assistant-avatar"' in index and '<option value="emblem">App emblem</option>' in index
    #: The emblem is the logo's own builder (`emblemArt`), never a second
    #: drawing of the mark, and a head is left out of the lift.
    assert "emblemArt(size, { head: true })" in js["assistant-avatar.js"]
    assert "renderEmblem(" not in chat


def test_board_text_is_made_editable_in_one_place() -> None:
    """WHITEBOARD_PLAN decision 12 added a third thing typed in place on the
    board (a shape's text, after a text box and a topic), and DESIGN.md's
    recipe index names the one way to do it: `wbBeginTextEdit` turns an
    element into a plain-text editor (so Enter is a line break the save can
    read, not a `<div>`) and `wbEndTextEdit` turns it back. An editor that
    sets `contenteditable` itself skips both halves, which is how "start",
    Enter, "- item" once saved as "start- item"."""
    for name in ("whiteboard.js", "whiteboard-map.js"):
        text = (ROOT / "frontend" / "js" / name).read_text(encoding="utf-8")
        code = re.sub(r"(?m)^\s*//.*$", "", text)
        makers = [
            m.start()
            for m in re.finditer(r"""(?:setAttribute\(\s*"contenteditable",\s*"(?:true|plaintext-only)"|contentEditable\s*=\s*["'](?:true|plaintext-only))""", code)
        ]
        begin = code.find("function wbBeginTextEdit(")
        end = code.find("\n}", begin)
        strays = [at for at in makers if not (begin != -1 and begin < at < end)]
        assert not strays, f"{name} makes board text editable outside wbBeginTextEdit ({len(strays)} places)"
    wb = (ROOT / "frontend" / "js" / "whiteboard.js").read_text(encoding="utf-8")
    #: A shape's text and a connector's label (decision 13) share one editor.
    edit = wb[wb.index("function wbOpenSketchLabelEditor(") :][:4000]
    assert "wbBeginTextEdit(editor)" in edit and "wbEditedText(editor)" in edit
    for caller in ("wbEditShapeLabel", "wbEditLinkLabel"):
        assert "wbOpenSketchLabelEditor(" in wb[wb.index(f"function {caller}(") :][:1500], caller


def test_a_frame_is_one_kind_reached_three_ways() -> None:
    """WHITEBOARD_PLAN decision 14 (DESIGN.md's frame row): one object kind,
    reached by the F key, the rail's Add section and the Insert menu, board
    only; its title typed through the board's one editor; its drag carrying
    what it holds through the bulk mover; its inside letting the pointer
    through; the Guide naming it."""
    wb = (ROOT / "frontend" / "js" / "whiteboard.js").read_text(encoding="utf-8")
    wbmap = (ROOT / "frontend" / "js" / "whiteboard-map.js").read_text(encoding="utf-8")
    index = (ROOT / "frontend" / "index.html").read_text(encoding="utf-8")
    css = "\n".join((ROOT / "frontend" / "css" / name).read_text(encoding="utf-8") for name in ("07-whiteboard-misc.css", "library-lazy.css"))
    assert 'f: "frame",' in wb
    assert '"sticky", "text", "frame",' in wbmap, "a map's F never picks the frame"
    assert 'data-tool="frame"' in index and 'data-wb-insert="frame"' in index
    assert "Frame (F)" in index
    edit = wb[wb.index("function wbEditFrameTitle(") :][:2000]
    assert "wbBeginTextEdit(titleEl, before)" in edit and "wbEndTextEdit(titleEl)" in edit
    # C17: the hint edits its own text, and an undo repaints what the edit wrote.
    assert "wbBeginTextEdit(titleEl, before)" in edit and "_wbPaintKey = null" in edit
    begin = wb[wb.index("function wbBeginTextEdit(") :][:900]
    assert "ownText !== undefined" in begin
    assert "|| wbFrameDragOrigin(d, d._dragAlone)" in wb
    assert "wbCaptureBulkMoveOrigin(null, keys)" in wb[wb.index("function wbFrameDragOrigin(") :][:400]
    frame_rule = css[css.index(".wb-object-frame {") :][:600]
    assert "pointer-events: none;" in frame_rule and "background: transparent;" in frame_rule
    guide = re.sub(r'"\s*\n\s*"', "", (ROOT / "src" / "tessellate" / "ai" / "help_chat.py").read_text(encoding="utf-8"))
    assert "F frame" in guide and "title drags it and what is inside it" in guide
    assert "Ctrl+Shift+L locks the selection" in guide


def test_a_locked_item_is_out_of_reach_in_one_way() -> None:
    """WHITEBOARD_PLAN decision 15 (DESIGN.md's lock row): a locked item lets
    the pointer through (one CSS rule, children named, above every per-part
    rule), and the selections that do not go through the pointer pass it by
    by asking `wbIsLocked`: Select all, the marquee, the lasso, a group's
    click and a frame's drag. The way back is on the board's own menu."""
    wb = (ROOT / "frontend" / "js" / "whiteboard.js").read_text(encoding="utf-8")
    css = "\n".join((ROOT / "frontend" / "css" / name).read_text(encoding="utf-8") for name in ("07-whiteboard-misc.css", "library-lazy.css"))
    assert "#whiteboard-container .wb-locked,\n#whiteboard-container .wb-locked * {\n  pointer-events: none;" in css
    assert "return out.filter(([kind, item]) => !wbIsLocked(kind, item) && !wbHiddenOnBoard(kind, item));" in wb
    assert wb.count('if (wbIsLocked("object", obj)) continue;') == 2, "the marquee and the lasso"
    assert wb.count("if (parsed.locked) continue;") == 2
    assert wb.count("if (node.locked) continue;") == 2
    assert "!wbIsLocked(memberKind, candidate)" in wb
    assert "if (!withLocked && wbIsLocked(kind, item)) continue;" in wb[wb.index("function wbFrameContents(") :][:800]
    assert "function wbFrameContents(frame, { withLocked = false } = {})" in wb, "a drag passes locked items by; only Export this frame takes them"
    assert "wbPaintLocks();" in wb[wb.index("function renderWhiteboard()") :]
    assert "Unlock ${locked} locked item" in wb


def test_drag_to_delete_is_one_target_on_the_three_drags() -> None:
    """INBOX 660 (DESIGN.md's drag-to-delete row): the three item drags (a
    card, a box or topic, a shape) mark their gesture as a move, and each
    one's end asks `wbTrashTake` before it saves anything, so a drop on the
    target is put back and then deleted, never saved and then deleted. The
    delete is the selection's own, one Undo step (`wbRecordGesture`) with a
    toast; the target is a floating panel (on the glass-off list), hidden
    from the tree, and its styles ride the Library bundle, not the boot CSS."""
    wb = (ROOT / "frontend" / "js" / "whiteboard.js").read_text(encoding="utf-8")
    lazy = (ROOT / "frontend" / "css" / "library-lazy.css").read_text(encoding="utf-8")
    for kind in ("sketch", "object", "node"):
        assert f'wbBeginGesture(() => wbRestoreMove("{kind}", d), true)' in wb, kind
        assert f'wbTrashTake(d._gesture, "{kind}", d);' in wb, kind
    assert wb.count("wbTrashTake(d._gesture,") == 3, "one target, asked at the three drags' ends and nowhere else"
    obj_end = wb[wb.index("async function objDragEnd(") :]
    assert obj_end.index("wbTrashTake(") < obj_end.index("delete d._bulkOrigin;"), "asked while the drag still holds its origin"
    node_end = wb[wb.index("async function dragEndNode(") :]
    assert node_end.index("wbTrashTake(") < node_end.index("await wbSaveNode(d);")
    delete = wb[wb.index("async function wbTrashDelete(") :]
    delete = delete[: delete.index("\n}\n")]
    assert "await wbRecordGesture(" in delete and 'toastAction(words, "Undo"' in delete
    take = wb[wb.index("function wbTrashTake(") :]
    take = take[: take.index("\n}\n")]
    assert "gesture.restore?.()" in take and "gesture.cancelled = true;" in take
    target = wb[wb.index("function wbTrashTarget(") :]
    target = target[: target.index("\n}\n")]
    assert '"whiteboard-floating-panel wb-trash card glass hidden"' in target
    assert 'setAttribute("aria-hidden", "true")' in target
    assert "!wbGesture.overTrash" in wb, "the edge pan holds still over the target"
    assert ".whiteboard-floating-panel.wb-trash {" in lazy and ".wb-trash.wb-trash-hot {" in lazy
    for css in CSS:
        if css.name != "library-lazy.css":
            assert "wb-trash" not in css.read_text(encoding="utf-8"), css.name


def test_presenting_is_one_mode_with_one_bar() -> None:
    """WHITEBOARD_PLAN decision 16 (DESIGN.md's presentation row): the View
    menu's row starts it, board only; one host class hides the chrome and
    makes the board a view; the keys are taken on the window in the capture
    phase so no board key acts; the bar's text is a polite live region."""
    wb = (ROOT / "frontend" / "js" / "whiteboard.js").read_text(encoding="utf-8")
    index = (ROOT / "frontend" / "index.html").read_text(encoding="utf-8")
    css = "\n".join((ROOT / "frontend" / "css" / name).read_text(encoding="utf-8") for name in ("07-whiteboard-misc.css", "library-lazy.css"))
    assert 'data-wb-fn="present" data-wb-surface="board"' in index
    assert 'data-wb-fn="present" data-wb-surface="map"' in index, "a map presents by branch (MINDMAP_PLAN 21)"
    #: Studying a map (MINDMAP_PLAN decision 36) is the same mode and bar.
    assert "return wbStudy.on ? wbMapStudySteps() : wbMapPresentSteps();" in wb
    assert 'id="wb-study-show"' in index and "wbMapEndStudy();" in wb
    assert 'if (item.dataset.wbFn === "present") { wbStartPresenting(); return; }' in wb
    assert 'id="wb-present-count" class="wb-present-count" aria-live="polite"' in index
    assert "#library-view-whiteboard.wb-presenting .wb-topbar," in css
    assert "#library-view-whiteboard.wb-presenting #wb-html-layer," in css
    keys = wb[wb.index("let wbPresent = null;") :]
    assert "event.stopImmediatePropagation();" in keys and "}, true);" in keys
    assert ".wb-board-menu [data-wb-surface]" in (ROOT / "frontend" / "js" / "whiteboard-map.js").read_text(encoding="utf-8")
    guide = (ROOT / "src" / "tessellate" / "ai" / "help_chat.py").read_text(encoding="utf-8")
    assert "Present frames: one frame" in guide


def test_the_text_box_grip_stands_on_an_opaque_ground() -> None:
    """The "⠿" tab on a text box or sticky's top edge: `--card-bg` is a glass
    in most looks, so on a sticky's yellow the muted glyph measured 1.68:1 in
    dark (`scratchpad/ui-sweeps/wbgripink.js`; 7.86:1 on the opaque ground)."""
    css = "\n".join((ROOT / "frontend" / "css" / name).read_text(encoding="utf-8") for name in ("07-whiteboard-misc.css", "library-lazy.css"))
    rule = css[css.index(".wb-object-grip {") :][:900]
    assert "background: var(--modal-bg-opaque);" in rule and "var(--card-bg)" not in rule.split("}")[0]


def test_a_maps_boundaries_and_summaries_are_drawn_in_one_pass() -> None:
    """MINDMAP_PLAN decisions 19 and 20 (DESIGN.md's row): one function draws
    both from where the topics are, after the lines on every render and on the
    selection bar's frame so a drag carries them; every change goes through
    the topic's one undo step; both reach the image export; neither takes the
    pointer; and a theme reset keeps them."""
    wb = (ROOT / "frontend" / "js" / "whiteboard.js").read_text(encoding="utf-8")
    wm = (ROOT / "frontend" / "js" / "whiteboard-map.js").read_text(encoding="utf-8")
    css = "\n".join((ROOT / "frontend" / "css" / name).read_text(encoding="utf-8") for name in ("07-whiteboard-misc.css", "library-lazy.css"))
    render = wb[wb.index("function renderWhiteboard()") :]
    assert render.index("wbRenderMapStructure();") > render.index("wbRenderMapEdges();")
    assert "if (wbIsMap()) wbRenderMapStructure();" in wb[wb.index("function wbQueueSelectionBar()") :][:400]
    setter = wm[wm.index("async function wbMapSetStructure(") :][:300]
    assert "await wbMapSetNodeStyle(node, patch);" in setter
    assert 'structure(".wb-map-boundaries > *")' in wb and 'structure(".wb-map-summaries > *")' in wb
    assert ".wb-map-boundaries,\n.wb-map-summaries {\n  --wb-boundary: var(--accent);\n  pointer-events: none;" in css
    for key in ("boundary", "boundary_label", "summary", "summary_span"):
        assert f'"{key}"' in wm[wm.index("const WB_MAP_CONTENT_KEYS") :][:200]


def test_a_topics_markers_are_one_row_from_one_icon_set() -> None:
    """MINDMAP_PLAN decision 34 (DESIGN.md's marker row): the marks are drawn
    by one function into one row from the paint pass, the icons come from a
    fixed Phosphor set with no emoji in it, every change is the topic's one
    undo step, and the markers are content (a branch copy keeps them)."""
    wm = (ROOT / "frontend" / "js" / "whiteboard-map.js").read_text(encoding="utf-8")
    paint = wm[wm.index("function wbPaintMapNodeStyle(") :][:6000]
    assert "wbMapPaintMarkers(markers, d.data || {});" in paint
    painter = wm[wm.index("function wbMapPaintMarkers(") :]
    painter = painter[: painter.index("\n}\n")]
    assert painter.count("wb-map-mark") >= 3 and wm.count("wb-map-mark ") == painter.count("wb-map-mark ")
    icons = wm[wm.index("const WB_MAP_MARKER_ICONS") :][:600]
    assert all(ord(ch) < 0x2000 for ch in icons), "an emoji in the marker set"
    assert "await wbMapSetNodeStyle(live, patch);" in wm[wm.index("function wbMapOpenMarkers(") :][:1500]
    keys = wm[wm.index("const WB_MAP_CONTENT_KEYS") :][:200]
    for key in ("priority", "progress", "flag", "markers"):
        assert f'"{key}"' in keys


def test_a_comment_thread_is_one_popover_reached_three_ways() -> None:
    """WHITEBOARD_PLAN decision 17 (DESIGN.md's comment row): the mark, the
    item menu and a topic's menu open the one thread, in the help popover's
    shell; every change goes through `wbSetComments`; the marks are painted
    after every render and follow a drag on the selection bar's frame."""
    wb = (ROOT / "frontend" / "js" / "whiteboard.js").read_text(encoding="utf-8")
    css = "\n".join((ROOT / "frontend" / "css" / name).read_text(encoding="utf-8") for name in ("07-whiteboard-misc.css", "library-lazy.css"))
    assert wb.count("wbOpenComments(") == 4, "the definition, the mark, the item menu, the topic menu"
    assert 'panel.className = "help-popover wb-comments";' in wb
    #: The window is the function's own length (it grew Attach and replies,
    #: 2026-10-10): the placing must still be inside it.
    opener = wb[wb.index("function wbOpenComments(") :]
    assert "placeHelpPopover(panel, target);" in opener[: opener.index("\nfunction ", 10)]
    assert wb.count("await wbSetComments(") == 2, "a post, and every change to a comment (reply, edit, resolve, delete)"
    assert "wbPaintCommentMarks();" in wb[wb.index("function renderWhiteboard()") :]
    assert "wbPaintCommentMarks();" in wb[wb.index("function wbQueueSelectionBar()") :][:300]
    assert '".wb-comment-pin",' in wb[wb.index("const WB_INV_ZOOM_GRIPS") :][:200]
    assert "#library-view-whiteboard.wb-presenting .wb-comment-marks {\n  display: none;" in css
    guide = re.sub(r'"\s*\n\s*"', "", (ROOT / "src" / "tessellate" / "ai" / "help_chat.py").read_text(encoding="utf-8"))
    assert "Right-click an item, Comment…" in guide and "Comment… starts a thread" in guide


def test_the_writing_rooms_selects_get_their_own_line_on_a_phone() -> None:
    """OPEN.md, "Writing Room at phone width": one nowrap row held what to
    write, tone, length and Use notes, so each select was 62px wide at 390 with
    its value cut to 16px. Below 600 the row wraps and the first select takes
    the line; `scratchpad/ui-sweeps/phonecapture.js` measures the three values
    (89, 65 and 59px shown of what they need)."""
    css = (ROOT / "frontend" / "css" / "04-chat-dock-appearance.css").read_text(encoding="utf-8")
    at = css.index("@media (max-width: 599.98px) {\n  .draft-controls.draft-desk-controls {")
    block = css[at : css.index("\n}\n", at)]
    assert "flex-wrap: wrap;" in block
    assert ".draft-desk-controls > .select-shell:first-child" in block and "flex-basis: 100%;" in block


def test_a_menu_fades_out_through_the_one_class_every_close_path_sets() -> None:
    """OPEN.md, perfpolish: menus left instantly though they entered with a
    reveal. Every close path (the opener again, Escape, a press outside,
    `closeActionMenus`) is `.hidden`, so the exit is CSS: opacity and a
    discrete `display` transition, no press taken while it goes. A menu moved
    to the body goes home after the fade, in both places that move one home
    (`closeActionMenus` and `wireEscapedActionMenu`'s observer), because moving
    a node cancels a transition. `scratchpad/ui-sweeps/kebabfirst.js` samples
    the frames: 4 part way, gone by about 150ms, on all eight kebab and select
    close paths."""
    css = (ROOT / "frontend" / "css" / "10-responsive.css").read_text(encoding="utf-8")
    # The motion pass (2026-10-05): the exit runs on Interface animations'
    # `--ui-exit` and shrinks back as it fades; on the closed state only.
    at = css.index(".action-menu.hidden {\n  opacity: 0;\n  scale: 0.96;\n  pointer-events: none;")
    block = css[at : css.index("}", at)]
    assert "opacity var(--ui-exit) var(--ease-out)" in block
    assert "display var(--ui-exit) linear allow-discrete" in block
    menus = (ROOT / "frontend" / "js" / "menus.js").read_text(encoding="utf-8")
    assert "restoreEscapedMenuAfterExit(menu);" in menus[menus.index("function closeActionMenus()") :][:900]
    assert "const exit = menuExitMs(menu);" in menus, "the escape observer must wait for the exit too"
    assert "function menuExitMs(menu)" in menus


def test_a_locked_load_is_not_logged_as_a_failure() -> None:
    """The lock screen is the expected state at boot, not a failed load: the
    browser log used to open with `WARN browser: [notes] could not load:
    Locked`. `loadSurface` still shows the surface's failed state (with Retry)
    but logs only a real failure; `api()` marks the 401 `isLockout`."""
    nav = (ROOT / "frontend" / "js" / "navigation.js").read_text(encoding="utf-8")
    at = nav.index("async function loadSurface(")
    body = nav[at : nav.index("\n}\n", at)]
    assert "if (!error?.isLockout) recordBrowserLog(" in body, (
        "loadSurface must not log a locked read (error.isLockout) as a WARN"
    )
    assert "locked.isLockout = true" in app_js_text()


#: **The second level of tabs is one recipe, `.tabs-line`** (DESIGN.md, "A
#: second-level tab strip"; INBOX 522). The top bar's pills are the frame; a
#: strip under it is text on the page with a 2px accent line under the chosen
#: tab, one height, one gap, no icons.
TABS_LINE_STRIPS = ("notes-subtabs", "library-subtabs", "doc-sidebar-tabs", "wb-format-tabs")


def test_every_second_level_strip_is_a_tabs_line() -> None:
    page = (ROOT / "frontend" / "index.html").read_text(encoding="utf-8")
    for strip in TABS_LINE_STRIPS:
        tag = re.search(rf'<div[^>]*id="{strip}"[^>]*>', page)
        assert tag, strip
        classes = re.search(r'class="([^"]*)"', tag.group(0)).group(1).split()
        assert "tabs-line" in classes, f"#{strip} is not a .tabs-line"
        #: INBOX 682: `#doc-sidebar-tabs` was the one strip that kept `.seg`, and
        #: the flat looks' choice-control fill, edge and square corner (08) drew
        #: its chosen tab as a grey bordered slab. No strip keeps it now.
        assert "seg" not in classes, f"#{strip} is a choice control again (.seg boxes it in a pill)"
        end = page.index("</div>", tag.end())
        assert "<i " not in page[tag.end() : end], (
            f"#{strip} has an icon: second-level tabs are words only (one icon rule)"
        )


def test_a_tabs_line_is_never_boxed_again() -> None:
    """No rule gives a second-level strip a fill, an edge, a corner or a blur
    of its own (the pill-in-a-card look this replaced), and no rule re-sizes
    its tabs: height, padding and the line live in the one `.tabs-line >
    button` rule. The only fill is the glass a sticky strip takes while
    content passes under it (`[data-scrolled]`)."""
    names = {".tabs-line", ".notes-subtabs", ".library-subtabs", ".doc-sidebar-tabs"}
    offenders = []
    for path in CSS:
        for selector, body in _rules(path.read_text(encoding="utf-8")):
            if selector.startswith("@") or "data-scrolled" in selector or "data-glass" in selector:
                continue
            for part in selector.split(","):
                part = " ".join(part.split())
                pieces = re.split(r"\s*[\s>+~]\s*", part)
                last = pieces[-1]
                if "::" in last or ":hover" in last:
                    continue
                if set(re.findall(r"\.[\w-]+", last)) & names:
                    for prop, ok in (
                        ("border-radius", {"0"}),
                        ("backdrop-filter", {"none"}),
                        ("background", {"transparent", "none"}),
                        ("border", {"0", "none"}),
                    ):
                        found = re.search(rf"(?<![\w-]){prop}\s*:\s*([^;]+)", body)
                        if found and " ".join(found.group(1).split()) not in ok:
                            offenders.append(f"{path.name}: {part} sets {prop}")
                elif last == "button" and len(pieces) > 1 and set(re.findall(r"\.[\w-]+", pieces[-2])) & (names - {".tabs-line"}):
                    for prop in ("height", "padding", "background", "border-radius", "font-weight"):
                        if re.search(rf"(?<![\w-]){prop}\s*:", body):
                            offenders.append(f"{path.name}: {part} sets {prop}")
    assert not offenders, "a second-level strip drawn off the .tabs-line recipe:\n  " + "\n  ".join(offenders)


def test_the_top_bar_well_never_grows_to_fill_the_gap() -> None:
    """INBOX 522: `#tab-bar` was `flex: 1 1 auto` between the header's two
    groups, so its inset well spanned the gap with the tabs centred in it (630px
    round 503px of tabs at 1150, and on every boot before the first measure).
    The well hugs its tabs in every mode; centring is auto margins."""
    offenders = []
    for path in CSS:
        for selector, body in _rules(path.read_text(encoding="utf-8")):
            if selector.startswith("@"):
                continue
            for part in selector.split(","):
                if part.split()[-1].split(">")[-1].strip() != "#tab-bar":
                    continue
                if "#phone-tab-dock" in part:  # the phone's bottom dock is full width on purpose
                    continue
                grow = re.search(r"(?<![\w-])flex\s*:\s*([\d.]+)", body)
                if grow and float(grow.group(1)) > 0:
                    offenders.append(f"{path.name}: {' '.join(part.split())} -> flex: {grow.group(1)}")
                if re.search(r"(?<![\w-])flex-grow\s*:\s*[1-9]", body):
                    offenders.append(f"{path.name}: {' '.join(part.split())} -> flex-grow")
    assert not offenders, "the top bar's well grows past its tabs:\n  " + "\n  ".join(offenders)


# ---------------------------------------------------------------------------
# One see-through recipe (UI_MODERNISATION_PLAN 102, DESIGN "Glass & materials"
# rule 1: "two variants, never a third"). The regular variant is
# `--glass-filter`; the clear one (blur only) is `--glass-filter-clear`. A
# surface takes one of the two by token. The literals below are the ones that
# existed when the ratchet was written, with their counts; the counts may only
# shrink, and a value not in this table fails.
# ---------------------------------------------------------------------------
GLASS_TOKENS = {"var(--glass-filter)", "var(--glass-filter-clear)", "none", "none !important"}
LITERAL_BACKDROPS = {
    "blur(var(--glass-blur)) saturate(160%) brightness(1.04)": 21,
    "blur(4px)": 5,  # modal scrims, not panels
    "blur(var(--glass-blur)) saturate(150%)": 4,
    "blur(8px)": 3,
    "blur(var(--glass-blur)) saturate(140%)": 1,
    "blur(6px) saturate(150%) !important": 1,
    "blur(16px)": 1,
}


def _backdrop_values() -> list[str]:
    values = []
    for path in CSS:
        for _selector, body in _rules(path.read_text(encoding="utf-8")):
            values += [
                v.strip()
                for v in re.findall(r"(?<!-webkit-)backdrop-filter:\s*([^;]+);", body)
            ]
    return values


def test_the_clear_glass_variant_is_one_token() -> None:
    tokens = (ROOT / "frontend" / "css" / "00-tokens-shell.css").read_text(encoding="utf-8")
    assert re.search(r"--glass-filter-clear:\s*blur\(var\(--glass-blur\)\);", tokens)
    # Blur only, written out, is the token's job now.
    assert "blur(var(--glass-blur))" not in _backdrop_values()


def test_no_third_glass_variant_and_the_literals_only_shrink() -> None:
    counts: dict[str, int] = {}
    for value in _backdrop_values():
        if value not in GLASS_TOKENS:
            counts[value] = counts.get(value, 0) + 1
    unknown = {v: n for v, n in counts.items() if v not in LITERAL_BACKDROPS}
    grown = {v: n for v, n in counts.items() if n > LITERAL_BACKDROPS.get(v, 0)}
    assert not unknown and not grown, (
        "a backdrop-filter that is neither --glass-filter nor --glass-filter-clear "
        f"(DESIGN.md, Glass & materials, rule 1): {unknown or grown}"
    )


def test_the_chat_sidebar_head_is_one_quiet_row():
    """INBOX 578, the owner: "this section in the chat sidebar looks awkward"
    (a filled 81px "+ New" in the head and a 144px "Recent" sort field alone
    on a row under it). The Notes sidebar's shape: the title, then quiet icon
    controls in the one head row. The sort is the icon-and-caret picker
    (`data-select-icon`), New chat a ghost icon button, so the tab's one
    filled action stays Send; and the row under the head is the list.
    `scratchpad/ui-sweeps/gl1005-chathead.js` measures it."""
    html = (ROOT / "frontend" / "index.html").read_text(encoding="utf-8")
    start = html.index('<aside class="card sidebar-panel" id="chat-sidebar">')
    aside = html[start : html.index("</aside>", start)]
    head = re.sub(r"<!--.*?-->", "", aside[aside.index('class="row space-between sidebar-head"') : aside.index('<p id="conv-empty"')], flags=re.S)
    #: The empty line sits between the head and the list (the owner,
    #: 2026-10-10: "should that no chats text be at the top not the bottom??").
    between = aside[aside.index('<p id="conv-empty"') : aside.index('<ul id="conversation-list">')]
    assert between.rstrip().endswith("</p>") and between.count("<") == 2
    assert 'id="chat-sidebar-sort"' in head and 'data-select-icon="ph-sort-descending"' in head
    new = re.search(r'<button id="chat-new"[^>]*>', head).group(0)
    assert 'class="ghost small icon-only"' in new and 'aria-label="New chat"' in new
    assert head.rstrip().endswith("</div>")
    text = "\n".join(p.read_text(encoding="utf-8") for p in CSS)
    # The old field-under-the-head rule (a 9rem floor) is gone, not overridden.
    bodies = [body for sel, body in _rules(text) if "#chat-sidebar .select-shell" in sel.split(",")]
    assert not any("min-width: 9rem" in body for body in bodies)


def test_no_help_panel_is_hand_wired():
    """Every '?' is the `data-help-for` recipe (DESIGN.md): a button naming its
    `.help-body` panel, wired by `initHelpToggles` and nothing else. The older
    shape was a `.graph-help-panel` opened by an `initHelpToggle(buttonId,
    panelId)` call (or its own click, outside-click and Escape listeners, as
    the Graph's was), which put nine popovers on a second code path and a
    second stylesheet. WORLD_CLASS_PLAN A8 moved them all; this keeps them
    moved."""
    html = (ROOT / "frontend" / "index.html").read_text(encoding="utf-8")
    assert "graph-help-panel" not in re.sub(r'id="graph-help-panel"|data-help-for="graph-help-panel"|aria-controls="graph-help-panel"', "", html), (
        "a `.graph-help-panel` element: use a `.help-body` panel and `data-help-for`"
    )
    for js in JS:
        text = js.read_text(encoding="utf-8")
        assert not re.search(r"\binitHelpToggle\(", text), f"{js.name}: a hand-wired help pair (initHelpToggle)"
        assert not re.search(r"""getElementById\(["'][\w-]*help[\w-]*["']\)\.classList\.(?:remove|toggle)\(["']hidden["']\)""", text), (
            f"{js.name}: a help panel shown by hand"
        )
    for css in CSS:
        assert ".graph-help-panel" not in re.sub(r"/\*.*?\*/", "", css.read_text(encoding="utf-8"), flags=re.S), (
            f"{css.name}: CSS for a hand-wired help panel"
        )
    # Every trigger that points at a panel through aria-controls and carries
    # the '?' class also carries `data-help-for` for the same panel.
    for button in re.finditer(r"<button[^>]*\bgraph-help-toggle\b[^>]*>", html):
        tag = button.group(0)
        assert "data-help-for=" in tag, f"a '?' with no data-help-for: {tag[:120]}"


def test_an_on_off_row_is_one_recipe_whichever_class_it_carries() -> None:
    """DESIGN.md's recipe index, "An on/off setting": a checkbox `.check-row`
    and a `.setting-check` draw the same row (OPEN.md, Settings and help,
    "Toggle rows onto one recipe (no lavender-filled bars)").

    The fill was unified by the consistency pass (08-consistency.css: a checked
    checkbox row has no fill, only a hairline between rows), but the gap from
    the switch to its label was not: measured in Settings at 1440,
    `togglerows.js`, 15 `.check-row` switch rows at 6.4px against 8
    `.setting-check` rows at 9.6px, two shapes of one control a scroll apart.
    Both now take `--space-4`, and the switch comes first in the markup as it
    does on screen, so a screen reader meets it in the order the eye does.
    """
    text = "\n".join(p.read_text(encoding="utf-8") for p in CSS)
    assert re.search(
        r'\n\.check-row \{[^}]*\bgap:\s*var\(--space-4\)', text
    ), "a .check-row must take the same --space-4 gap as .setting-check"
    block = text[text.index("label.setting-check,\n.setting-check {"):]
    block = block[: block.index("}")]
    assert "column-gap: var(--space-4)" in block, "the .setting-check gap is --space-4"

    html = (ROOT / "frontend" / "index.html").read_text(encoding="utf-8")
    for match in re.finditer(r'<label class="setting-check[^"]*"[^>]*>(.*?)</label>', html, re.S):
        inner = match.group(1)
        if 'type="checkbox"' not in inner:
            continue
        assert inner.strip().startswith("<input"), (
            "a .setting-check row leads with its switch: " + inner.strip()[:80]
        )


def test_the_ai_skills_dock_holds_one_row() -> None:
    """INBOX 599, the owner, with the AI skills dock in two rows: "can you
    clean up and redesign this top docks??". Measured with `settingsheads.js`:
    90px and two rows at 1100 and 820 before, one row (50px) at 1440, 1280 and
    1100 after. Three parts, any of which a later session could undo:

    1. the sort is an icon-and-caret picker (`data-select-icon`) and an icon
       picker in a dock is not held to a worded select's 9rem floor;
    2. the kind filter is one worded select (INBOX 665: it was a pill well
       of three whose words left the row under 58rem), its counts on its rows;
    3. the planned two-line break (INBOX 450) waits for a dock under 700px.
    """
    html = (ROOT / "frontend" / "index.html").read_text(encoding="utf-8")
    sort = re.search(r'<select id="skills-sort"[^>]*>', html).group(0)
    assert 'data-select-icon="ph-' in sort
    kind = html[html.index('<select id="skills-kind"'):]
    kind = kind[: kind.index("</select>")]
    assert kind.count("<option ") == 3 and "toolbar-word" not in kind
    css = "\n".join(p.read_text(encoding="utf-8") for p in CSS)
    assert ".dock:has(.toolbar-word) {\n  container: dock / inline-size;" in css
    assert ".dock .select-shell:has(.select-opener-icon) {\n  min-width: 0;" in css
    assert "@container dock (max-width: 700px)" in css
    assert "skills-page" not in css


def test_every_settings_pane_opens_on_its_dock() -> None:
    """DESIGN.md, "A Settings pane's head" (INBOX 599, the owner: "keep doing
    it for the settings pages ... make sure all the design styles across all
    pages and popups are consistent"). Measured with `settingsheads.js` before:
    21 panes opened on a bare 18.4px title row with the '?' at the far right
    and the section index as a second strip under it, Logs on a `.dock` with a
    12px title. After: every pane's head is a `.dock` (title 16px 600, the index
    inside it, the '?' last), one row and one control height at 1440.

    A pane written in the markup opens on `.dock.settings-pane-title`; a pane
    without one gets the same shape from `ensureSettingsPaneTitle`, and the
    dock is what sticks. The index went from inside the dock to the sidebar's
    second level (INBOX 622, `settingsIndexBuild`).
    """
    html = (ROOT / "frontend" / "index.html").read_text(encoding="utf-8")
    html = re.sub(r"<!--.*?-->", "", html, flags=re.S)
    for match in re.finditer(r'<section class="settings-section[^"]*" id="(settings-[a-z]+)">\s*<([a-z]+)([^>]*)>', html):
        pane, tag, attrs = match.groups()
        assert "help-head" not in attrs, f"{pane} opens on a bare help-head row: make it the pane's dock"
        if "dock" in attrs:
            assert tag == "div" and re.search(r'class="dock\b', attrs), pane
    settings = with_pieces("settings.js")
    body = _function_body(settings, "ensureSettingsPaneTitle")
    assert '"dock settings-pane-title"' in body and '"dock-identity"' in body
    find = (ROOT / "frontend" / "js" / "settings-find.js").read_text(encoding="utf-8")
    # The index is the sidebar's second level now (INBOX 622), not a strip in
    # this dock.
    assert '$("settings-nav")' in _function_body(find, "settingsIndexBuild")
    title = _css_block("#settings-modal .settings-section > .dock h3")
    # 600 is `.card h3`'s own weight; the size and the ink are this rule's.
    assert "var(--text-body)" in title and "var(--ink)" in title


def test_the_note_edit_form_is_one_composition() -> None:
    """INBOX 606, then 616, the owner: "its better but still needs a more
    modern and professional ui/ux redesign (the note edit form)", "the attach
    a link button doesnt do anything", "there is no padding around the tag
    entries", the folded strip "looks really awkward" and the category
    dropdown is "completely out of place". Measured with `noteedit616.js` at
    1440 and 390, light and dark. Now: one `.note-composer` surface holding
    the title, the properties line (the category chip, then the tag chips and
    the add-tag input, no well and no '#' icon), the strip and the text; under
    it the files and a slim foot: Attach a link and the word count at the
    left, Cancel then the one filled Save at the right. Related is one
    disclosure line, closed."""
    form = _function_body(app_js_text(), "renderEditForm")
    assert 'surface.className = "note-composer note-edit-surface"' in form
    assert 'tagField.className = "tag-field note-edit-tags"' in form
    assert "ph-hash" not in form and "search-field" not in form
    assert 'chip("", "category note-edit-category"' in form
    assert "meta.append(categoryChip, tagField)" in form
    assert "surface.append(titleInput, meta, toolbarEl, textarea)" in form
    assert "li.append(surface, chipsHost, foot)" in form
    assert "foot.append(count, row)" in form
    assert form.index('smallButton("Cancel"') < form.index("    saveButton\n  );")
    panels = (ROOT / "frontend" / "js" / "note-edit-panels.js").read_text(encoding="utf-8")
    assert panels.count('li.insertBefore(panel, li.querySelector(":scope > .note-edit-foot"))') == 2
    assert "foot.prepend(attachButton)" in panels
    rows = (ROOT / "frontend" / "js" / "note-panels.js").read_text(encoding="utf-8")
    #: INBOX 709: the + is inside the note's chip, the chip the one control.
    assert 'chip("", "link entry-related-chip", linkIt)' in rows
    assert 'relChip.setAttribute("aria-label", `Link to ${name}`)' in rows
    assert 'add.className = "ph ph-plus entry-related-add"' in rows
    assert 'smallButton("ph:plus"' not in rows


def test_the_note_edit_forms_attach_a_link_opens_the_picker() -> None:
    """INBOX 616, the owner: "the note edit form attach a link button doesnt
    do anything". It appended a bare select to the References panel, which is
    hidden while the note has none, so the first press drew nothing visible;
    a pick re-ran the panel and added a second Attach button. Now the press
    opens the app's one-thing picker on its Bookmarks source and a pick
    repaints the one panel (`noteeditflow.js`: refs 1, shown 1, one button)."""
    panels = (ROOT / "frontend" / "js" / "note-edit-panels.js").read_text(encoding="utf-8")
    picker = _function_body(panels + "\nfunction ", "openBookmarkAttachPicker")
    assert 'pickLibraryItemDialog("Attach a link", { sources: ["link"] })' in picker
    assert 'createElement("select")' not in picker
    assert "openBookmarkAttachPicker(entry, refresh)" in panels
    related = panels[panels.index("function renderRelatedWhileEditing("):panels.index("function renderNoteBookmarksWhileEditing(")]
    assert "note-edit-related-toggle" in related and "list.hidden = true" in related


def test_a_notes_strip_is_one_icon_row_that_never_folds() -> None:
    """INBOX 616: the folded strip was an empty band with three icons and a
    caret, and B, I, S were typed letters beside Phosphor icons. The note
    strip (Capture's and the edit form's clone) is icons only, at every width,
    and `applyDocToolbarCollapsed` leaves it out of the fold."""
    html = (ROOT / "frontend" / "index.html").read_text(encoding="utf-8")
    strip = html[html.index('id="note-toolbar"'):]
    strip = strip[: strip.index("</div>")]
    assert "<strong>B</strong>" not in strip and "<em>I</em>" not in strip
    for icon in ("ph-text-b", "ph-text-italic", "ph-text-strikethrough", "ph-code-simple"):
        assert icon in strip
    docs = _function_body((ROOT / "frontend" / "js" / "documents.js").read_text(encoding="utf-8"), "applyDocToolbarCollapsed")
    assert 'collapsed && !bar.classList.contains("note-toolbar")' in docs
    css = (ROOT / "frontend" / "css" / "05-sidebars-themes.css").read_text(encoding="utf-8")
    rule = css.index(".note-toolbar .toolbar-word {")
    assert "@media" not in css[css.rfind("}", 0, rule) : rule]


def test_a_dialog_foot_is_one_height_with_its_filled_action_last() -> None:
    """DESIGN.md, "A popup window or panel": the foot (INBOX 599, the owner:
    "make sure all the design styles across all pages and popups are
    consistent"). The popup census (`popupinv.js`, foot fields) found, at 1440:
    eight `.space-dialog-actions` feet with two button heights (40 and 38, the
    base button size) beside the confirm alert's and the pickers' 32, and the
    Extract and Improve writing feet with the filled action first, at the left.
    Now every dialog foot is `row right space-dialog-actions`: `small` buttons,
    ghosts first, the one filled action last."""
    html = (ROOT / "frontend" / "index.html").read_text(encoding="utf-8")
    html = re.sub(r"<!--.*?-->", "", html, flags=re.S)
    feet = re.findall(r'<div class="row right space-dialog-actions">(.*?)</div>', html, re.S)
    assert len(feet) >= 12
    for foot in feet:
        buttons = re.findall(r"<button[^>]*>", foot)
        for button in buttons:
            assert re.search(r'class="[^"]*\bsmall\b', button), f"a dialog foot button is not small: {button}"
        kinds = ["ghost" if re.search(r'class="[^"]*\bghost\b', b) else "filled" for b in buttons]
        assert kinds.count("filled") <= 1 and (not kinds.count("filled") or kinds[-1] == "filled"), kinds
    for name in ("note-properties.js", "quick-access.js"):
        code = (ROOT / "frontend" / "js" / name).read_text(encoding="utf-8")
        assert '.className = "ghost small";' in code and '.className = "accent small";' in code, name


#: `p.muted` empty lines not yet on the recipe. Empty since op5-1005 moved the
#: last nine (Documents', Chat's, Ask's, the graph's and the whiteboard's).
EMPTY_LINES_NOT_YET: set[str] = set()


def test_an_empty_line_in_a_small_panel_is_the_recipe():
    """DESIGN.md's recipe index, "An empty line in a small panel" (OPEN.md,
    visual-c; op4-1005). `.empty-state` is a centred block with 2rem of
    padding for a surface whose content area is empty; a short list in a
    glance panel or a Settings section says so in one `.empty-line` instead.
    Measured before: fourteen such lines in four type sizes and five
    margins. Every `<p id="...-empty">` is one of the two recipes, or a
    named one still waiting for its owner."""
    html = re.sub(r"<!--.*?-->", "", (ROOT / "frontend" / "index.html").read_text(encoding="utf-8"), flags=re.S)
    off = set()
    for tag in re.findall(r"<p\b[^>]*>", html):
        ident = re.search(r'\bid="([a-z0-9-]+-empty)"', tag)
        if not ident:
            continue
        found = re.search(r'\bclass="([^"]*)"', tag)
        classes = found.group(1).split() if found else []
        if "empty-line" not in classes and "empty-state" not in classes:
            off.add(ident.group(1))
    assert off <= EMPTY_LINES_NOT_YET, f"an empty line off the recipe: {sorted(off - EMPTY_LINES_NOT_YET)}"
    css = "\n".join((ROOT / "frontend" / "css" / name).read_text(encoding="utf-8") for name in ("07-whiteboard-misc.css", "library-lazy.css"))
    rule = next(body for sel, body in _rules(css) if sel.strip() == ".empty-line")
    for part in ("var(--muted)", "var(--text-md)", "text-align: start", "margin: var(--space-3) 0"):
        assert part in rule, f".empty-line lost {part}"


def test_a_label_on_a_settings_list_row_takes_the_ink():
    """`contrast.js` (op4-1005): "Built-in" on a Settings, Skills row read
    4.27:1 in light, `--muted` on three stacked tints (the fold, the row, the
    label). A label there takes `--ink`, as the ok label already does."""
    css = (ROOT / "frontend" / "css" / "08-consistency.css").read_text(encoding="utf-8")
    rule = next(
        body for sel, body in _rules(css)
        if ".entry-list > li > :is(.skill-row, .persona-row) .chip.item-label" in sel
    )
    assert "color: var(--ink)" in rule


def test_the_installed_models_are_model_cards():
    """UI_MODERNISATION_PLAN 444, decision 10 (op4-1005): "the Installed models
    list is the old row list". It is the suggested downloads' own card now
    (`buildModelCard` as a custom model, in the lazy settings-models.js), in
    a `.model-grid`, with no "Installed" badge in a list where every card is
    installed; the boot copy and its fixed-column CSS are gone, and the
    status poll calls it behind a `typeof` guard, as it does the suggested
    list."""
    lazy = (ROOT / "frontend" / "js" / "settings-models.js").read_text(encoding="utf-8")
    body = _function_body(lazy, "renderInstalledModels")
    assert "buildModelCard(model, state)" in body and 'listed: "installed"' in body
    assert "list.dataset.sig === sig" in body, "a poll must not redraw the cards under an open menu"
    assert 'state.installed && !model.listed' in lazy
    boot = with_pieces("ai-tools.js")
    assert "function renderInstalledModels" not in boot
    status = with_pieces("status.js")
    #: Drawn under the one check that the lazy settingsUi file has loaded.
    assert 'if (typeof renderSuggested === "function") {\n      renderInstalledModels(status);' in status
    html = (ROOT / "frontend" / "index.html").read_text(encoding="utf-8")
    assert '<div id="installed-list" class="model-grid"></div>' in html
    css = (ROOT / "frontend" / "css" / "01-forms-settings.css").read_text(encoding="utf-8")
    assert "#installed-list li" not in css


def test_the_autonomous_override_names_what_it_falls_back_to():
    """444 decision 10 counted "a background-job model chosen in Models and in
    Background tasks" as one setting in two places. They are two (the utility
    model, and the autonomous pass's own override), and the override's
    default now says which model it means, in the per-feature pickers' words
    (INBOX 430): "Same as utility model (currently llama3.2)" (op4-1005)."""
    js = with_pieces("ai-tools.js")
    body = _function_body(js, "renderAutonomousModelPicker")
    assert "Same as utility model (currently ${fallback})" in body
    assert "status.utility_model || status.chat_model" in body


def test_the_ocr_toolbars_segment_track_grows_round_its_touch_buttons() -> None:
    """OPEN.md, "the OCR workspace head": `.ocr-head .seg` is `height:
    var(--control-h)`, and below 600 the segments lift to `--target-min`, so
    the 32px page-size track sat 12px short of its 44px buttons and the
    buttons 6px below their neighbours (`wbtopbar.js` with `ONLY=ocr`). The
    track grows round them on the same band."""
    css = (ROOT / "frontend" / "css" / "10-responsive.css").read_text(encoding="utf-8")
    at = css.index("  .sheet-card-page .ocr-toolbar .seg-compact {\n")
    block = css[at : css.index("}", at)]
    assert "height: auto;" in block and "min-height: var(--target-min);" in block


#: **A control inside a rounded container takes the container's tokens**
#: (DESIGN.md, "Controls inside a rounded container"; INBOX 682 and 683, the
#: owner: "the square active goes out of the circular pill"). Each key is a
#: selector as written; each value is the one corner every rule that rounds
#: it may use. The table bar's "Copy | ... | X" drew its buttons with
#: `--radius-inner`, a card surface's concentric corner that is 0 below a 12px
#: corner setting, so a rounded square sat in a capsule.
CONTROLS_IN_ROUNDED_CONTAINERS = {
    ".code-actions > .code-copy": "var(--radius-in-pill)",
    ".code-actions > .menu-wrap > button": "var(--radius-in-pill)",
    ".whiteboard-floating-panel.whiteboard-floating-panel.bottom-right > button": "var(--radius-in-pill)",
    ".timeline-days .timeline-day.ghost.small": "var(--radius-in-choice)",
    ".graph-zoom .graph-zoom-btn": "var(--radius-in-md)",
    ".tabs-line > button": "var(--radius-md)",
}


def test_a_control_in_a_rounded_container_takes_the_container_tokens() -> None:
    found: dict[str, list[str]] = {key: [] for key in CONTROLS_IN_ROUNDED_CONTAINERS}
    for path in CSS:
        for selector, body in _rules(path.read_text(encoding="utf-8")):
            if selector.startswith("@"):
                continue
            radius = re.search(r"(?<![\w-])border-radius\s*:\s*([^;]+)", body)
            if not radius:
                continue
            value = " ".join(radius.group(1).replace("!important", "").split())
            for part in selector.split(","):
                part = " ".join(part.split())
                if part in found:
                    found[part].append(value)
    offenders = []
    for key, want in CONTROLS_IN_ROUNDED_CONTAINERS.items():
        if not found[key]:
            offenders.append(f"{key}: no rule rounds it (expected {want})")
        offenders += [f"{key}: {value} (expected {want})" for value in found[key] if value != want]
    assert not offenders, "a control inside a rounded container off the table:\n  " + "\n  ".join(offenders)


def test_the_contained_corner_tokens_are_defined_from_the_table() -> None:
    tokens = (ROOT / "frontend" / "css" / "00-tokens-shell.css").read_text(encoding="utf-8")
    for name, value in (
        ("--radius-in-pill", "var(--radius-pill)"),
        ("--radius-in-choice", "max(var(--radius-md), calc(var(--radius-choice) - var(--space-1)))"),
        ("--radius-in-md", "max(var(--radius-sm), calc(var(--radius-md) - var(--space-1)))"),
    ):
        got = re.search(rf"{re.escape(name)}\s*:\s*([^;]+);", tokens)
        assert got and " ".join(got.group(1).split()) == value, f"{name} is not {value}"
    design = (ROOT / "docs" / "DESIGN.md").read_text(encoding="utf-8")
    assert "### Controls inside a rounded container" in design


def test_no_second_level_strip_is_also_a_choice_control() -> None:
    """The class that gave the Documents sidebar's tabs a grey, edged, square
    slab in the flat looks (INBOX 682): `.seg` and `.tabs-line` are two
    recipes, never one element's two classes."""
    page = (ROOT / "frontend" / "index.html").read_text(encoding="utf-8")
    offenders = [
        tag
        for tag in re.findall(r"<[a-z]+\s[^>]*>", page)
        if (classes := re.search(r'class="([^"]*)"', tag))
        and {"seg", "tabs-line"} <= set(classes.group(1).split())
    ]
    assert not offenders, f"an element is both .seg and .tabs-line: {offenders}"


# --- One sidebar row recipe for every rail (INBOX 702) ----------------------------
#: A left rail's rows. Hover is the neutral `--row-hover-bg`, the current row
#: may carry the accent (`--accent-soft`), and the row's ⋯ is a plain ghost
#: icon that fills only under its own pointer. The owner, with two screenshots:
#: "the hover and button styles on the notes sidebar is different from the
#: others. is that intentional??" (a blue-tinted hover on Notes, grey on Chats).
RAIL_ROWS = {
    "#sidebar li": ("#sidebar li.active",),
    "#category-list li": (),
    "#conversation-list li": ("#conversation-list li.active-conv",),
    ".modal-nav button": (".modal-nav button.active",),
}
#: Every `.sidebar-panel` is a rail with rows above, or is named here with why not.
RAIL_PANELS = {
    "sidebar": "Notes categories",
    "chat-sidebar": "Chats",
    "doc-sidebar": "Documents (cards with a resting fill; hover is the next neutral tier)",
    "skills-sidebar": "Skill logs: a log, not a list of rows with a menu",
}
#: Wrappers of a row's ⋯ in a rail; the recipe rule in 08-consistency.css
#: names each.
RAIL_MENUS = ("#category-list li .category-actions", "#conversation-list li .entry-actions", ".doc-item .doc-item-menu")


def _rail_background(body: str) -> str | None:
    found = re.search(r"(?:^|;)\s*background(?:-color)?\s*:\s*([^;]+)", body)
    return " ".join(found.group(1).split()) if found else None


def test_a_rail_row_hovers_neutral_and_the_current_row_is_the_only_accent() -> None:
    css = "\n".join(path.read_text(encoding="utf-8") for path in CSS)
    seen_hover: set[str] = set()
    seen_current: set[str] = set()
    offenders = []
    for selector, body in _rules(css):
        fill = _rail_background(body)
        if fill is None:
            continue
        for part in (p.strip() for p in selector.split(",")):
            for row, currents in RAIL_ROWS.items():
                if part == f"{row}:hover":
                    seen_hover.add(row)
                    if fill != "var(--row-hover-bg)":
                        offenders.append(f"{part} fills {fill}: a rail row hovers var(--row-hover-bg)")
                for current in currents:
                    if part in (current, f"{current}:hover"):
                        seen_current.add(current)
                        if fill != "var(--accent-soft)":
                            offenders.append(f"{part} fills {fill}: the current row is var(--accent-soft)")
    assert not offenders, "\n".join(offenders)
    assert seen_hover >= {"#sidebar li", "#conversation-list li", ".modal-nav button"}, seen_hover
    assert seen_current >= {"#sidebar li.active", "#conversation-list li.active-conv", ".modal-nav button.active"}, seen_current


def test_every_rail_is_a_known_rail() -> None:
    page = (ROOT / "frontend" / "index.html").read_text(encoding="utf-8")
    panels = set(re.findall(r'<aside[^>]*class="[^"]*\bsidebar-panel\b[^"]*"[^>]*id="([\w-]+)"', page))
    panels |= set(re.findall(r'<aside[^>]*id="([\w-]+)"[^>]*class="[^"]*\bsidebar-panel\b', page))
    assert panels == set(RAIL_PANELS), (
        f"sidebar panels {sorted(panels)}; known {sorted(RAIL_PANELS)}: a new rail takes the row recipe "
        "(DESIGN.md, 'A sidebar row') and joins RAIL_ROWS and RAIL_PANELS"
    )


def test_a_rail_rows_menu_is_a_plain_ghost_icon_that_fills_on_its_own_hover() -> None:
    css = (ROOT / "frontend" / "css" / "08-consistency.css").read_text(encoding="utf-8")
    plain = [body for selector, body in _rules(css) if all(menu in selector for menu in RAIL_MENUS) and selector.endswith("button")]
    hover = [body for selector, body in _rules(css) if all(menu in selector for menu in RAIL_MENUS) and re.search(r"button:hover(,|$)", selector)]
    assert plain and hover, "the rail ⋯ recipe rule (08-consistency.css) is missing or no longer names every rail's menu"
    assert _rail_background(plain[0]) == "transparent", "a rail ⋯ has no fill at rest or while its row is hovered"
    assert _rail_background(hover[0]) == "var(--ghost-btn-bg)", "a rail ⋯ fills only under its own pointer"
    assert "border-radius: var(--radius-md)" in plain[0], "the fill stays inside the row's own radius"


#: **Every `.seg` pill inside a popup, by name** (INBOX 715, the owner: "i
#: dont like pills like that in popups"). DESIGN.md's row "A popup that
#: chooses a kind" is a `.tabs-line` tab strip under the head; the New board
#: dialog's Board | Mind map and the icon picker's Emoji | Icons were pills and
#: are strips now. What is left is either a setting's value or a view of one
#: pane (DESIGN.md's `.seg` row: two or three short choices), or a kind switch
#: placed in `docs/roadmap/archive/agent-remaining/board715-1006.md`. The lists only
#: shrink: a new pill in a popup fails here.
SEG_IN_POPUPS = {
    "doc-history-filter": "Earlier versions: All or AI edits, a filter of one list",
    "ocr-zoom": "the OCR workspace's zoom",
    "ocr-view": "the OCR workspace's view of one page",
    "theme-seg": "Settings: a value",
    "fontsize-seg": "Settings: a value",
    "border-style-seg": "Settings: a value",
    "privacy-range": "Settings: a value",
    "log-view-toggle": "Settings: a view of one log",
}
SEG_BUILT_IN_SCRIPT = {
    ("app.js", "seg seg-compact confirm-seg"): "promptDialog's `segment`, a value",
    ("documents.js", "seg"): "the print setup's values",
    ("skills.js", "seg seg-compact chat-skill-pace"): "a skill's pace, a value",
    ("whiteboard.js", "seg seg-compact wb-export-seg"): "Export this board: the format, a value",
    ("timeline-calendar.js", "seg seg-compact timeline-cal-span"): "not a popup: the calendar head's view mode (Month, Week, Day)",
    ("dashboard.js", "seg focus-presets-seg"): "not a popup: the focus timer's length, a value (UI_MODERNISATION V8)",
}


class _PopupPills(HTMLParser):
    """Every `.seg` inside a dialog, a `[popover]` or a `role="dialog"`, by id."""

    VOID = {"input", "img", "br", "hr", "meta", "link", "source", "area", "col", "embed", "param", "track", "wbr", "base"}

    def __init__(self) -> None:
        super().__init__()
        self.stack: list[tuple[str, bool]] = []
        self.found: list[str] = []

    def handle_starttag(self, tag, attrs):
        a = dict(attrs)
        popup = tag == "dialog" or "popover" in a or a.get("role") == "dialog"
        if "seg" in (a.get("class") or "").split() and any(p for _, p in self.stack):
            self.found.append(a.get("id") or "?")
        if tag not in self.VOID:
            self.stack.append((tag, popup))

    def handle_endtag(self, tag):
        for i in range(len(self.stack) - 1, -1, -1):
            if self.stack[i][0] == tag:
                del self.stack[i:]
                break


def test_a_popup_chooses_a_kind_with_a_tab_strip() -> None:
    """INBOX 715: a popup's kind switch is a `.tabs-line.popup-kinds` with
    `role="tablist"`, its tabs `role="tab"` with `aria-selected`, never a
    `.seg` pill; no new pill appears in a popup, in the markup or in script."""
    html = (ROOT / "frontend" / "index.html").read_text(encoding="utf-8")
    pills = _PopupPills()
    pills.feed(re.sub(r"<!--.*?-->", "", html, flags=re.S))
    assert set(pills.found) <= set(SEG_IN_POPUPS), sorted(set(pills.found) - set(SEG_IN_POPUPS))
    built = set()
    for path in JS:
        for classes in re.findall(r'\.className = "(seg(?: [^"]*)?)";', path.read_text(encoding="utf-8")):
            built.add((path.name, classes))
    assert built <= set(SEG_BUILT_IN_SCRIPT), sorted(built - set(SEG_BUILT_IN_SCRIPT))
    # The two the owner named are tab strips.
    assert re.search(r'class="tabs-line popup-kinds[^"]*" id="wb-template-kind" role="tablist"', html)
    picker = (ROOT / "frontend" / "js" / "icon-picker.js").read_text(encoding="utf-8")
    assert 'tabs.className = "tabs-line popup-kinds icon-picker-modes"' in picker
    assert 'b.setAttribute("role", "tab")' in picker and '"aria-selected"' in picker
    guide = (ROOT / "frontend" / "js" / "help-chat.js").read_text(encoding="utf-8")
    assert 'seg.className = "tabs-line popup-kinds help-chat-views"' in guide


#: **A Rows line starts with its kind icon** (INBOX 722, the owner: "theres a
#: wierd gap at the start of the library all tab lines view"). With one picture
#: in the list, every row without one reserved a 3rem `::before` slot so the
#: thumbnails would line up, which pushed every other row's icon 63px in
#: (measured: icon at x 75 against a 14px row padding). The thumbnail now sits
#: after the title and the preview, in a slot only the row that has one pays
#: for, so the icon is at the row's own padding on every row.
def test_a_library_row_reserves_no_leading_slot_for_a_thumbnail() -> None:
    css = "\n".join(path.read_text(encoding="utf-8") for path in CSS)
    for selector, body in _rules(css):
        if ".library-list" in selector and "::before" in selector and "content" in body:
            raise AssertionError(f"a Rows line reserves space before its icon: {selector}")
    thumb = [
        body for selector, body in _rules((ROOT / "frontend/css/00-tokens-shell.css").read_text(encoding="utf-8"))
        if selector == ".library-list .library-card-thumb"
    ]
    assert thumb, "the Rows thumbnail rule is missing"
    order = re.search(r"order\s*:\s*(-?\d+)", thumb[0])
    assert order and int(order.group(1)) > 0, "a Rows thumbnail follows the title; it never leads the row"
    assert "has-thumbs" not in (ROOT / "frontend/js/library.js").read_text(encoding="utf-8")


#: **The hover tick is a control with its icon, not an empty box** (INBOX 722,
#: the owner: an empty square beside the hovered row's ⋯). It was neither a
#: leftover nor a pin: it is the Library's selection tick (`.library-card-tick`,
#: wired to the bulk bar, labelled "Select <title>"), revealed on hover. Drawn
#: unchecked it was a 28px blank square next to the 28px ⋯, which reads as a
#: control that failed to load. An unchecked tick now shows a faint check, so it
#: says what it is before it is pressed, and it carries a title.
def test_the_library_hover_tick_shows_its_check_and_names_itself() -> None:
    css = (ROOT / "frontend" / "css" / "library-lazy.css").read_text(encoding="utf-8")
    faint = [
        body for selector, body in _rules(css)
        if ".library-card-tick:not(:checked)::after" in selector
    ]
    assert faint, "an unchecked Library tick draws a faint check (library-lazy.css)"
    assert 'content: ""' in faint[0] and "border-width: 0 2px 2px 0" in faint[0]
    assert re.search(r"border(?:-color)?\s*:[^;]*var\(--(?:muted|faint)", faint[0]) or "border-color: var(--muted)" in faint[0]
    script = (ROOT / "frontend" / "js" / "library.js").read_text(encoding="utf-8")
    assert re.search(r'tick\.className = "library-card-tick";\s*tick\.title = "Select"', script), "the tick names itself on hover"


#: **One ⋯ (INBOX 722, the owner: "meatball buttons have a visible outline, is
#: that consistent with the rest of the app?? i dont think it is").** The app's
#: rule, DESIGN.md's "A ⋯ or ⋮ that opens a menu" row: a plain ghost icon, no fill, edge
#: or shadow at rest, `--ghost-btn-bg` only under its own pointer or while its
#: menu is open, drawn at `--radius-md`. `kebabMenu` gives every opener the one
#: class, `kebab-opener`, and it is styled once in 08-consistency.css; a surface
#: that wants its ⋯ dressed differently does not get to say so.
def test_the_kebab_opener_is_one_shared_ghost_icon_styled_once() -> None:
    script = with_pieces("sheets-selects.js")
    assert 'opener.classList.add("icon-only", "kebab-opener")' in script, "kebabMenu's opener carries the shared class"

    shared = (ROOT / "frontend" / "css" / "08-consistency.css").read_text(encoding="utf-8")
    named = [(selector, body) for selector, body in _rules(shared) if ".kebab-opener" in selector]
    plain = [body for selector, body in named if ":hover" not in selector]
    at_rest = [body for selector, body in named if ":not(:hover" in selector]
    hover = [body for selector, body in named if ":not(:hover" not in selector and ":is(:hover" in selector]
    assert plain and at_rest and hover, "the shared kebab opener rule (08-consistency.css) is missing"
    assert all(_rail_background(body) == "transparent" for body in at_rest), "a ⋯ has no fill at rest"
    rest = "\n".join(plain)
    assert re.search(r"border(?:-color)?\s*:\s*transparent", rest), "a ⋯ has no edge at rest"
    assert re.search(r"box-shadow\s*:\s*none", rest), "a ⋯ has no shadow at rest"
    assert "border-radius: var(--radius-md)" in rest
    assert any(_rail_background(body) == "var(--ghost-btn-bg)" for body in hover), "a ⋯ fills only under its own pointer"

    # No other rule in the app dresses the opener: a selector that names
    # `.kebab-opener`, or the library's ⋯ chip that this replaced, may not set
    # a resting fill, edge or shadow anywhere else.
    for path in CSS:
        if path.name == "08-consistency.css":
            continue
        for selector, body in _rules(path.read_text(encoding="utf-8")):
            names_opener = ".kebab-opener" in selector or (
                'button[aria-haspopup="menu"]' in selector and "library-card-menu" in selector
            )
            if names_opener and re.search(r"(?:^|;)\s*(?:background(?:-color)?|border(?:-color)?|box-shadow)\s*:", body):
                raise AssertionError(f"{path.name}: {selector} dresses the ⋯ opener; styled once in 08-consistency.css")


#: **A rail row's ⋮ overlays the row; it never reserves a column** (INBOX 722,
#: the owner: "there's quite a big gap on the right side of the chat sidebar
#: chat items"). Measured at rest before: a chat's title 34px and a Documents
#: title 33px short of the row's padding edge (the hidden ⋮ still held a flex
#: item, and a 2rem `padding-right`, open); the Notes categories rail was
#: already right (its `.category-actions` is absolute and the count is the last
#: thing in the row). Now every rail's menu is absolutely placed, the row keeps
#: only its own padding, and the words fade under the ⋮ while it shows.
def test_a_rail_rows_title_takes_the_full_width_and_its_menu_overlays_it() -> None:
    css = "\n".join(path.read_text(encoding="utf-8") for path in CSS)

    def declared(selector: str, prop: str) -> list[str]:
        return [
            re.search(rf"(?:^|;)\s*{prop}\s*:\s*([^;]+)", body).group(1).strip()
            for sel, body in _rules(css)
            if selector in [part.strip() for part in sel.split(",")] and re.search(rf"(?:^|;)\s*{prop}\s*:", body)
        ]

    assert "absolute" in declared("#conversation-list li .entry-actions", "position"), "a chat row's ⋮ overlays the row"
    assert "absolute" in declared("#category-list li .category-actions", "position") or "absolute" in declared(".category-actions", "position")
    assert "absolute" in declared(".menu-wrap.doc-item-menu", "position"), "a Documents row's ⋮ overlays the row"
    # No right padding held back for the ⋮: the row keeps its own 0.6rem, the
    # old `var(--space-9)` (2rem) reservation is gone.
    paddings = declared(".doc-item-button", "padding")
    assert paddings and all("space-9" not in value for value in paddings), "the Documents row reserves a column for its ⋮"
    # The words fade under the ⋮ rather than stopping short of it.
    fades = [body for sel, body in _rules(css) if "#conversation-list li" in sel and "mask-image" in body]
    assert fades, "the end of a chat's title fades under its ⋮"
    assert any(":hover" in sel and "doc-item" in sel for sel, body in _rules(css) if "mask-image" in body)


def test_a_note_cards_details_line_ends_the_card_and_keeps_the_space_before_edited() -> None:
    """INBOX 760, the owner: "you still havent fixed the positioning of the
    dates and times". The wiki-link row, the why line and the review answers
    are built after `.entry-meta`, so a card with links showed its time 48px
    (one row) to 113px (three, at 390) above the card's foot against 7.4px on
    a card with none (`scratchpad/ui-sweeps/carddate.js`). Card view is a
    column flex whose details line has the last `order`, and the "· edited"
    suffix keeps its space as a no-break space, because a plain leading space
    collapses inside the date's inline flex box."""
    css = (ROOT / "frontend" / "css" / "08-consistency.css").read_text(encoding="utf-8")
    card = "#entry-list:not(.is-rows) > li"
    rules = list(_rules(css))

    def body(selector: str) -> str:
        return "\n".join(b for s, b in rules if s == selector)

    assert re.search(r"display\s*:\s*flex", body(card)) and re.search(r"flex-direction\s*:\s*column", body(card))
    meta = body("#entry-list > li:not(.list-window-sentinel) > .entry-meta.entry-meta")
    assert re.search(r"order\s*:\s*1\b", meta), "the details line is last in card view"
    parts = body(f"{card}:not(.list-window-sentinel) > :not(.entry-meta, .entry-title)")
    assert re.search(r"margin-bottom\s*:\s*0\b", parts), "flex margins do not collapse, so the parts drop theirs"
    assert "!important" not in "\n".join([body(card), meta, parts])
    # The row view is a grid placed by explicit cell; the card rule must not reach it.
    assert ":not(.is-rows)" in card
    # The suffix keeps its space as a no-break space in its text (a plain
    # leading space collapses inside the date's inline flex box).
    assert 'textContent: "\\u00a0· edited"' in (ROOT / "frontend" / "js" / "note-cards.js").read_text(encoding="utf-8")
    # The phone rule that hides the suffix is still there.
    assert re.search(r"display\s*:\s*none", body(".entry-meta.note-meta .entry-edited"))
def test_the_no_model_notice_is_one_row_on_the_notice_recipe() -> None:
    """INBOX 767 (the owner, 2026-10-10): the Chat tab's no-model line was "ugly
    and on multiple rows": a long sentence, then the button and the close on a
    second row, in a box of its own.

    So it is the notice recipe now, in the recipe's order: the plug icon as the
    first child (built by `setLabel` on the container, so `.notice > .ph`
    styles it), one short sentence, the button, the close last. The long
    explanation moved to the button's `title`.
    """
    status = app_js_text()
    start = status.index("function renderAiOfflineNotice(")
    body = status[start : status.index("\n}\n", start)]
    order = [
        body.index('setLabel(container, "ph:plugs")'),
        body.index("container.append(text, link)"),
        body.index("container.append(close)"),
    ]
    assert order == sorted(order), "the row's order is icon, sentence, button, close"
    assert 'text.className = "ai-offline-text"' in body
    assert "detail" in body and "link.title" in body, "the long half lives in the button's title"

    #: Every container draws the recipe's box, so none keeps a private one.
    html = (ROOT / "frontend" / "index.html").read_text(encoding="utf-8")
    for ident in ("chat-offline", "ask-offline", "draft-offline", "command-palette-offline"):
        assert re.search(rf'id="{ident}" class="ai-offline-note notice hidden"', html), ident
    dashboard = with_pieces("dashboard.js")
    assert 'offline.className = "ai-offline-note notice hidden"' in dashboard

    #: One short sentence per surface (under 90 characters), no exclamation mark.
    sentences = re.findall(r'renderAiOfflineNotice\(\s*\$\("[a-z-]+"\),\s*"([^"]+)"', status)
    assert len(sentences) == 4, sentences
    for sentence in sentences:
        assert len(sentence) < 90 and "!" not in sentence, sentence

    css = "\n".join(path.read_text(encoding="utf-8") for path in CSS)
    row = re.search(r"\n\.ai-offline-note\.notice \{(.*?)\n\}", css, re.S)
    assert row and "align-items: center" in row.group(1), ".ai-offline-note.notice has no row rule"
    assert re.search(r"\n\.ai-offline-text \{[^}]*flex: 1 1 12rem;[^}]*min-width: 0", css), (
        "the sentence takes the spare width and can shrink, or the button is pushed out of the box"
    )
    #: `.notice` does not wrap; this row alone wraps, so the action steps to a
    #: second row when the words would be squeezed under 12rem (mono, a narrow card).
    notice = re.search(r"\n\.notice \{(.*?)\n\}", css, re.S).group(1)
    assert "flex-wrap" not in notice and "flex-wrap: wrap" in row.group(1)
    phone = re.search(r"@media \(max-width: 599\.98px\) \{\s*\.ai-offline-note\.notice \{(.*?)\n  \}(.*?)\n\}\n", css, re.S)
    assert phone and "display: grid" in phone.group(1), "under 600px (599.98px) the row is a grid"
    assert re.search(r"\.icon-only\) \{[^}]*grid-area: 2 / 2", phone.group(2)), "the button sits under the sentence"
    assert re.search(r"\.ai-offline-note > \.icon-only \{[^}]*grid-area: 1 / 3", phone.group(2)), (
        "the close stays at the end of the first row on a phone"
    )




def test_what_a_field_was_read_as_is_one_chip_row() -> None:
    """DESIGN.md, "What a field's words were read as" (CHAT_PLAN decision 50):
    the chips under a field come from quickadd.js alone, and no surface asks
    the reading route for itself, so every field reads, asks and saves the
    same way."""
    own = {"quickadd.js"}
    builders = [p.name for p in JS if p.name not in own and "qa-chips" in p.read_text(encoding="utf-8")]
    assert not builders, f"a chip row built outside quickadd.js: {builders}"
    readers = [
        p.name
        for p in JS
        if p.name not in own and re.search(r"""["'`]/(?:api/)?read\?""", p.read_text(encoding="utf-8"))
    ]
    assert not readers, f"a surface asking /read itself rather than through quickAddAttach: {readers}"
# Phase 12 decisions 2 and 3 (UI_MODERNISATION_PLAN; DESIGN.md, the ten rules
# 4 and 6) had an icon button answer hover with its glyph alone; the owner
# retired that on 2026-10-10 (INBOX 784/788): every button takes the one quiet
# box, `test_every_button_answers_hover_with_the_same_quiet_box` below.
_NOT = re.compile(r":not\((?:[^()]|\([^()]*\))*\)")


def _served_rules():
    from tessellate.api.asset_strip import strip_for_path

    for path in CSS:
        served = strip_for_path(path.name, path.read_bytes()).decode("utf-8")
        served = re.sub(r"@(media|supports|container)[^{]*\{", "", served)
        for m in re.finditer(r"([^{}]+)\{([^{}]*)\}", served):
            yield path.name, [s.strip() for s in m.group(1).split(",")], m.group(2)


#: The fills a button's hover may paint: the quiet tokens the recipe names (a
#: tonal button's `--ghost-btn-bg`, a status item's `--chip-bg`, a row's veil,
#: a surface step, the accent's low alpha for an open or chosen one, the filled
#: button's own deeper step).
_BUTTON_HOVER_OK = re.compile(
    r"^(transparent|none|var\(--(ghost-btn-bg|ghost-btn-bg-hover|surface-2|chip-bg|hover-veil|row-hover-bg|accent-soft|accent-surface-hover|button-ground)\)"
    r"|linear-gradient\(var\(--hover-veil\), var\(--hover-veil\)\)(?: var\(--[a-z-]+\))?)\s*(!important)?$"
)


def test_every_button_answers_hover_with_the_same_quiet_box() -> None:
    """INBOX 784/788, the owner: "not all buttons have the same hover states ...
    all the ui styles across the app need to be consistent". An icon button used
    to answer hover with its glyph's colour and no box (Phase 12 decision 2) while
    a labelled button beside it took a box; the top bar showed both. One recipe now
    (DESIGN.md, "One hover for every button"): a quiet fill from the recipe's
    tokens, the glyph to full ink, and the accent colour kept for what is chosen.
    The tokens an icon's hover paints are no longer nulled, and no icon selector's
    hover is a colour change alone."""
    forms = (ROOT / "frontend" / "css" / "01-forms-settings.css").read_text(encoding="utf-8")
    assert not re.search(r":is\(button, summary\):is\(\.icon-only[^{]*\{[^}]*--hover-veil: transparent", forms), (
        "an icon button's hover tokens are nulled again: that is the glyph-only grammar the owner retired"
    )
    assert not re.search(r":is\(\.icon-only, \.icon-button[^)]*\):is\(:hover, :focus-visible\) \{\s*--ink: var\(--accent-text\)", forms)
    assert re.search(r":is\(button, summary\):is\(\.icon-only, \.icon-button[^{]*\{\s*--ghost-btn-bg: var\(--hover-veil\)", forms), (
        "borderless buttons share one fill, the veil (the bell and 'All spaces' measured 0.12 and 0.07 side by side)"
    )
    assert re.search(
        r":is\(button, summary\)\.ghost:is\(\.icon-only, \.icon-button\)[^{]*:is\(:hover, :focus-visible, \[aria-expanded=\"true\"\]\) \{\s*background: var\(--ghost-btn-bg\)",
        forms,
    ), "the icon button's hover fill is gone from 01-forms-settings.css"
    bad = []
    for name, sels, body in _served_rules():
        hits = [s for s in sels if ":hover" in s and re.search(r"\.icon-(only|button)\b", _NOT.sub("", s))]
        if not hits:
            continue
        values = re.findall(r"(?:^|;)\s*background(?:-color)?\s*:\s*([^;]+)", body)
        for value in values:
            if not _BUTTON_HOVER_OK.match(value.strip()):
                bad.append(f"{name}: {hits[0][:80]} -> background {value.strip()[:40]}")
        color = re.search(r"(?:^|;)\s*color\s*:\s*([^;]+)", body)
        if color and not values and "accent" in color.group(1):
            bad.append(f"{name}: {hits[0][:80]} -> only the glyph goes to {color.group(1).strip()[:30]}")
    assert not bad, "an icon button's hover departs from the one recipe (DESIGN.md, One hover for every button):\n" + "\n".join(bad)


def test_the_dashboards_search_doorway_answers_hover_with_the_box() -> None:
    """`.dash-find` was the one button answering hover with its glyph and an
    accent edge. It takes the veil box and full ink like every other button."""
    bad = []
    found = 0
    for name, sels, body in _served_rules():
        if not any("dash-find" in s and (":hover" in s or ":focus-visible" in s) for s in sels):
            continue
        found += 1
        if "--hover-veil" not in body:
            bad.append(f"{name}: {sels[0][:70]} has no veil")
        if re.search(r"border-color\s*:\s*var\(--accent", body):
            bad.append(f"{name}: {sels[0][:70]} answers with the accent edge")
    assert found >= 2 and not bad, "\n".join(bad) or "the .dash-find hover rules are gone"


def test_a_backlink_row_action_is_the_quiet_row_action() -> None:
    """The unlinked mention's Link (Connections and a document's panel) was a
    bordered ghost button. It is the list row's action: no edge or fill at
    rest, the veil on hover, like the insight verdicts."""
    css = (ROOT / "frontend" / "css" / "05-sidebars-themes.css").read_text(encoding="utf-8")
    m = re.search(r"\.doc-backlink-foot > button\.doc-backlink-action \{([^}]*)\}", css)
    assert m, "the backlink action's row recipe is gone"
    assert re.search(r"border:\s*0", m.group(1)) and "background: transparent" in m.group(1)
    assert re.search(r"doc-backlink-action:is\(:hover, :focus-visible\):not\(:disabled\) \{\s*background: var\(--hover-veil\)", css)


def test_every_help_trigger_is_one_shape() -> None:
    """The owner: "Some tooltip buttons are circles and some are rounded squares"."""
    round_ = []
    for name, sels, body in _served_rules():
        if not any(re.search(r"graph-help-toggle|data-help-for", s) for s in sels):
            continue
        for value in re.findall(r"(?:^|;)\s*border-radius\s*:\s*([^;]+)", body):
            if re.search(r"50%|999|radius-pill", value):
                round_.append(f"{name}: {sels[0][:70]} -> {value.strip()}")
    assert not round_, "a help trigger is drawn round; it takes the button radius:\n" + "\n".join(round_)


def test_a_date_or_time_field_is_the_picker_recipe() -> None:
    """Phase 12 decision 5: the page's date and time fields are enhanced at boot,
    keep their native value (a write repaints, a focus lands on the face) and
    read typed words with `ai/when`, never a second picker built by hand."""
    selects = with_pieces("sheets-selects.js")
    boot = selects[selects.index("function watchForSelects()"):]
    boot = boot[: boot.index("new MutationObserver")]
    assert 'querySelectorAll(\'input:is([type="date"], [type="time"])\')' in boot and "enhanceDateField(field)" in boot
    body = selects[selects.index("function enhanceDateField(input)"):]
    body = body[: body.index("\n}\n")]
    for need in ('Object.defineProperty(input, "value"', "input.focus = (options) => opener.focus(options)",
                 'ensureModule("dateField")', "dateFieldWire(input, opener, panel, label, isTime)"):
        assert need in body, need
    panel = (ROOT / "frontend" / "js" / "date-field.js").read_text(encoding="utf-8")
    for need in ("wireHelpPopover(opener, panel)", '"/reminders/when"', '"timeline-monthpop-grid"'):
        assert need in panel, need
    others = [p.name for p in JS if p.name != "date-field.js" and "/reminders/when" in p.read_text(encoding="utf-8")]
    assert not others, f"a second typed-date reader: {others}"


def test_an_insights_verdicts_are_one_compact_pair_on_the_sentences_row() -> None:
    """INBOX 782, the owner: "redesign the confirm and not right buttons ... and
    any other similar instances of them across the app". Chat's pattern lines
    and Tidy's Patterns draw them with `insightLine` (status.js); the
    dashboard's ⋯ takes the same two items from `INSIGHT_VERDICT_ITEMS`. No
    other file words the pair, and the pair is quiet (no edge, no fill at
    rest), not two full-size bordered buttons under the sentence."""
    status = with_pieces("status.js")
    assert "function insightLine(" in status and "function insightVerdicts(" in status
    assert "const INSIGHT_VERDICT_ITEMS" in status
    copies = []
    for path in JS:
        text = path.read_text(encoding="utf-8")
        code = "\n".join(line for line in text.splitlines() if not line.lstrip().startswith("//"))
        if path.name != "status.js" and re.search(r"""["'](?:ph:x )?Not right["']""", code):
            copies.append(path.name)
        if path.name != "status.js" and "insightVerdicts(" in code:
            copies.append(f"{path.name} calls the pair directly: use insightLine")
    assert not copies, f"the Confirm and Not right pair is drawn in one place; also in: {copies}"
    css = "\n".join(
        m.group(0) for m in re.finditer(r"\.insight-verdict\s*\{[^}]*\}", (ROOT / "frontend" / "css" / "04-chat-dock-appearance.css").read_text(encoding="utf-8"))
    )
    assert "border: 0" in css and "background: transparent" in css, "the pair is quiet at rest"
    for name in ("chat-attach.js", "tidy.js"):
        assert "insightLine(" in (ROOT / "frontend" / "js" / name).read_text(encoding="utf-8"), name


def test_a_changed_setting_is_marked_by_the_rows_recipe():
    """DESIGN.md, "A setting changed from its default" (WORLD_CLASS_PLAN 25f).

    One file marks a changed row and draws its reset; a second marker or a
    reset built elsewhere would be two looks for one fact.
    """
    rows = (ROOT / "frontend" / "js" / "settings-rows.js").read_text(encoding="utf-8")
    assert 'button.className = "icon-only ghost small setting-reset"' in rows
    assert 'rowEl.classList.toggle("setting-modified", modified)' in rows
    others = [p.name for p in JS if p.name != "settings-rows.js" and "setting-modified" in p.read_text(encoding="utf-8")]
    assert not others, f"a changed setting marked outside settings-rows.js: {others}"
    css = "\n".join(p.read_text(encoding="utf-8") for p in CSS)
    #: The bar sits in the gutter, outside the text edge (the owner,
    #: 2026-10-11: an inset bar on the text edge clashed with the label).
    rule = re.search(r"#settings-modal \.setting-modified::before \{([^}]*)\}", css)
    assert rule and "background: var(--accent-text)" in rule.group(1)
    assert "inset-inline-start: calc(-1 * var(--space-3))" in rule.group(1) and "border:" not in rule.group(1)


def test_one_calendar_grid_of_dom_cells() -> None:
    """TIMELINE_PLAN section 9 (decisions 14, 15, 16, 19): the app has one
    calendar, the Timeline's, drawn by timeline-calendar.js as DOM cells in a
    CSS grid (no SVG), every day through `timelineCalCell`, three rows and a
    "+n" in a month cell, and its keys and drags on one delegated listener
    each on the view's box, never one per cell. The reminders tab opens it
    rather than drawing a month of its own."""
    cal = (ROOT / "frontend" / "js" / "timeline-calendar.js").read_text(encoding="utf-8")
    assert "const TIMELINE_CAL_ROWS = 3;" in cal
    #: A press on a day opens it, and the written notes are chips with titles
    #: wherever the cell has the room (the owner, 2026-10-11): fitted by
    #: measuring, never by a count that ignores the cell's height.
    assert "function timelineCalPick(" in cal and "timelineCalPick(cell.dataset.calDay)" in cal
    assert 'event.key === "Enter" || event.key === " "' in cal
    assert "timelineCalFit(grid)" in cal and "cell.clientHeight" in cal
    assert "<svg" not in cal and "createElementNS" not in cal, "the calendar is DOM cells, not SVG"
    assert cal.count('className = "timeline-cal-cell"') == 1, "every day is built by timelineCalCell"
    for event in ("keydown", "dragstart", "dragover", "drop"):
        assert len(re.findall(rf'addEventListener\("{event}"', cal)) == 1, event
    code = app_js_text()
    assert "function renderReminderCalendar" not in code, "one calendar (decision 19)"
    assert 'timelineCalendarCall("timelineCalendarReminders")' in code
    others = [p.name for p in JS if p.name != "timeline-calendar.js" and re.search(r"class(?:Name)?\s*=\s*[\"'][^\"']*-cal-grid", p.read_text(encoding="utf-8"))]
    assert not others, f"a second month grid: {others}"


def test_web_results_are_one_fold_read_in_place():
    """CHAT_PLAN decision 66 (INBOX 810): web results are one fold in the
    Thinking fold's look, a page read in place as text, built in one place."""
    text = (ROOT / "frontend/js/ask-compose.js").read_text(encoding="utf-8")
    body = text[text.index("function renderWebSources"):text.index("//: The digest's one offer")]
    assert 'fold.className = "agent-step web-fold"' in body and 'summary.className = "fold-summary"' in body
    assert "/websearch/read?url=" in body and "innerHTML" not in body and "iframe" not in body
    builders = [p.name for p in (ROOT / "frontend/js").glob("*.js") if "web-fold" in p.read_text(encoding="utf-8")]
    assert builders == ["ask-compose.js"], builders


def test_why_this_answer_is_one_fold_built_once():
    """CHAT_PLAN B30: how an answer was made is one fold in the Thinking
    fold's look, its lines text (never markup), built in one place."""
    text = (ROOT / "frontend/js/ask-compose.js").read_text(encoding="utf-8")
    start = text.index("function renderAskWhy")
    body = text[start:text.index("\n}\n", start)]
    assert 'fold.className = "agent-step why-fold"' in body and 'summary.className = "fold-summary"' in body
    assert "innerHTML" not in body and "textContent" in body
    builders = [p.name for p in (ROOT / "frontend/js").glob("*.js") if "why-fold" in p.read_text(encoding="utf-8")]
    assert builders == ["ask-compose.js"], builders


def test_answer_shape_is_lifted_in_one_place():
    """CHAT_PLAN decision 71: a count's figure and a who card are lifted from
    the rendered answer in one function, on tokens, without markup strings."""
    text = (ROOT / "frontend/js/ask-compose.js").read_text(encoding="utf-8")
    body = text[text.index("function digestShape"):text.index("//: **Short by default, More expands**")]
    assert 'className = "digest-figure"' in body and 'className = "digest-card"' in body
    assert "innerHTML" not in body and "setLabel(head" in body
    css = (ROOT / "frontend/css/ask-compose-lazy.css").read_text(encoding="utf-8")
    card = css[css.index(".digest-card {"):css.index("}", css.index(".digest-card {"))]
    for token in ("var(--surface-2)", "var(--border)", "var(--radius-md)", "var(--space-3)"):
        assert token in card, token
    builders = [p.name for p in (ROOT / "frontend/js").glob("*.js") if "digest-card" in p.read_text(encoding="utf-8")]
    assert builders == ["ask-compose.js"], builders
    more = text[text.index("function digestMore"):text.index("//: The digest's one offer")]
    assert 'className = "linklike digest-more"' in more and "aria-expanded" in more and ".hidden = true" in more
    ask = (ROOT / "frontend/js/capture-ask.js").read_text(encoding="utf-8")
    assert "digestShape(answerEl, support.shape, support.figure)" in ask and "digestMore(answerEl, support.more)" in ask


# A note's or document's name is shown through one helper (INBOX 820, the
# owner: layers "and potentially other places in the app dont handle inline md
# rendering or cut it out"; a board's Layers row read "Note card: **Current
# Commit..."). `noteNamePlain(content, limit)` in chat-attach.js drops the
# frontmatter, takes the first line with words and turns its Markdown into the
# words it means. A hand-rolled `.split("\n")[0]` on a note's content hands the
# reader the stored syntax, so each remaining one is named here with why it is
# not a name; a new one fails the build.
FIRST_LINE_SPLIT = re.compile(r'\.split\("\\n"\)\[0\]')
FIRST_LINE_NOT_A_NAME = {
    "capture-ask.js": 1,  # a figure caption's own words, not a note
    "documents-code.js": 3,  # parser messages and a search seed from code
    "documents-codekit.js": 2,  # a snippet's first line of code
    "documents-prose.js": 1,  # a prose-check option's text
    "documents.js": 2,  # an editor selection and a placeholder
    "editor.js": 2,  # the link target a [[wiki link]] resolves by (stored words, brackets stripped)
    "quick-note.js": 1,  # the quick-note field's own typed title
}


def test_a_note_is_named_through_note_name_plain_not_its_first_line() -> None:
    found: dict[str, int] = {}
    for path in JS:
        text = "\n".join(line for line in path.read_text(encoding="utf-8").splitlines() if not line.lstrip().startswith("//"))
        count = len(FIRST_LINE_SPLIT.findall(text))
        if count:
            found[path.name] = count
    assert found == FIRST_LINE_NOT_A_NAME, (
        f"a first-line split on content outside noteNamePlain: {found} (allowed {FIRST_LINE_NOT_A_NAME}); "
        "name a note with noteNamePlain(content, limit) (chat-attach.js)"
    )


def test_note_name_plain_is_defined_once_and_used_by_the_name_sites() -> None:
    text = (ROOT / "frontend" / "js" / "chat-attach.js").read_text(encoding="utf-8")
    assert len(re.findall(r"^function noteNamePlain\(", text, flags=re.M)) == 1
    used = {p.name for p in JS if "noteNamePlain(" in p.read_text(encoding="utf-8")}
    for name in ("whiteboard.js", "dashboard.js", "graph.js", "menus.js", "palette.js", "notes-list.js", "phone-shell.js", "note-cards.js"):
        assert name in used, name


# --- INBOX 803: the quiet tier in a card, a disclosure row, a counted chip -----------


def _forms_css() -> str:
    return (ROOT / "frontend" / "css" / "01-forms-settings.css").read_text(encoding="utf-8")


def test_a_ghost_in_a_card_is_quiet() -> None:
    """The owner (INBOX 803): "Im still iffy about the design use of these
    buttons styles in some places", three times over, each a tinted bordered
    box inside a card or a panel. One rule draws the quiet tier for every
    ghost in a card that is not a dialog, at the tonal rule's own weight
    (`:where`), with the same tint under the pointer and the keyboard."""
    css = _forms_css()
    head = ":where(.card) button.ghost:where(:not(:is(dialog, .modal-card, .modal) *))"
    rest = re.search(re.escape(head) + r" \{([^}]*)\}", css)
    assert rest and "border-color: transparent" in rest.group(1) and "background: none" in rest.group(1)
    assert re.search(
        re.escape(head) + r":hover,\s*" + re.escape(head) + r":is\(:focus-visible, :has\(:focus-visible\)\) \{[^}]*--ghost-btn-bg",
        css,
    )
    assert css.index(head) > css.index("button.ghost:hover,"), "after the tonal rule, so it wins on order"


def test_a_disclosure_is_a_row_not_a_boxed_button() -> None:
    css = _forms_css()
    assert re.search(r"button\.ghost\.disclosure-row \{[^}]*width: 100%[^}]*border-color: transparent[^}]*background: none", css)
    assert re.search(r"button\.ghost\.disclosure-row:hover,\s*button\.ghost\.disclosure-row:is\(:focus-visible", css)
    assert '"ghost small disclosure-row night-kind-toggle"' in with_pieces("dashboard.js")


def test_a_counted_filter_is_a_chip() -> None:
    body = _function_body((ROOT / "frontend" / "js" / "graph-canvas.js").read_text(encoding="utf-8"), "gcFilterChip")
    assert 'chip(label, "tag graph-filter-chip", onClick)' in body
    assert "library-chip" not in body.replace("library-chip-count", "")


# --- INBOX 804/810/813: row actions, a set to start, bar controls -------------------


def _css_all() -> str:
    return "\n".join(p.read_text(encoding="utf-8") for p in CSS)


def test_a_rows_repeated_action_is_quiet_and_three_fold_into_its_menu() -> None:
    """DESIGN.md, Row actions (INBOX 810): a column of thirty-one bordered
    "Change" buttons was the loudest thing in the Shortcuts pane. A repeated
    action is a quiet text button, a destructive one is muted until aimed at,
    and a row of three or more keeps its first and folds the rest into ⋯."""
    body = _function_body(with_pieces("sheets-selects.js"), "rowActions")
    assert 'b.classList.add("quiet")' in body and 'b.classList.add("danger")' in body
    assert "actions.length < 3" in body and "kebabMenu(actions.slice(1), ariaLabel)" in body
    css = _forms_css()
    assert re.search(r"button\.ghost\.quiet \{[^}]*border-color: transparent;[^}]*background: none", css)
    assert re.search(r"button\.ghost\.quiet\.danger \{[^}]*color: var\(--muted\)", css)
    assert re.search(
        r"button\.ghost\.quiet\.danger:hover,\s*button\.ghost\.quiet\.danger:is\(:focus-visible, :has\(:focus-visible\)\) \{[^}]*color: var\(--error\)",
        css,
    )
    for name, needle in (("settings.js", "rowActions(acts, "), ("settings-data.js", "rowActions([")):
        assert needle in (ROOT / "frontend" / "js" / name).read_text(encoding="utf-8"), name


def test_a_shortcuts_keys_are_its_rebind_button() -> None:
    """The key chip is the button (title "Change"); no column of Change."""
    body = _function_body((ROOT / "frontend" / "js" / "settings-wiring.js").read_text(encoding="utf-8"), "buildShortcutList")
    assert '"ghost small quiet shortcut-key"' in body and "change.append(combo, pen)" in body
    assert 'change.title = capturing ? "Cancel" : "Change"' in body
    assert "textContent = capturingShortcut === id ? \"Cancel\" : \"Change\"" not in body
    assert re.search(r"\.shortcut-list button\.shortcut-key \{[^}]*min-height: var\(--target-min\)", _css_all())


def test_a_set_to_start_is_rows_with_their_descriptions_not_a_wall() -> None:
    """DESIGN.md, "A set of things to start" (INBOX 804): Help's fourteen tour
    buttons became one row each, the section's name over its one-line blurb,
    under the pane's one filled button (Start the tour) and a quiet second."""
    tour = _function_body((ROOT / "frontend" / "js" / "tour.js").read_text(encoding="utf-8"), "renderTourReplay")
    assert '"ghost small tour-row"' in tour and "tour-row-blurb" in tour and "section.blurb" in tour
    assert 'createElement("li")' in tour
    html = (ROOT / "frontend" / "index.html").read_text(encoding="utf-8")
    assert '<ul id="tour-replay-buttons"' in html
    assert '<button id="tour-start-btn" class="small" type="button">' in html
    assert re.search(r'<button id="show-guide-btn" class="ghost small quiet"', html)
    css = _css_all()
    assert re.search(r"button\.ghost\.tour-row \{[^}]*border-color: transparent;[^}]*background: none", css)


def test_a_bar_has_one_select_one_filter_trigger_and_one_view_order() -> None:
    """DESIGN.md, Bar controls (INBOX 813). One bar select: the dock's
    edgeless inset, also in the Ask composer and the chat strip. One filter
    trigger: icon and word, the word a `.dock-word` that leaves on a phone.
    One view order: list, then grid."""
    css = (ROOT / "frontend" / "css" / "08-consistency.css").read_text(encoding="utf-8")
    rule = re.search(
        r"\.dock \.select-shell > \.select-opener,\s*\.ask-composer \.select-shell > \.select-opener,\s*"
        r"\.chat-dock-controls \.select-shell > \.select-opener \{([^}]*)\}",
        css,
    )
    assert rule and "border: 1px solid transparent" in rule.group(1) and "var(--field-inset)" in rule.group(1)
    html = (ROOT / "frontend" / "index.html").read_text(encoding="utf-8")
    for summary in re.findall(r"<summary[^>]*>\s*<i class=\"ph ph-funnel-simple[^\n]*", html):
        assert '<span class="dock-word">Filter</span>' in summary, summary[:120]
    assert re.search(r"\.dock \.dock-menu > summary \.dock-word", _css_all())
    for seg in re.findall(r'<div class="seg[^"]*"[^>]*>(.*?)</div>', html, re.S):
        if "ph-rows" in seg and "ph-squares-four" in seg:
            assert seg.index("ph-rows") < seg.index("ph-squares-four"), "a view switch is list, then grid"


def test_the_documents_assistant_is_one_composer_at_one_height() -> None:
    """INBOX 804: the asks, the field and its send were three heights and
    three looks. The field is the search well with the send inside it; the
    asks and tools are quiet chips; all at `--control-h`."""
    html = (ROOT / "frontend" / "index.html").read_text(encoding="utf-8")
    assert '<form id="doc-assist-form" class="search-field doc-assist-form">' in html
    css = (ROOT / "frontend" / "css" / "library-lazy.css").read_text(encoding="utf-8")
    assert re.search(r"\.search-field\.doc-assist-form \{[^}]*height: var\(--control-h\)", css)
    chips = re.search(r"\.doc-assist-asks > button\.ghost,\s*\.doc-assist-tools > button\.ghost \{([^}]*)\}", css)
    assert chips and "height: var(--control-h)" in chips.group(1) and "border-color: transparent" in chips.group(1)
    line = re.search(r"\.cm-console-line \{([^}]*)\}", css)
    assert line and "padding: var(--space-1) var(--space-3)" in line.group(1), "the ring keeps clear of the rule above"


def test_a_toasts_action_is_a_quiet_text_action() -> None:
    """INBOX 811, the owner of a toast's bordered grey Undo: the action is
    the accent's text on no face and no edge; the toast is wide enough that
    a one-sentence notice and its Undo stay one line."""
    css = (ROOT / "frontend" / "css" / "02-chat-graph.css").read_text(encoding="utf-8")
    rule = re.search(r"\.toast-action,\s*\.toast \.toast-help \{([^}]*)\}", css)
    assert rule and "background: none" in rule.group(1) and "color: var(--accent-text)" in rule.group(1)
    assert "border: 1px solid transparent" in rule.group(1)
    assert re.search(r"\.toast > \.toast-msg \{[^}]*text-wrap: pretty", css)
    assert re.search(r"\.toast \{[^}]*max-width: 30rem", _forms_css())


def test_a_menu_has_no_gap_at_its_ends() -> None:
    """The owner: "some dropdown menus across the app have wierd gaps at the
    start and end". A dock menu's section pads itself from the hairline
    between sections, never from the menu's own first and last edge."""
    css = (ROOT / "frontend" / "css" / "07-whiteboard-misc.css").read_text(encoding="utf-8")
    assert re.search(r"\.dock-menu-list > :is\(\.dock-menu-section, \.dock-arrange-label\):first-child \{\s*padding-top: 0;", css)
    assert re.search(r"\.dock-menu-list > \.dock-menu-section:last-child \{\s*padding-bottom: 0;", css)
    sweep = (ROOT / "scratchpad" / "ui-sweeps" / "menus.js").read_text(encoding="utf-8")
    assert "inset top" in sweep and ".dock-menu-check" in sweep


def test_an_address_for_another_device_is_one_block_drawn_by_one_renderer() -> None:
    """INBOX 867, the owner of the receipt's run-on list of four addresses:
    "can this be better styled and easier to read??". Settings, Other
    devices and the privacy receipt draw one block, from one function: the
    first address large with Copy, the rest behind a disclosure row."""
    js = ROOT / "frontend" / "js"
    controls = (js / "settings-controls.js").read_text(encoding="utf-8")
    body = controls.split("function renderLanAddresses(", 1)[1].split("\n}\n", 1)[0]
    assert '"lan-address"' in body and "copyToClipboard(" in body
    assert "disclosure-row" in body and "aria-expanded" in body
    assert 'renderLanAddresses($("account-lan-addresses")' in controls
    assert 'renderLanAddresses(where' in (js / "settings-data.js").read_text(encoding="utf-8")
    for name in ("settings-controls.js", "settings-data.js"):
        text = (js / name).read_text(encoding="utf-8")
        assert 'addresses.join(" or ")' not in text and '.join(", ") || listening.host' not in text, name
def test_note_card_show_more_hugs_its_label():
    """INBOX 901: a `display: block` button spans the card, so "Show more"
    sat centred far from the text with a card-wide focus ring."""
    css = (ROOT / "frontend" / "css" / "03-dashboard-widgets.css").read_text()
    m = re.search(r"#entry-list:not\(\.is-rows\) \.entry-more \{([^}]*)\}", css)
    assert m, "card-view .entry-more rule missing"
    body = m.group(1)
    assert "width: fit-content" in body
    assert "text-align: start" in body
    assert "width: 100%" not in body


def test_assistant_tools_are_an_even_grid():
    """The owner: the code assistant's four tool buttons wrapped 3+1."""
    css = (ROOT / "frontend" / "css" / "library-lazy.css").read_text()
    assert re.search(r"\.doc-assist-tools \{[^}]*grid-template-columns: repeat\(2, minmax\(0, 1fr\)\)", css)
    assert not re.search(r"\.doc-assist-tools,\s*\.doc-assist-apply", css)


def test_no_model_notice_action_keeps_its_border():
    """The owner: the Connect a model action must read as a button. A card
    quiets its ghost buttons to edgeless, so the notice restores the edge."""
    css = (ROOT / "frontend" / "css" / "03-dashboard-widgets.css").read_text()
    m = re.search(r"\.ai-offline-note > button\.ghost:not\(\.icon-only\) \{([^}]*)\}", css)
    assert m, "no-model notice action rule missing"
    assert "border-color: var(--ghost-btn-border)" in m.group(1)
    assert "transparent" not in m.group(1)


def test_file_reading_text_fits_up_to_a_page():
    """The owner: the extracted text in a Files row was quite short."""
    css = (ROOT / "frontend" / "css" / "library-lazy.css").read_text()
    m = re.search(r"\.library-file-reading-text \{([^}]*)\}", css)
    assert m and "max-height: min(28rem, 55vh)" in m.group(1)
    shell = (ROOT / "frontend" / "css" / "00-tokens-shell.css").read_text()
    assert re.search(r"\.library-image-card-fold > \.library-image-reading-body \{\s*max-height: 11rem", shell)
#: DESIGN.md, "A control that acts on the computer Tessellate runs on". Every
#: static control that reaches a `this_computer_only` route or a this-computer
#: preference (routes_settings `_THIS_COMPUTER_PREFERENCES`).
THIS_COMPUTER_CONTROLS = {
    "llm-provider-select", "llm-provider-apply", "local-only-ai", "restore-bundle", "import-dir",
    "pref-searxng", "searxng-detect", "searxng-start", "searxng-stop", "searxng-reinstall", "searxng-autostart",
    "pref-update-check", "pref-auto-update", "pref-update-channel-main", "update-install-version",
    "extras-list", "extras-bulk-install", "embed-choices", "embed-pull-go",
    "embedding-apply", "pref-semantic-auto-install", "quit-btn", "app-quit",
}


class _ThisComputerScan(HTMLParser):
    VOID = {"input", "img", "br", "hr", "meta", "link", "source", "wbr", "area", "col", "embed", "track"}

    def __init__(self) -> None:
        super().__init__()
        self.stack: list[bool] = []
        self.marked: set[str] = set()

    def handle_starttag(self, tag, attrs):
        attrs = dict(attrs)
        inside = (bool(self.stack) and self.stack[-1]) or "data-this-computer" in attrs
        if inside and attrs.get("id"):
            self.marked.add(attrs["id"])
        if tag not in self.VOID:
            self.stack.append(inside)

    def handle_endtag(self, tag):
        if tag not in self.VOID and self.stack:
            self.stack.pop()


def test_a_control_that_acts_on_this_computer_says_so_elsewhere() -> None:
    from tessellate.api.this_computer import REFUSAL

    scan = _ThisComputerScan()
    scan.feed((ROOT / "frontend" / "index.html").read_text(encoding="utf-8"))
    assert not THIS_COMPUTER_CONTROLS - scan.marked, sorted(THIS_COMPUTER_CONTROLS - scan.marked)
    skills = (ROOT / "frontend" / "js" / "skills.js").read_text(encoding="utf-8")
    assert f'const THIS_COMPUTER_ONLY = "{REFUSAL}";' in skills
    assert "markOtherDevice().catch" in skills


def test_a_panel_head_is_a_title_and_not_the_eyebrow() -> None:
    """Row 1586: `h3.panel-head` (and the board sidebar's and Format panel's
    `h3.wb-sidebar-title`) names a whole card or column, so it draws in the
    dialog title's voice; `.card h3` (the eyebrow, 12px) is for a label over
    one group. Measured: five panel heads and both board panel heads at 12px
    beside the Web panel's 16px."""
    consistency = (ROOT / "frontend" / "css" / "08-consistency.css").read_text(encoding="utf-8")
    rule = next(
        body for sel, body in _rules(consistency)
        if ".card h3.panel-head" in sel and "h3.wb-sidebar-title" in sel
    )
    assert "font-size: var(--text-body)" in rule
    assert "text-transform: none" in rule
    assert "color: var(--ink)" in rule
    html = (ROOT / "frontend" / "index.html").read_text(encoding="utf-8")
    heads = re.findall(r'<(\w+) class="panel-head\b', html)
    assert heads and set(heads) == {"h3"}, f"a panel head left the h3 recipe: {sorted(set(heads))}"


#: Filters built by hand before `listFilter` existed (row 1643): each keeps
#: its own field because its list does more than hide rows (a sort, a scope,
#: a count). May only shrink; a new long list calls `listFilter`.
HAND_BUILT_FILTERS = {
    "Filter widgets…", "Filter notes", "Filter headings…", "Filter this index…",
    "Filter logs", "Filter tags", "Filter categories", "Filter names",
}


def test_a_long_list_is_typed_to_through_the_one_recipe() -> None:
    """Row 1643 (WORLD_CLASS_PLAN 22.2, "every list with more than 20 rows
    can be filtered by typing"): `listFilter` is the one builder, the
    shortcut list (31 rows) and the space menu use it, and no new
    hand-built "Filter ..." field joins the eight that predate it."""
    selects = with_pieces("sheets-selects.js")
    body = selects.split("function listFilter(", 1)[1][:3000]
    assert 'field.className = "search-field list-filter hidden"' in body
    assert 'event.key === "Escape"' in body and "list-filter-empty" in body
    wiring = (ROOT / "frontend" / "js" / "settings-wiring.js").read_text(encoding="utf-8")
    assert "listFilter(list, { label: \"Filter shortcuts\" })" in wiring.split("function buildShortcutList", 1)[1][:4000]
    spaces = (ROOT / "frontend" / "js" / "spaces-find.js").read_text(encoding="utf-8")
    assert "listFilter(menu," in spaces.split("function renderSpaceMenu", 1)[1][:3000]
    found = set()
    for path in [ROOT / "frontend" / "index.html", *sorted((ROOT / "frontend" / "js").glob("*.js"))]:
        found |= set(re.findall(r'placeholder\s*=\s*"(Filter[^"]*)"', path.read_text(encoding="utf-8")))
    assert found <= HAND_BUILT_FILTERS, f"a hand-built filter field: {sorted(found - HAND_BUILT_FILTERS)}; call listFilter"
    assert found == HAND_BUILT_FILTERS, "a hand-built filter moved to listFilter: shrink HAND_BUILT_FILTERS"


def test_the_local_chip_shows_the_privacy_verdict_and_opens_the_record() -> None:
    """Row 1641 (WORLD_CLASS_PLAN 22.1 item 9): the top bar's Local chip reads
    `/privacy/verdict`, opens Settings, Privacy, stays hidden until it has an
    answer, and is a row of the phone's header menu below 600."""
    html = (ROOT / "frontend" / "index.html").read_text(encoding="utf-8")
    header = re.search(r'<header id="top-bar">(.*?)</header>', html, re.S).group(1)
    chip = re.search(r'<button id="privacy-chip"[^>]*>', header)
    assert chip and "hidden" in chip.group(0), "the Local chip left the top bar, or shows before it knows"
    status = with_pieces("status.js")
    assert '"/privacy/verdict"' in status
    assert 'openSettingsModal("privacy")' in status.split("function startPrivacyChip", 1)[1][:600]
    # Its one call site: every unlock, beside the reminder watch.
    assert "startPrivacyChip();" in status.split("function startReminderWatch(", 1)[1][:900]
    phone = (ROOT / "frontend" / "js" / "phone-shell.js").read_text(encoding="utf-8")
    rows = re.search(r"const PHONE_STATUS_ROWS = \[(.*?)\];", phone, re.S).group(1)
    assert '"privacy-chip"' in rows
    responsive = (ROOT / "frontend" / "css" / "10-responsive.css").read_text(encoding="utf-8")
    assert "#top-bar #privacy-chip" in responsive


def test_the_flag_marker_is_one_toggle_not_two_previews():
    """Ledger 1546 (seg665 item 5): an on/off marker is a single pressed-state button."""
    wm = frontend_text("whiteboard-map.js")
    assert 'wbMapMarkerToggle("Flag"' in wm
    assert 'wbMapMarkerSeg("Flag"' not in wm
    toggle = wm[wm.index("function wbMapMarkerToggle("):]
    toggle = toggle[: toggle.index("\n}\n")]
    assert "aria-pressed" in toggle and "choose(!on)" in toggle
def test_a_check_result_row_is_the_health_row_with_a_mark():
    """DESIGN.md, "The result of a check on this computer": Settings, About,
    Maintenance's rows are the Health group's `.setting-row`, the label led by
    one `.doctor-mark` whose glyph and tone both carry the result, built in
    one place."""
    js = frontend_text("settings-controls.js")
    build = js[js.index("function maintenanceDoctorRow(row) {"):]
    build = build[: build.index("\n}\n")]
    assert 'el.className = "setting-row doctor-row";' in build and "doctor-mark is-" in build
    assert 'label.className = "setting-label";' in build and 'value.className = "setting-control muted";' in build
    for tone, glyph in (("ok", "check-circle"), ("warn", "warning"), ("x", "x-circle")):
        assert f'{tone}: ["{glyph}",' in js
    builders = [p.name for p in JS if "doctor-mark" in p.read_text(encoding="utf-8")]
    assert builders == ["settings-controls.js"], builders
    css = _css_all()
    for tone, token in (("ok", "--ok"), ("warn", "--warn"), ("x", "--error")):
        assert re.search(rf"\.doctor-mark\.is-{tone} \{{\s*color: var\({token}\);", css), tone
def test_the_drop_veil_takes_no_press_and_has_no_blur() -> None:
    """DESIGN.md "A drop target" (ledger libr-1011 row 1266): the veil laid over
    the window while files are dragged in must not catch the drag, and a blurred
    full-window surface is the cost the glass-off list exists to avoid."""
    css = (ROOT / "frontend" / "css" / "file-drop-lazy.css").read_text(encoding="utf-8")
    veil = _css_block_in(css, ".drop-veil")
    assert "pointer-events: none" in veil and "position: fixed" in veil
    assert "backdrop-filter" not in css and "blur(" not in css
    assert "var(--accent-soft)" in veil and "var(--accent)" in veil
    design = (ROOT / "docs" / "DESIGN.md").read_text(encoding="utf-8")
    assert "**The drop veil**" in design
    for path in JS:
        if path.name != "file-drop.js":
            assert "drop-veil" not in path.read_text(encoding="utf-8"), f"{path.name} builds its own drop veil"


def _css_block_in(css: str, selector: str) -> str:
    start = css.index(selector + " {")
    return css[start : css.index("}", start)]


def test_a_modal_cards_dialog_head_is_sticky_on_an_opaque_surface() -> None:
    """C12: the head stays at the top of a scrolling modal card. Browser half:
    scratchpad/ui-sweeps/dialogheadsticky.js."""
    css = (ROOT / "frontend" / "css" / "08-consistency.css").read_text(encoding="utf-8")
    start = css.index(".modal-card > .dialog-head {")
    block = css[start : css.index("}", start)]
    assert "position: sticky;" in block and "top: 0;" in block
    assert "background: var(--modal-bg-opaque);" in block


def test_help_rows_do_not_animate_hover() -> None:
    """C25: scrolling Help at 4x CPU was 33.3ms a frame (median) because the wheel
    starts a hover transition on a new row every frame; 16.7 without them
    (scratchpad/ui-sweeps/helplag.js)."""
    css = (ROOT / "frontend" / "css" / "08-consistency.css").read_text(encoding="utf-8")
    start = css.index("#settings-help summary,")
    block = css[start : css.index("}", start)]
    assert "#settings-help .linklike" in block and "transition: none;" in block


def test_a_dot_on_the_graph_answers_with_its_hover_card():
    """DESIGN.md, "A card about one dot on a canvas" (INBOX 1300 C11): the
    hover card, never the native title, for a note on the Graph tab."""
    canvas = (ROOT / "frontend" / "js" / "graph-canvas.js").read_text(encoding="utf-8")
    css = (ROOT / "frontend" / "css" / "graph-lazy.css").read_text(encoding="utf-8")
    assert "s.canvas.title = node ? gcTooltip(node, s)" not in canvas
    assert "gcHoverCardFrame(s);" in canvas
    rule = css[css.index(".graph-hovercard {") :].split("}")[0]
    assert "backdrop-filter" not in rule and "var(--modal-bg-opaque)" in rule


def test_ghost_topics_are_one_lazy_layer_with_four_keys():
    """DESIGN.md, "Suggestions offered under a map topic": the picker dialog is
    gone; ghosts live in the lazy Library sheet, never the boot CSS."""
    js = (ROOT / "frontend" / "js" / "whiteboard-map.js").read_text(encoding="utf-8")
    body = js[js.index("function wbMapBranchPicker(") :]
    body = body[: body.index("\n}\n")]
    assert "pickerDialog(" not in body
    for needle in ('"Tab"', '"Enter"', '"Escape"', "is-taken", "wb-ghosts"):
        assert needle in body, needle
    lazy = (ROOT / "frontend" / "css" / "library-lazy.css").read_text(encoding="utf-8")
    assert ".wb-ghosts {" in lazy and ".wb-ghost.is-taken {" in lazy
    for boot in ("00-tokens-shell", "07-whiteboard-misc", "08-consistency"):
        assert "wb-ghost" not in (ROOT / "frontend" / "css" / f"{boot}.css").read_text(encoding="utf-8")
    rule = lazy[lazy.index(".wb-ghosts {") :].split("}")[0]
    assert "backdrop-filter" not in rule
