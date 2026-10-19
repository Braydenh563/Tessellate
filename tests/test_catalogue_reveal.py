"""Every catalogue row lands on the thing it names.

Reported (the owner, 2026-09-24): "make sure that the tools and features panel
options, as well as the command palatte and find anything search actually show
what they are. like I clicked on the "suggested links" option in the tools and
features panel and all it did was take me to the graph page, it didnt actually
open the menu option for suggested links in the graph like it should have."

Measured before the fix (a read of every closure): of the 110 written rows in
"Tools and features", 50 did no more than switch tab (or open a parent view)
while naming one control on it, 11 more opened a Settings pane at its top while
naming one setting in it, every one of the AI tool rows built from
`/chat/tools` opened that pane at its top too, and the palette's two board rows
did nothing at all unless a board was already open. The cause was the shape of the rows: each was a hand-written closure, and
`switchTab("graph")` is the shortest closure that looks like it works.

So a row no longer carries a closure. It *declares* where it goes, one of:

* `tab: "graph"`: the row names a tab and the tab is the whole answer
  ("Graph view", "Go to Notes").
* `reveal: "graph-suggest"`: the row names something on a tab, in a menu or
  behind a dialog; `revealFeature` (app.js) switches tab, waits for the lazy
  bundle, opens the menu, panel or dialog, and rings the control with the
  app's own jump-to highlight. The targets live in one table,
  `REVEAL_TARGETS`, and `settings:<section>` names a Settings pane.
* `act: fn`: the row is a command that changes something where you already
  are (zoom, the theme, lock, a download). It has no place to land, and an
  act may not switch tab: a row that goes somewhere is a reveal.

What this file checks, statically: every row declares exactly one of the
three; every tab exists; every reveal key exists; every target names an
element that is in index.html, or a selector plus the named function that
builds it at runtime. `scratchpad/ui-sweeps/deeplinks.js` is the other half:
it runs every row in a browser and checks the named control is on screen.
"""

from __future__ import annotations

import re
from pathlib import Path
from tests._app_js import frontend_text

FRONTEND = Path(__file__).resolve().parents[1] / "frontend"
INDEX = FRONTEND / "index.html"

SCRIPTS = (
    "app.js",
    "whiteboard.js",
    "graph.js",
    "graph-canvas.js",
    "documents.js",
    "library.js",
    "dashboard.js",
    "settings.js",
    "manual.js",
    "editor.js",
    "timeline.js",
    "palette.js",
    "avatars.js",
    "atlas.js",
    #: New meeting and the meeting sheet (INBOX 644), a lazy bundle.
    "meetings.js",
    #: Tidy (INBOX 691), a lazy bundle.
    "tidy.js",
)


def _read(name: str) -> str:
    return frontend_text(name)


def _strip_comments(text: str) -> str:
    # Line comments first: a `/*` inside a `//` line must not open a block
    # (test_feature_catalog.py's docstring has the incident).
    text = re.sub(r"^\s*//.*$", "", text, flags=re.M)
    return re.sub(r"/\*.*?\*/", "", text, flags=re.S)


def _match_brace(source: str, start: int) -> int:
    """Index of the brace closing the one at `start`, skipping strings."""
    depth = 0
    index = start
    quote = ""
    while index < len(source):
        char = source[index]
        if quote:
            if char == "\\":
                index += 2
                continue
            if char == quote:
                quote = ""
        elif char in "\"'`":
            quote = char
        elif char == "{":
            depth += 1
        elif char == "}":
            depth -= 1
            if depth == 0:
                return index
        index += 1
    raise AssertionError("unbalanced braces")


def _body(source: str, signature: str) -> str:
    start = source.index(signature)
    brace = source.index("{", start + len(signature) - 1)
    return source[start : _match_brace(source, brace) + 1]


