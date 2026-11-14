"""Surfaces kept as raw text, so the dashboard's first frame does not parse them (owner log 1111, item 5).

index.html carried 14 `<template data-surface>` payloads, 693 KB of its 828 KB. A
`<template>`'s content is still parsed into an inert fragment at load: at 4x CPU the
document parse alone was 89 ms with them against 50 ms as raw text, and the first frame
(FCP) 572 ms against 408 ms with them gone. Each top-level surface is now a
`<script type="text/x-surface" data-surface="NAME">`: the parser makes no nodes for a
script's text, and `surfaceBuild` (settings-body.js) parses it on the first visit. A
surface nested in another (the board inside the Library) stays a `<template>` in its
parent's text and is named in the parent's `data-nests`.

The rest of the suite reads index.html through `tests/conftest.py`'s shared reader,
which hands it back with each such script written as the `<template>` it replaces, so
every lint still sees every id, class and landmark; this file reads the raw bytes.
"""

from __future__ import annotations

import json
import re
import shutil
import subprocess
from pathlib import Path

import pytest

from tessellate.api.asset_strip import strip_html
from tessellate.core import security

ROOT = Path(__file__).resolve().parents[1]
FRONTEND = ROOT / "frontend"
RAW = (FRONTEND / "index.html").read_bytes().decode("utf-8")
needs_node = pytest.mark.skipif(not shutil.which("node"), reason="needs node")

SCRIPTS = list(re.finditer(r'<script type="text/x-surface"([^>]*)>(.*?)</script>', RAW, re.S))


def test_every_inline_script_in_the_page_is_a_surface():
    """The page has no executable inline script (CSP, test_static_freshness): the only `<script>`
    without a `src` is a data block of this one type, which no browser runs."""
    html = re.sub(r"<!--.*?-->", "", RAW, flags=re.S)
    inline = [m.group(0) for m in re.finditer(r"<script(?![^>]*\bsrc=)[^>]*>", html, re.I)]
    assert inline and all(tag.startswith('<script type="text/x-surface"') for tag in inline), inline
    assert all('data-surface="' in tag for tag in inline), inline


def test_the_fifteen_top_level_surfaces_are_scripts_and_no_template_is_left_at_the_top():
    names = [re.search(r'data-surface="(\w+)"', m.group(1)).group(1) for m in SCRIPTS]
    assert sorted(names) == sorted(
        "atlasChat palette quickNote notes chat timeline graph documents reminders library ocr settings shortcuts meeting docDictionary".split()
    )
    outside = re.sub(r'<script type="text/x-surface".*?</script>', "", RAW, flags=re.S)
    assert "<template data-surface" not in outside, "a surface is a template at the top again: it is parsed at boot"


def test_a_surface_body_cannot_end_its_script_early():
    """A `</script` ends the block, and a `<!--` followed by a `<script` before its `-->` switches the parser into the
    double-escaped state where `</script>` no longer ends it. Neither text may appear in a body."""
    for m in SCRIPTS:
        body = m.group(2).lower()
        name = m.group(1)
        assert "<script" not in body and "</script" not in body, name


def test_nests_name_exactly_the_templates_inside_the_body():
    for m in SCRIPTS:
        nested = re.findall(r'<template data-surface="(\w+)"', m.group(2))
        named = re.search(r'data-nests="([^"]*)"', m.group(1))
        assert (named.group(1).split() if named else []) == nested, m.group(1)


def test_the_served_page_strips_comments_inside_every_surface_but_not_a_real_scripts_text():
    served = strip_html(RAW)
    for m in re.finditer(r'<script type="text/x-surface"([^>]*)>(.*?)</script>', served, re.S):
        assert "<!--" not in m.group(2), m.group(1)
    assert len(served) < len(RAW)
    mixed = '<script type="text/x-surface" data-surface="a"><p><!-- gone --></p></script><script>var s = "<!-- kept -->";</script>'
    out = strip_html(mixed)
    assert "gone" not in out and "<!-- kept -->" in out


def test_a_surface_block_is_not_an_inline_script_for_the_csp(tmp_path):
    page = tmp_path / "page.html"
    page.write_text('<script type="text/x-surface" data-surface="a"><p>x</p></script><script>go()</script>')
    assert len(security.inline_script_hashes(page)) == 1, "only the executable block is hashed"
    page.write_text('<script type="text/x-surface" data-surface="a"><p>x</p></script>')
    assert security.inline_script_hashes(page) == []
    assert security.inline_script_hashes(FRONTEND / "index.html") == []


def test_no_script_reads_a_surface_entry_but_settings_body_js():
    """`entry.tpl` is a script or a nested template and its `content` exists for only one of them: the
    others use `SURFACES.peek`, `surfaceBuild`, `onSurface` and `$`."""
    offenders = [
        p.name
        for p in (FRONTEND / "js").glob("*.js")
        if p.name != "settings-body.js" and re.search(r"\bSURFACES\.(get|set|has|entries|values|fragment|holds|register)\b", p.read_text(encoding="utf-8"))
    ]
    assert offenders == []


# ---- the loader, against a small fake DOM ------------------------------------------------------

