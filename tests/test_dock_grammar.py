"""Every control dock follows the dock grammar (UI_MODERNISATION_PLAN.md, Phase 8).

A dock is the control row at the top of a tab or sub-tab. The plan states one
grammar for all of them, identity, then find, then arrange, then actions , 
and this lint holds the parts of it that can be read from the markup:

- **Zone order.** Whatever zones a dock has appear in the order identity →
  find → arrange → actions, and each at most once.
- **One primary.** At most one filled button (a `<button>` with neither
  `ghost` nor `icon-only`) per dock. A second filled button is the "two
  answers to what this row is for" defect the plan names. "In the dock" here
  means the same thing the stylesheet means by it: a direct child of a zone,
  the run of controls `.dock > * > button` sizes. A clickable chip nested
  further in (the Chat header's model badge and context pill live inside the
  headline, as metadata you can press) is not in that run and is not a
  primary; keeping the lint and the stylesheet on one definition is what
  stops the two drifting.
- **Settings live in menus.** No checkbox or radio directly in a dock zone, 
  a switch is a setting, and belongs in a popover or in Settings. Inside a
  `.dock-menu` they are fine (that is what the View menu is for).
- **Utilities in a fixed order, last.** Within `.dock-actions`, after the
  primary: refresh, help, more: never help before refresh, never the kebab
  before either. A utility is recognised by its id (`*-refresh`,
  `*-help-toggle`) or class (`dock-more`).
- **The page head, quiet facts, a quiet field, one trailing group** (INBOX
  621, the owner: the bars "dont feel professional or modern and more
  demo/vibe coded"). The one filled action closes the row: it is the last
  control of `.dock-actions`, after every utility. Icon-only buttons stand
  in that zone only, after its worded ghosts, so they read as one trailing
  group rather than icons scattered among the zones. Every search box in a
  dock is a `.search-field.dock-search` with its leading
  `.search-field-icon`. And the stylesheet draws no hairline between zones
  (the title boxed off by one, every zone fenced by another) and no edge or
  fill round a count (`.dock-chip` is quiet muted text).
- **No text-only segmented controls in a zone.** A `.seg`/`.segmented-control`
  in a dock zone must carry an icon per option or be inside a menu; the plan
  keeps segments for *view* and gives them icons. A segment's own cells are
  not counted as primaries: the fill on a segment *is* its selected state,
  not a call to action, so "one primary" is about the buttons beside it.

Like the other frontend lints this cannot see the DOM; `scratchpad/ui-sweeps/
docks.js` measures the same docks against a running app (one height per
dock, ≤ 7 visible controls per row). Docks join the lint by carrying
`data-dock-name="<name>"`, so a surface that has not been brought onto the grammar
yet is not failed for it, the ratchet is the count of docks that carry it.
"""

from __future__ import annotations

import re
from html.parser import HTMLParser
from pathlib import Path

import pytest
from tests._app_js import frontend_text

ROOT = Path(__file__).resolve().parents[1]
INDEX = ROOT / "frontend" / "index.html"

ZONES = ["dock-identity", "dock-find", "dock-arrange", "dock-actions"]

