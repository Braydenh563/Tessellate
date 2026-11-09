"""Audit 1031 row 21: surfaces as templates, stamped on first need.

A surface the page shows only on request sits in an inert
`<template data-surface="NAME">` inside its live root; `surfaceBuild(name)`
(settings-body.js) puts it in the page once, at the open or at the first `$`
of one of its ids (`surfaceFind`), and `onSurface(name, run)` runs wiring that
needs its elements once they exist. The markup stays in index.html, so ids,
help anchors and chord titles are read where they always were. This holds the
shape per surface, and the rule that keeps a template cheap: nothing that runs
at load wires its elements except through `onSurface`.
"""

from __future__ import annotations

import json
import re
import shutil
import subprocess
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
FRONTEND = ROOT / "frontend"
JS = FRONTEND / "js"
INDEX = (FRONTEND / "index.html").read_text(encoding="utf-8")
needs_node = pytest.mark.skipif(not shutil.which("node"), reason="needs node")

#: surface -> (its live root's id, globs of the files whose load-time wiring may
#: reach it, the function(s) that open it and must build it first, ids it must hold).
SURFACES = {
    "board": (
        "wb-canvas-view",
        ("whiteboard*.js",),
        ("wbShowCanvasView", "initWhiteboard"),
        ("whiteboard-container", "wb-tools-panel", "wb-format", "wb-outline-tree", "wb-back-to-boards"),
    ),    "ocr": ("ocr-workspace", ("library.js",), ("openOcrWorkspace",), ("ocr-close", "ocr-stage", "ocr-rail", "ocr-page-pane")),
    "shortcuts": (
        "shortcuts-overlay",
        ("reveal-targets.js", "settings-wiring.js"),
        ("openShortcuts",),
        ("shortcuts-card", "shortcuts-close", "shortcut-list", "shortcut-list-whiteboard"),
    ),
}


def _template(name: str) -> tuple[str, str]:
    """(the markup just before the template, the template's body)."""
    m = re.search(rf'<template data-surface="{name}"[^>]*>(.*?)</template>', INDEX, re.S)
    assert m, f"no <template data-surface=\"{name}\"> in index.html"
    return INDEX[: m.start()], m.group(1)


def _ids(markup: str) -> set[str]:
    return set(re.findall(r'\bid="([^"]+)"', markup))


def _files(globs: tuple[str, ...]) -> list[Path]:
    return sorted({p for g in globs for p in JS.glob(g)})


def _src(name: str) -> str:
    return (JS / name).read_text(encoding="utf-8")


@pytest.mark.parametrize("name", SURFACES)
def test_the_surface_sits_in_one_template_inside_its_live_root(name):
    root, _, _, wanted = SURFACES[name]
    before, body = _template(name)
    # The root stays live (checks of "is it open" never build it); the template
    # is its first child, comments aside.
    opening = re.search(rf'<div id="{root}"[^>]*>\s*(?:<!--.*?-->\s*)*$', before, re.S)
    assert opening, f"the {name} template is not the first child of #{root}"
    ids = _ids(body)
    assert root not in ids
    missing = [i for i in wanted if i not in ids]
    assert not missing, f"{missing} are not in the {name} template"
    assert INDEX.count(f'data-surface="{name}"') == 1


def test_dollar_falls_back_to_every_surface():
    assert re.search(r"^const \$ = \(id\) => document\.getElementById\(id\) \|\| surfaceFind\(id\);$", _src("app.js"), re.M)


@pytest.mark.parametrize("name", SURFACES)
def test_opening_the_surface_builds_it_before_reading_it(name):
    _, globs, openers, _ = SURFACES[name]
    text = "".join(p.read_text(encoding="utf-8") for p in _files(globs))
    for opener in openers:
        m = re.search(rf"^(?:async )?function {opener}\([^)]*\) \{{\n(.*?)^\}}", text, re.S | re.M)
        assert m, f"{opener} not found"
        body = m.group(1)
        call = f'surfaceBuild("{name}");'
        assert call in body, f"{opener} does not build the {name} surface"
        reads = [i for i in (body.find('$("'), body.find("getElementById(")) if i != -1]
        assert not reads or body.index(call) < min(reads), f"{opener} reads an element before it builds the {name} surface"


def _load_time_blocks(text: str):
    """Top-level statements that run when the file loads: `onDomReady(...)`
    blocks, bare `document.getElementById(...)` and `$(...)` lines and IIFEs, with their text."""
    lines = text.split("\n")
    i = 0
    while i < len(lines):
        line = lines[i]
        if line.startswith(("onDomReady(", "document.getElementById(", "$(", "onSurface(", "(function", "(() =>")):
            # The statement ends at the first unindented line closing it.
            j = i
            while j < len(lines) - 1 and not (
                re.search(r"\);\s*$", lines[j]) and (j == i or not lines[j].startswith((" ", "\t")))
            ):
                j += 1
            yield i + 1, line, "\n".join(lines[i : j + 1])
            i = j + 1
        else:
            i += 1


@pytest.mark.parametrize("name", SURFACES)
def test_load_time_wiring_of_the_surface_waits_for_it(name):
    _, globs, _, _ = SURFACES[name]
    _, body = _template(name)
    ids = _ids(body)
    found = []
    for path in _files(globs):
        for number, head, block in _load_time_blocks(path.read_text(encoding="utf-8")):
            named = sorted(i for i in re.findall(r"""["'#]([\w-]+)["')\s]""", block) if i in ids)
            if named and not head.startswith(f'onSurface("{name}"'):
                found.append(f"{path.name}:{number} {named[:3]}")
    assert not found, f"wiring at load reaches the {name} template before it is built: " + "; ".join(found)


def _run(body: str) -> dict:
    parts = [
        "const log = []; const live = new Set();",
        "function tpl(name, ids) { const host = { name }; return { dataset: { surface: name }, parentNode: host,"
        " content: { getElementById: (id) => (ids.includes(id) ? { id } : null) },"
        " replaceWith() { ids.forEach((i) => live.add(i)); log.push('stamp ' + name); } }; }",
        "const tpls = [tpl('settings', ['sync-now']), tpl('board', ['whiteboard-container'])];",
        "const document = { querySelectorAll: () => tpls, getElementById: (id) => (live.has(id) ? { id, live: 1 } : null) };",
        "const window = { initHelpToggles: (h) => log.push('help ' + h.name) };",
        _src("settings-body.js"),
        body,
    ]
    out = subprocess.run(["node", "-e", "\n".join(parts)], capture_output=True, text=True, timeout=30)
    assert out.returncode == 0, out.stderr
    return json.loads(out.stdout)


@needs_node
def test_build_is_once_per_surface_find_builds_only_the_one_asked_and_the_queue_runs_after():
    result = _run(
        """
        const miss = surfaceFind('no-such-id');
        onSurface('board', () => log.push('board wiring'));
        const found = surfaceFind('whiteboard-container');
        const again = surfaceBuild('board');
        onSurface('board', () => log.push('board now'));
        const unknown = surfaceBuild('nothing');
        console.log(JSON.stringify({ miss, found, again, unknown, log }));
        """
    )
    assert result["miss"] is None
    assert result["found"]["live"] == 1, "the element, from the page, after the build"
    assert result["again"] is False and result["unknown"] is False
    assert result["log"] == ["stamp board", "help board", "board wiring", "board now"], result["log"]