_FAKE = r"""
const log = [];
const live = new Map();
function makeFragment(html) {
  const ids = new Set(Array.from(html.matchAll(/\sid="([^"]+)"/g), (m) => m[1]));
  const nested = Array.from(html.matchAll(/<template data-surface="(\w+)"[^>]*>(.*?)<\/template>/gs), (m) => m);
  return {
    getElementById: (id) => (ids.has(id) && !nested.some((n) => n[2].includes(`id="${id}"`)) ? { id } : null),
    querySelectorAll: () => nested.map((n) => tplFrom(n[1], n[2], null)),
    ids,
  };
}
function tplFrom(name, html, text) {
  const content = makeFragment(html);
  const el = { dataset: { surface: name }, content, parentNode: { name }, replaceWith(frag) {
    log.push('stamp ' + name);
    for (const id of frag.ids) if (!(frag.getElementById(id) === null)) live.set(id, { id, live: 1 });
  } };
  return el;
}
function scriptFrom(name, text, nests) {
  return { dataset: { surface: name, ...(nests ? { nests } : {}) }, text, parentNode: { name }, replaceWith(frag) {
    log.push('stamp ' + name);
    for (const id of frag.ids) if (frag.getElementById(id)) live.set(id, { id, live: 1 });
  } };
}
let parses = 0;
const scripts = [
  scriptFrom('notes', '<div id="notes-root"><div id="capture-bar-row" data-group-id="not-an-id"></div></div>'),
  scriptFrom('library', '<div id="lib"></div><template data-surface="board"><div id="whiteboard-container"></div></template>', 'board'),
];
const document = {
  querySelectorAll: () => scripts,
  getElementById: (id) => live.get(id) ?? null,
  createElement: () => { const holder = { get content() { parses++; return makeFragment(this._html); } }; Object.defineProperty(holder, 'innerHTML', { set(v) { this._html = v; } }); return holder; },
};
const window = { initHelpToggles: (h) => log.push('help ' + h.name) };
const timers = [];
globalThis.setTimeout = (fn, ms) => { timers.push([fn, ms]); return 0; };
"""


def _run(body: str) -> dict:
    src = (FRONTEND / "js" / "settings-body.js").read_text(encoding="utf-8")
    out = subprocess.run(["node", "-e", "\n".join([_FAKE, src, body])], capture_output=True, text=True, timeout=30)
    assert out.returncode == 0, out.stderr
    return json.loads(out.stdout)


@needs_node
def test_a_script_surface_is_found_by_its_ids_and_parsed_only_when_needed():
    r = _run(
        """
        const before = parses;
        const miss = surfaceFind('no-such-id');
        const falsePositive = surfaceFind('not-an-id');
        const afterMiss = parses;
        const found = surfaceFind('notes-root');
        console.log(JSON.stringify({ before, miss, falsePositive, afterMiss, found, parses, log }));
        """
    )
    assert r["before"] == 0 and r["afterMiss"] == 0, "a miss reads the ids in the text and parses nothing"
    assert r["miss"] is None and r["falsePositive"] is None, "data-group-id=... is not an id"
    assert r["found"]["live"] == 1 and r["parses"] == 1
    assert r["log"] == ["stamp notes", "help notes"]


@needs_node
def test_a_nested_surface_builds_its_parent_first_and_onSurface_waits_for_it():
    r = _run(
        """
        onSurface('board', () => log.push('board wiring'));
        const early = surfaceBuild('board');
        const again = surfaceBuild('board');
        onSurface('board', () => log.push('board now'));
        console.log(JSON.stringify({ early, again, log }));
        """
    )
    assert r["early"] is True and r["again"] is False
    assert r["log"] == ["stamp library", "help library", "stamp board", "help board", "board wiring", "board now"], r["log"]


@needs_node
def test_an_id_inside_a_nested_surface_builds_the_library_then_the_board():
    r = _run(
        """
        const found = surfaceFind('whiteboard-container');
        console.log(JSON.stringify({ found, log }));
        """
    )
    assert r["found"]["live"] == 1
    assert r["log"][0] == "stamp library" and "stamp board" in r["log"], r["log"]


@needs_node
def test_surface_node_reads_an_element_without_building_and_the_build_reuses_the_parse():
    r = _run(
        """
        const row = SURFACES.peek('notes', 'capture-bar-row');
        const none = SURFACES.peek('notes', 'nope');
        const built = surfaceBuild('notes');
        console.log(JSON.stringify({ row, none, built, parses, log }));
        """
    )
    assert r["row"] == {"id": "capture-bar-row"} and r["none"] is None
    assert r["built"] is True and r["parses"] == 1, "one parse serves the read and the build"
    assert r["log"] == ["stamp notes", "help notes"]


@needs_node
def test_idle_warming_parses_one_surface_per_slot_and_the_build_then_parses_nothing():
    r = _run(
        """
        const armed = timers.map((t) => t[1]);
        const run = () => { const [fn] = timers.shift(); fn(); };
        run();
        const afterOne = parses;
        run();
        const afterTwo = parses;
        run();
        const idle = timers.length;
        surfaceBuild("notes");
        console.log(JSON.stringify({ armed, afterOne, afterTwo, parses, idle, log }));
        """
    )
    assert r["armed"] == [3000], "one timer at load, nothing else"
    assert (r["afterOne"], r["afterTwo"]) == (1, 2), "one surface per slot"
    assert r["parses"] == 2, "the nested board is already parsed with the library, and the build reuses the warm parse"
    assert r["idle"] == 0, "nothing left to warm: the chain stops"
    assert r["log"] == ["stamp notes", "help notes"]