#: Docks that have been brought onto the grammar. Add a name here when a
#: surface lands; the test below fails if the markup and this list disagree,
#: so the ratchet cannot silently loosen.
ON_THE_GRAMMAR = {
    # The live captions dock, floated over any surface (captions.js, Brief 82).
    "captions",
    # A recording that outlives its dialog (meetings.js, UI_MODERNISATION V1).
    "recording",
    "chat",
    "graph",
    "library",
    "library-boards",
    "library-contents",
    "library-docs",
    "library-links",
    "library-media",
    #: Library, Recordings (WORLD_CLASS_PLAN 28.5 row 6, Brief 80).
    "library-recordings",
    "library-skills",
    #: The quick sketch pad's bar left the markup in the 10-26 rebuild:
    #: sketch-pad.js builds it, and test_sketch_pad.py plus the pad sweep
    #: check it.
    "notes",
    "timeline",
    "reminders",
    # The Notes tab's Writing room sub-tab (WORLD_CLASS_PLAN D16): its head
    # was an h2 and a lone round '?' with no control bar at all, and the two
    # filled buttons it carried were one per column.
    "writing-room",
    # The one dock that is not a tab head: the Settings screen's Logs console,
    # reported as the last control row still built by hand. It lives inside the
    # settings modal, which is why `scratchpad/ui-sweeps/docks.js` (which walks
    # the seven tabs) does not see it and `logsdock.js` measures it instead.
    "settings-logs",
    # Every Settings pane's head (INBOX 599): the panes written in the markup
    # with a '?'; the rest get the same dock from `ensureSettingsPaneTitle`,
    # and the section index goes inside it (`settingsIndexBuild`).
    "settings-account",
    "settings-learned",
    "settings-memory",
    # Personas, in the markup since its dock carries New persona.
    "settings-personas",
    "settings-privacy",
    "settings-skills",
    "settings-templates",
    "settings-websearch",
    # The Dashboard's one row between the hero and the widgets (INBOX 436):
    # the search doorway, New note and the menu that holds everything else.
    "dashboard",
    # The Notes tab's Questions view (WORLD_CLASS_PLAN I3, row 7): its gate
    # names this lint.
    "questions",
    # The OCR workspace's tools (INBOX 717): View, then Read, one row that
    # folds what does not fit into its own menu, the first dock in a dialog.
    "ocr",
}


class _Segment:
    """One segmented control sitting directly in a dock zone."""

    def __init__(self, name: str, ident: str):
        self.dock = name
        self.id = ident or "(no id)"
        self.options = 0
        self.with_icon = 0


class _Dock:
    def __init__(self, name: str):
        self.name = name
        self.zones: list[str] = []
        self.filled: list[str] = []
        self.loose_switches: list[str] = []
        self.utilities: list[str] = []
        self.segments: list[_Segment] = []
        #: The zones' direct children in order, as (zone, kind, id): kind is
        #: "filled", "icon", "worded" or "other".
        self.run: list[tuple[str, str, str]] = []
        #: Every search box: [id, wrapped in `.search-field.dock-search`,
        #: that wrapper holds a `.search-field-icon`, the wrapper's frame id].
        self.searches: list[list] = []


def _kind(tag: str, classes: set[str]) -> str:
    """What a control in a zone's run is: the filled action, an icon, a word."""
    # A split button (DESIGN.md: a filled action with a default and a choice,
    # the OCR workspace's Read) is one control: the default press and its
    # caret are two halves of the one filled action.
    if "split-button" in classes:
        return "filled"
    if tag == "details" and "dock-menu" in classes:
        if "dock-more" in classes:
            return "icon"
        # A filled action with a choice inside it (the Boards and maps New):
        # its summary is `.dock-menu-primary` and the details is the flip menu.
        return "filled" if "dock-menu-flip" in classes else "worded"
    if "dock-more" in classes:
        return "icon"
    if tag != "button":
        return "other"
    if "icon-only" in classes:
        return "icon"
    if classes & {"ghost", "library-chip", "linklike"}:
        return "worded"
    return "filled"


