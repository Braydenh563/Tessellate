"""The `library` bundle (documents, the list) no longer carries the board code (audit-1028 D22).

A first document open fetched nine whiteboard files and d3 it never ran, about
1.5 MB raw. They are the `boards` bundle now: the `library` files first (the board
code calls into documents), then d3 and the whiteboard files. The price is that a
call from a library file into board code meets code that may be absent. Each such
call is one of three things, and this file reads every one:

- a stand-in of the `boards` group (lazy-entries.js) that fetches the bundle and
  then calls the real function, for a call whose answer nobody reads;
- a `typeof name === "function"` or `window.name` guard, for a call whose answer is
  read (it means "no board is open", which is true while the code is absent);
- an `ensureModule("boards")` just before it.

A call that is none of them is a silent dead button, which is what the 2026-11-11
sweep (`docs/roadmap/agent-remaining/dec-1111-d2.md`) drove path by path.
"""

from __future__ import annotations

import re
import sys

from tessellate.api.asset_strip import strip_js_comments
from tests import test_lazy_bundle_calls as bundles

FRONTEND = bundles.FRONTEND
JS = FRONTEND / "js"

BOARD_FILES = [
    "whiteboard-map.js", "whiteboard-map-more.js", "whiteboard.js", "whiteboard-commands.js",
    "whiteboard-library.js", "whiteboard-templates.js", "whiteboard-format.js", "whiteboard-label.js", "whiteboard-hints.js", "whiteboard-options.js", "whiteboard-export-more.js", "whiteboard-keys.js", "whiteboard-workspace.js", "whiteboard-layers-more.js", "whiteboard-draw-more.js", "whiteboard-arrange-more.js", "whiteboard-layouts-more.js", "whiteboard-structure-more.js", "whiteboard-shape-more.js", "whiteboard-shapes-js.js", "whiteboard-library-more.js",
    "whiteboard-interchange.js", "whiteboard-history.js",
]

#: The window before a call in which an `ensureModule("boards")` counts as its door.
DOOR_LINES = 12


def _boards_only() -> list[str]:
    lazy = bundles._lazy_files()
    return [f for f in lazy["boards"] if f not in lazy["library"]]


def _code(name: str) -> str:
    return strip_js_comments((JS / name).read_text(encoding="utf-8"))


def _stand_ins() -> set[str]:
    return bundles._entry_points()["boards"]


def test_boards_is_the_library_then_the_board_files():
    lazy = bundles._lazy_files()
    library, boards = lazy["library"], lazy["boards"]
    assert boards[: len(library)] == library, "the board files load after every library file, never before"
    assert _boards_only() == BOARD_FILES
    entries = (JS / "lazy-entries.js").read_text(encoding="utf-8")
    block = re.search(r"\n  boards: \[(.*?)\],\n", entries, re.S).group(1)
    assert "...LAZY_MODULES.library" in block, "the two lists must not be able to drift apart"
    assert block.index('"/vendor/d3.v7.min.js"') < block.index('"/js/whiteboard-map.js"'), "d3 before the files that draw with it"


def test_library_carries_no_board_file_and_no_d3():
    app = (JS / "app.js").read_text(encoding="utf-8")
    library = re.search(r"\n  library: \[(.*?)\],\n", app, re.S).group(1)
    assert "whiteboard" not in library and "d3" not in library, library


def _board_names() -> set[str]:
    names: set[str] = set()
    for f in BOARD_FILES:
        funcs, _ = bundles._top_level_bindings(JS / f)
        names |= funcs
    # A name the library files also define is theirs to call (the board file only overrides nothing).
    for f in bundles._lazy_files()["library"]:
        funcs, _ = bundles._top_level_bindings(JS / f)
        names -= funcs
    return names