def _objects(body: str, key: str) -> list[tuple[str, str]]:
    """Every `{ key: "…", … }` object literal in `body`, as (name, text)."""
    out = []
    for match in re.finditer(r"\{\s*" + key + r':\s*"([^"]+)"', body):
        end = _match_brace(body, match.start())
        out.append((match.group(1), body[match.start() : end + 1]))
    return out


def _top_level_keys(obj: str) -> set[str]:
    """The keys an object literal sets at its own depth, not inside a closure."""
    keys = set()
    depth = 0
    quote = ""
    index = 0
    while index < len(obj):
        char = obj[index]
        if quote:
            if char == "\\":
                index += 2
                continue
            if char == quote:
                quote = ""
        elif char in "\"'`":
            quote = char
        elif char in "{([":
            depth += 1
        elif char in "})]":
            depth -= 1
        elif depth == 1:
            match = re.match(r"([A-Za-z_]\w*)\s*:", obj[index:])
            if match and (index == 0 or not re.match(r"[\w$.]", obj[index - 1])):
                keys.add(match.group(1))
                index += len(match.group(0))
                continue
        index += 1
    return keys


def _feature_rows() -> list[tuple[str, str]]:
    body = _body(_strip_comments(_read("app-features.js")), "function featureCatalog() {")
    return _objects(body, "name")


def _palette_rows() -> list[tuple[str, str]]:
    body = _body(_strip_comments(_read("app.js")), "function paletteCommands() {")
    rows = _objects(body, "label")
    #: The four filter rows are built from a table by one `.map`, so the
    #: object literal the map returns is the row they all share.
    for match in re.finditer(r"\(\{\s*label,\s*(\w+):", body):
        end = _match_brace(body, match.start() + 1)
        rows.append(("(mapped filter rows)", body[match.start() + 1 : end + 1]))
    return rows


def _all_rows():
    for name, obj in _feature_rows():
        yield "Tools and features", name, obj
    for name, obj in _palette_rows():
        yield "palette", name, obj


def _list_literal(script: str, name: str) -> set[str]:
    match = re.search(rf"\b{name}\s*=\s*\[(.*?)\]", _read(script), flags=re.S)
    assert match, f"{name} is not declared in {script}"
    return set(re.findall(r'"([^"]+)"', match.group(1)))


def _markup_ids() -> set[str]:
    markup = re.sub(r"<!--.*?-->", "", INDEX.read_text(encoding="utf-8"), flags=re.S)
    return set(re.findall(r'\bid="([^"]+)"', markup))


def _declared_functions() -> set[str]:
    names: set[str] = set()
    for script in SCRIPTS:
        source = _strip_comments(_read(script))
        names |= set(re.findall(r"\bfunction\s+([A-Za-z_$][\w$]*)\s*\(", source))
    return names


def _targets() -> dict[str, str]:
    """`REVEAL_TARGETS`, key to object text."""
    source = _strip_comments(_read("app.js"))
    body = _body(source, "const REVEAL_TARGETS = {")
    out = {}
    at = body.index("{") + 1
    entry = re.compile(r'\s*"?([\w:-]+)"?:\s*\{')
    while True:
        match = entry.match(body, at)
        if not match:
            break
        start = match.end() - 1
        end = _match_brace(body, start)
        out[match.group(1)] = body[start : end + 1]
        at = end + 1
        #: The comma after an entry, and any blank line before the next.
        comma = re.match(r"\s*,", body[at:])
        if comma:
            at += comma.end()
    return out


def test_the_tables_were_found():
    """A parser that silently finds nothing passes every check below."""
    assert len(_feature_rows()) > 100, "featureCatalog rows were not found"
    assert len(_palette_rows()) > 50, "paletteCommands rows were not found"
    assert len(_targets()) > 60, "REVEAL_TARGETS entries were not found"