class _Parser(HTMLParser):
    """A small stack walker: enough to know, for each element, which dock,
    which zone and whether a `.dock-menu` encloses it."""

    def __init__(self) -> None:
        super().__init__()
        self.stack: list[dict] = []
        self.docks: list[_Dock] = []
        self.void = {"input", "img", "br", "hr", "meta", "link"}
        #: The frames (by `id()`) that hold a `.search-field-icon`.
        self.icons_in: set[int] = set()

    def _classes(self, attrs) -> set[str]:
        return set((dict(attrs).get("class") or "").split())

    def handle_starttag(self, tag, attrs):
        a = dict(attrs)
        classes = self._classes(attrs)
        frame = {"tag": tag, "classes": classes, "id": a.get("id") or "", "dock": None}
        if "data-dock-name" in a:
            dock = _Dock(a["data-dock-name"])
            self.docks.append(dock)
            frame["dock"] = dock
        self.stack.append(frame)
        dock = next((f["dock"] for f in reversed(self.stack) if f["dock"]), None)
        if dock is None:
            if tag not in self.void:
                pass
            else:
                self.stack.pop()
            return
        in_menu = any("dock-menu" in f["classes"] for f in self.stack[:-1])
        zone = next((z for z in ZONES if z in classes), None)
        if zone:
            dock.zones.append(zone)
        current_zone = next(
            (z for f in reversed(self.stack) for z in ZONES if z in f["classes"]), None
        )
        # Whether this element is a *direct* child of its zone, which is the
        # stylesheet's own test for "in the control run" (`.dock > * > button`).
        parent = self.stack[-2] if len(self.stack) > 1 else None
        in_run = bool(parent) and any(z in parent["classes"] for z in ZONES)
        # A cell of a segmented control is not a primary, and this had to be
        # said explicitly: `.seg button` is transparent by design (the fill is
        # the *selected* state), so a segment carries neither `ghost` nor, once
        # its options have words beside their icons, `icon-only`. Counting its
        # cells as filled buttons failed Contents for having four ways to group
        # an index, which is not the "two answers to what this row is for"
        # defect this test is here to catch. The docstring's own segment rule
        # is now a test as well, one line below.
        in_seg = any(
            "seg" in f["classes"] or "segmented-control" in f["classes"]
            for f in self.stack[:-1]
        )
        if not in_menu and current_zone:
            if "split-button" in classes and in_run:
                dock.filled.append(a.get("id") or "(no id)")
            if (
                tag == "button"
                and in_run
                and not in_seg
                and "ghost" not in classes
                and "icon-only" not in classes
                # And a chip is not a primary either, for the same reason a
                # segment's cell is not: `.library-chip` is the app's own
                # filter-chip recipe, a pill that carries a filter you can
                # take off, and it carries neither `ghost` nor `icon-only`
                # because its resting paint is its own. The Timeline's band
                # clear ("Show: Work") is one, and counting it failed that
                # dock for having two filled buttons when it has one.
                and "library-chip" not in classes
            ):
                dock.filled.append(a.get("id") or "(no id)")
            if tag == "input" and a.get("type") in ("checkbox", "radio"):
                dock.loose_switches.append(a.get("id") or a.get("name") or "(no id)")
            if ("seg" in classes or "segmented-control" in classes) and tag != "summary":
                dock.segments.append(_Segment(dock.name, a.get("id") or ""))
            if tag == "button" and in_seg and dock.segments:
                dock.segments[-1].options += 1
            if tag == "i" and in_seg and dock.segments:
                if any(c == "ph" or c.startswith("ph-") for c in classes):
                    dock.segments[-1].with_icon += 1
        if in_run and not in_menu:
            # A hidden file input and a help popover's body are not controls
            # in the row, and nor is a button kept only for the keyboard and a
            # screen reader (Chat's Export and Delete, which its menu shows).
            skip = (tag == "input" and a.get("type") == "file") or classes & {"help-body", "visually-hidden"}
            if not skip:
                dock.run.append((current_zone or "", _kind(tag, classes), a.get("id") or tag))
        if tag == "input" and a.get("type") == "search" and not in_menu:
            wrapper = parent["classes"] if parent else set()
            dock.searches.append(
                [a.get("id") or "(no id)", {"search-field", "dock-search"} <= wrapper, False, id(parent)]
            )
        if tag == "i" and "search-field-icon" in classes and parent:
            self.icons_in.add(id(parent))
        if current_zone == "dock-actions" and not in_menu:
            ident = a.get("id") or ""
            if ident.endswith("-refresh"):
                dock.utilities.append("refresh")
            elif ident.endswith("-help-toggle"):
                dock.utilities.append("help")
            elif "dock-more" in classes:
                dock.utilities.append("more")
        if tag in self.void:
            self.stack.pop()

    def handle_endtag(self, tag):
        for i in range(len(self.stack) - 1, -1, -1):
            if self.stack[i]["tag"] == tag:
                del self.stack[i:]
                return