def _calls_without_a_door() -> list[str]:
    boards = _board_names()
    stand_ins = _stand_ins()
    pattern = re.compile(r"(?<![\w$.\-])(" + "|".join(sorted(map(re.escape, boards), key=len, reverse=True)) + r")(?![\w$\-])")
    out = []
    for f in bundles._lazy_files()["library"]:
        if not f.endswith(".js"):
            continue
        text = _code(f)
        lines = text.splitlines()
        for i, line in enumerate(lines):
            for m in pattern.finditer(line):
                name = m.group(1)
                head, tail = line[: m.start()], line[m.end():]
                if re.match(r"\s*(?:async\s+)?function\b", head) or name in stand_ins:
                    continue
                near = "\n".join(lines[max(0, i - 2) : i + 1])
                if re.search(r"typeof\s+" + re.escape(name) + r"(?![\w$])", near) or re.search(r"window\." + re.escape(name) + r"(?![\w$])", near):
                    continue  # guarded: a read answer means "no board is open" while the code is absent
                if re.search(r"\b(?:const|let|var)\s+" + re.escape(name) + r"(?![\w$])", text):
                    continue  # a local of this file that shares a board function's name
                if re.match(r"\s*[:=]", tail) and not re.match(r"\s*==", tail):
                    continue  # a property key or an assignment target, not a call
                before = "\n".join(lines[max(0, i - DOOR_LINES) : i + 1])
                if 'ensureModule("boards")' in before:
                    continue
                if re.match(r"\s*\)?\s*[,;)\]]", tail) and not tail.lstrip().startswith("("):
                    continue  # named only, not called here
                out.append(f"{f}:{i + 1}: {name}")
    return out


def test_no_library_file_calls_board_code_without_a_door():
    found = _calls_without_a_door()
    assert not found, "board code called from a library file with no stand-in, typeof guard or ensureModule(\"boards\"):\n" + "\n".join(found)


def test_the_detector_sees_a_bare_call_and_not_its_guards(monkeypatch):
    """The lint above must flag the fault it exists for: a library file calling `wbShowBoardsLanding`-shaped code bare."""
    monkeypatch.setattr(bundles, "_lazy_files", lambda: {"library": ["fake.js"], "boards": ["fake.js"]})
    monkeypatch.setattr(bundles, "_top_level_bindings", lambda p: ({"wbOnlyOnBoards"}, set()) if p.name != "fake.js" else (set(), set()))
    monkeypatch.setitem(globals(), "BOARD_FILES", ["board.js"])
    sources = {
        "bare": ("wbOnlyOnBoards(1);\n", 1),
        "typeof": ('if (typeof wbOnlyOnBoards === "function") wbOnlyOnBoards(1);\n', 0),
        "window": ("window.wbOnlyOnBoards?.(1);\n", 0),
        "door": ('await ensureModule("boards");\nwbOnlyOnBoards(1);\n', 0),
    }
    for label, (text, expected) in sources.items():
        monkeypatch.setattr(sys.modules[__name__], "_code", lambda name, t=text: t)
        assert len(_calls_without_a_door()) == expected, label


#: Every entry path P1 to P19 of dec-1111-d2.md that goes through an `ensureModule("boards")`
#: rather than a stand-in: file to the least number of doors it keeps.
DOORS = {
    "library.js": 2,          # Create menu: New board, New mind map
    "navigation.js": 1,       # the dashboard's New board action
    "reveal-targets.js": 2,   # revealBoard, revealBoardsGallery (Help "show me")
    "search.js": 2,           # Find anything: a board or a map result
    "whiteboard-library.js": 1,  # wbLoadLibrary waits before drawing tiles
    "whiteboard.js": 1,
}


def test_every_door_the_entry_paths_use_is_still_there():
    short = {}
    for name, least in DOORS.items():
        n = len(re.findall(r'ensureModule\("boards"\)', _code(name)))
        if n < least:
            short[name] = (n, least)
    assert not short, short


def test_no_site_still_asks_for_library_to_get_board_code():
    """A leftover `ensureModule("library")` ahead of a board call loads documents and no board: a dead button."""
    stale = []
    for name in ["navigation.js", "reveal-targets.js", "search.js", "whiteboard-library.js"]:
        for i, line in enumerate(_code(name).splitlines(), 1):
            if 'ensureModule("library")' in line and re.search(r"\bwb[A-Z]\w*|Board|board", "\n".join(_code(name).splitlines()[i - 1 : i + 3])):
                stale.append(f"{name}:{i}")
    assert not stale, stale