def test_every_row_declares_where_it_goes():
    """One of tab, reveal or act, exactly; never a bare closure."""
    wrong = []
    for where, name, obj in _all_rows():
        keys = _top_level_keys(obj)
        declared = keys & {"tab", "reveal", "act"}
        if len(declared) != 1 or "run" in keys:
            wrong.append(f"{where}: {name!r} declares {sorted(declared) or 'nothing'}"
                         + (" and a run" if "run" in keys else ""))
    assert not wrong, (
        "a catalogue row declares where it goes (tab, reveal or act), not a "
        "closure: " + "; ".join(wrong)
    )


def test_an_act_never_switches_tab():
    """A row that goes somewhere is a reveal, so it lands on the feature."""
    wrong = [
        f"{where}: {name!r}"
        for where, name, obj in _all_rows()
        if "act" in _top_level_keys(obj) and re.search(r"switchTab|showNotesSection", obj)
    ]
    assert not wrong, f"these acts switch tab; make them reveals: {wrong}"


def test_every_tab_exists():
    tabs = _list_literal("app.js", "TABS")
    for where, name, obj in _all_rows():
        for tab in re.findall(r'\btab:\s*"([^"]+)"', obj):
            assert tab in tabs, f"{where}: {name!r} names tab {tab!r}, not in TABS"
    for key, obj in _targets().items():
        for tab in re.findall(r'\btab:\s*"([^"]+)"', obj):
            assert tab in tabs, f"REVEAL_TARGETS[{key!r}] names tab {tab!r}"


def test_every_reveal_names_a_target():
    targets = _targets()
    sections = _list_literal("settings.js", "SETTINGS_SECTIONS")
    ids = _markup_ids()
    for where, name, obj in _all_rows():
        for key in re.findall(r'\breveal:\s*"([^"]+)"', obj):
            if key.startswith("settings:"):
                section = key.split(":", 1)[1]
                assert section in sections, f"{where}: {name!r} names pane {section!r}"
                assert f"settings-{section}" in ids, f"no #settings-{section} in index.html"
                continue
            assert key in targets, f"{where}: {name!r} reveals {key!r}, not in REVEAL_TARGETS"


def test_every_target_names_a_control_that_exists():
    """An id in index.html, or a selector plus the function that builds it."""
    ids = _markup_ids()
    functions = _declared_functions()
    sections = _list_literal("settings.js", "SETTINGS_SECTIONS")
    wrong = []
    for key, obj in _targets().items():
        keys = _top_level_keys(obj)
        element = re.search(r'\bel:\s*"([^"]+)"', obj)
        if element:
            if element.group(1) not in ids:
                wrong.append(f"{key}: #{element.group(1)} is in no element in index.html")
        elif "sel" in keys:
            built = re.search(r'\bbuilt:\s*"([^"]+)"', obj)
            if not built:
                wrong.append(f"{key}: a selector needs `built:` naming what makes it")
            elif built.group(1) not in functions:
                wrong.append(f"{key}: built by {built.group(1)!r}, defined nowhere")
        else:
            wrong.append(f"{key}: names no control (el, or sel with built)")
        for pane in re.findall(r'\bsettings:\s*"([^"]+)"', obj):
            if pane not in sections:
                wrong.append(f"{key}: settings pane {pane!r} is not in SETTINGS_SECTIONS")
        for fallback in re.findall(r'\bfallback:\s*"([^"]+)"', obj):
            if fallback not in ids:
                wrong.append(f"{key}: fallback #{fallback} is in no element in index.html")
    assert not wrong, "; ".join(wrong)


def test_every_target_is_used():
    """A target no row names is dead weight that drifts."""
    used = set()
    for _where, _name, obj in _all_rows():
        used |= set(re.findall(r'\breveal:\s*"([^"]+)"', obj))
    #: The AI tool rows are built from the backend's own list at open time
    #: (`renderFeatures`), so their one target is named there.
    used |= set(re.findall(r'reveal:\s*"([^"]+)"', _strip_comments(_read("dashboard.js"))))
    unused = sorted(set(_targets()) - used)
    assert not unused, f"REVEAL_TARGETS entries no row reveals: {unused}"