def _docks() -> list[_Dock]:
    text = re.sub(r"<!--.*?-->", "", INDEX.read_text(encoding="utf-8"), flags=re.S)
    parser = _Parser()
    parser.feed(text)
    for dock in parser.docks:
        for search in dock.searches:
            search[2] = search[3] in parser.icons_in
    return parser.docks


def test_every_dock_on_the_grammar_is_marked_and_vice_versa():
    names = {d.name for d in _docks()}
    assert names == ON_THE_GRAMMAR, (
        f"docks in the markup: {sorted(names)}; docks this lint expects: "
        f"{sorted(ON_THE_GRAMMAR)}: update ON_THE_GRAMMAR when a surface lands"
    )


@pytest.mark.parametrize("dock", _docks(), ids=lambda d: d.name)
def test_zones_are_in_order_and_unique(dock):
    assert len(dock.zones) == len(set(dock.zones)), f"{dock.name}: a zone appears twice"
    order = [ZONES.index(z) for z in dock.zones]
    assert order == sorted(order), f"{dock.name}: zones out of order: {dock.zones}"


@pytest.mark.parametrize("dock", _docks(), ids=lambda d: d.name)
def test_one_primary_action(dock):
    assert len(dock.filled) <= 1, f"{dock.name}: more than one filled button: {dock.filled}"


@pytest.mark.parametrize("dock", _docks(), ids=lambda d: d.name)
def test_switches_live_in_menus(dock):
    assert not dock.loose_switches, (
        f"{dock.name}: a checkbox/radio sits directly in a dock zone: {dock.loose_switches}"
    )


def _segments():
    return [s for d in _docks() for s in d.segments]


@pytest.mark.parametrize("seg", _segments(), ids=lambda s: f"{s.dock}:{s.id}")
def test_segments_in_a_zone_carry_an_icon_per_option(seg):
    """The docstring's segment rule, which was described and never asserted.

    A segmented control in a dock means *view*, and the plan gives it icons so
    that four ways of drawing one list read as one control rather than as four
    words someone left in the row. Words may sit beside the icons; what is
    refused is an option with no icon at all.
    """
    if not seg.options:
        # A well that is empty in the markup is one whose options are built at
        # runtime, because how many there are, or what they are called, is not
        # known until something has been fetched (the Timeline's kind filter is
        # built from `TIMELINE_KINDS` with a count per kind). A static lint
        # cannot see those; what it can insist on is that something builds
        # them, and the runtime shape is gated by a sweep instead:
        # `scratchpad/ui-sweeps/timelinedock.js` asserts one row, the icons,
        # the `aria-pressed` per segment and the 44px target at 390.
        #: app.js and timeline.js joined: the Timeline tab, whose kind filter
        #: is the case above, was split out of app.js into timeline.js.
        app = "\n".join(
            frontend_text(name)
            for name in ("app.js", "timeline.js")
        )
        assert seg.id and f'"{seg.id}"' in app, (
            f"{seg.dock}:{seg.id}: a segment with no options and nothing in "
            "app.js or timeline.js that builds them"
        )
        return
    assert seg.with_icon >= seg.options, (
        f"{seg.dock}:{seg.id}: {seg.options} options but only {seg.with_icon} "
        "carry an icon; a segment in a dock zone gives every option one"
    )


@pytest.mark.parametrize("dock", _docks(), ids=lambda d: d.name)
def test_utilities_keep_their_order(dock):
    expected = ["refresh", "help", "more"]
    seen = [u for u in expected if u in dock.utilities]
    assert dock.utilities == seen, (
        f"{dock.name}: utilities are {dock.utilities}; the order is refresh · help · more"
    )


@pytest.mark.parametrize("dock", _docks(), ids=lambda d: d.name)
def test_the_filled_action_closes_the_row(dock):
    """INBOX 621: "the filled primary sits mid-row followed by more icons".

    The one filled action is the last control of the actions zone, after
    refresh, help and the overflow, so the row ends on what it is for.
    """
    filled = [i for i, (_, kind, _) in enumerate(dock.run) if kind == "filled"]
    if not filled:
        return
    zone, _, ident = dock.run[filled[-1]]
    assert zone == "dock-actions", f"{dock.name}: the filled {ident} is in {zone}, not the actions"
    assert filled[-1] == len(dock.run) - 1, (
        f"{dock.name}: {ident} is followed by {[r[2] for r in dock.run[filled[-1] + 1:]]}; "
        "the filled action is the last control in the row"
    )


@pytest.mark.parametrize("dock", _docks(), ids=lambda d: d.name)
def test_icon_buttons_are_one_trailing_group(dock):
    """INBOX 621: "icon buttons are scattered among dividers".

    Icon-only buttons (and the overflow) stand in the actions zone, after any
    worded ghost there: one trailing run, then the filled action.
    """
    stray = [ident for zone, kind, ident in dock.run if kind == "icon" and zone != "dock-actions"]
    assert not stray, f"{dock.name}: icon buttons outside the trailing group: {stray}"
    actions = [(kind, ident) for zone, kind, ident in dock.run if zone == "dock-actions"]
    first_icon = next((i for i, (kind, _) in enumerate(actions) if kind == "icon"), None)
    if first_icon is None:
        return
    after = [ident for kind, ident in actions[first_icon:] if kind in ("worded", "other")]
    assert not after, f"{dock.name}: {after} breaks the icon group; worded actions come before it"


@pytest.mark.parametrize("dock", _docks(), ids=lambda d: d.name)
def test_every_search_is_a_quiet_field_with_its_icon(dock):
    """INBOX 621: "the search fields are heavy and bordered"."""
    for ident, wrapped, icon, _ in dock.searches:
        assert wrapped, f"{dock.name}: #{ident} is not inside a .search-field.dock-search"
        assert icon, f"{dock.name}: #{ident}'s field has no leading .search-field-icon"


CSS_DIR = ROOT / "frontend" / "css"


def _rules(selector_pattern: str) -> list[str]:
    """The declaration block of every rule whose selector matches, comments out."""
    text = "\n".join(p.read_text(encoding="utf-8") for p in sorted(CSS_DIR.glob("*.css")))
    text = re.sub(r"/\*.*?\*/", "", text, flags=re.S)
    return [
        m.group(2)
        for m in re.finditer(r"([^{}]+)\{([^{}]*)\}", text)
        if re.search(selector_pattern, m.group(1))
    ]


def test_no_hairline_parts_the_zones():
    """INBOX 621: "the title is boxed off by a divider". The zones are parted
    by the dock's gap; no rule draws a line before or after a zone."""
    for body in _rules(r"\.dock\s*>\s*(\*|\.dock-(identity|find|arrange|actions|group))"):
        assert not re.search(r"border-(left|right|inline-start|inline-end)\s*:\s*1px", body), body


def test_a_count_is_quiet_text_not_a_pill():
    """INBOX 621: "the counts sit in bordered pills"."""
    bodies = _rules(r"(^|[\s,])\.dock-chip\s*$")
    assert bodies, "the .dock-chip rule moved"
    for body in bodies:
        assert not re.search(r"\bborder\s*:\s*1px", body), body
        assert "background" not in body, body


def test_the_dock_search_field_has_no_edge_at_rest():
    """A subtle fill and the focus ring; the edge arrives with focus only."""
    bodies = _rules(r"\.dock-search\s*$")
    assert bodies, "the .dock-search rule is missing"
    assert any(re.search(r"border-color\s*:\s*transparent", b) for b in bodies)
