"""INBOX 1501 (audit PF9, row 54): Settings' body is built when it first opens.

The 21 sections (2,700 nodes, 784 ids) sat in index.html under a window that is
`display:none` until somebody opens it, and cost every boot their parse, their
memory and a share of every style pass. They now sit in an inert `<template>`
and `surfaceBuild("settings")` (settings-body.js) puts them in the page on the first
open, or the first `$("<id>")` that asks for one of them. The numbers are in
CHANGELOG.md; this holds the shape, and the one rule that keeps it cheap: a
script that loads at boot must not ask for a control in the body, because the
ask would build all of it at boot again.
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
INDEX = (FRONTEND / "index.html").read_text(encoding="utf-8")
BODY_JS = (FRONTEND / "js" / "settings-body.js").read_text(encoding="utf-8")
needs_node = pytest.mark.skipif(not shutil.which("node"), reason="needs node")

TEMPLATE = re.search(r'<template id="settings-body-template" data-surface="settings">(.*?)</template>', INDEX, re.S)


def _template() -> str:
    assert TEMPLATE, "the Settings body template is gone from index.html"
    return TEMPLATE.group(1)


def _body_ids() -> set[str]:
    return set(re.findall(r'\bid="([^"]+)"', _template()))


def _boot_scripts() -> list[str]:
    """The local scripts the page loads at boot, in order (not the lazy bundles)."""
    return [m.group(1) for m in re.finditer(r'<script src="(/js/[^"?]+)', INDEX)]


def test_the_sections_sit_in_one_template_inside_the_modal_content():
    body = _template()
    assert len(re.findall(r'<section class="settings-section"', body)) == len(
        re.findall(r'class="settings-section"', INDEX)
    ), "every settings section is in the template, none outside it"
    before = INDEX[: TEMPLATE.start()]
    assert 'class="modal-content" tabindex="-1"' in before[-1200:], "the template is the content of the modal"
    assert INDEX.count('id="settings-body-template"') == 1


def test_the_template_is_not_the_nav_or_the_search_or_the_close():
    # The nav (reveal targets, the jump select, the search) is part of the shell
    # and is never lazy: it is what a deep link lands in before the body exists.
    ids = _body_ids()
    for shell in ("settings-modal", "settings-close", "settings-search", "settings-nav-help"):
        assert shell not in ids, f"{shell} belongs to the shell, not the lazy body"
    for pane in ("settings-models", "settings-appearance", "settings-about", "settings-logs"):
        assert pane in ids


def test_the_script_loads_before_app_js_which_calls_it():
    scripts = _boot_scripts()
    assert "/js/settings-body.js" in scripts
    assert scripts.index("/js/settings-body.js") < scripts.index("/js/app.js")
    assert re.search(r"^const \$ = \(id\) => document\.getElementById\(id\) \|\| surfaceFind\(id\);$", _src("app.js"), re.M)


def _src(name: str) -> str:
    return (FRONTEND / "js" / name).read_text(encoding="utf-8")


def test_opening_the_window_builds_the_body_first():
    src = _src("settings.js")
    start = src.index("function openSettingsModal")
    head = src[start : start + 2500]
    assert 'surfaceBuild("settings");' in head
    assert head.index('surfaceBuild("settings");') < min(
        i for i in (head.find('$("'), head.find("showSettingsSection(")) if i != -1
    ), "the body is built before the first control is read"
    controls = _src("settings-controls.js")
    assert controls.index('surfaceBuild("settings");') < controls.index('$("'), "the lazy listeners find their controls"


def test_no_boot_script_asks_for_a_control_in_the_body_at_its_top_level():
    ids = _body_ids()
    asks = re.compile(r'\$\(\s*["\']([\w-]+)["\']\s*\)')
    found: list[str] = []
    for script in _boot_scripts():
        text = _src(script.rsplit("/", 1)[1])
        for number, line in enumerate(text.splitlines(), 1):
            # A top-level statement starts in column 0; what is indented is in
            # a function that runs when something calls it, not at load.
            if not line or line[0] in " \t/}*)]" or line.startswith(("//", "function", "async function")):
                continue
            for match in asks.finditer(line):
                if match.group(1) in ids:
                    found.append(f"{script}:{number} {match.group(0)}")
    assert not found, "a boot script reads a control of Settings' body and would build it: " + "; ".join(found)


def test_no_boot_script_sweeps_the_body_at_its_top_level():
    # The same mistake by selector: `wireFoldHelps();` at the top of settings.js
    # ran before the body existed, found no folds, and every fold's '?' sat
    # unplaced over the head's corner. A function that queries Settings by
    # selector runs from `onSurface("settings", ...)`, never as a bare top-level call.
    funcs = {}
    for script in _boot_scripts():
        text = _src(script.rsplit("/", 1)[1])
        for m in re.finditer(r"^(?:async )?function (\w+)\([^)]*\) \{\n(.*?)^\}", text, re.S | re.M):
            funcs[m.group(1)] = m.group(2)
    sweeps = re.compile(r"querySelector(?:All)?\(\s*[\"'`][^\"'`]*#settings-modal")
    found = []
    for script in _boot_scripts():
        text = _src(script.rsplit("/", 1)[1])
        for m in re.finditer(r"^(\w+)\(\);?$", text, re.M):
            if sweeps.search(funcs.get(m.group(1), "")):
                found.append(f"{script} {m.group(1)}()")
    assert not found, "a boot script sweeps Settings' body before it is built: " + "; ".join(found)


def test_every_boot_sweep_over_the_body_is_rerun_at_the_build():
    # What the page ran over every control at boot, for the controls that now
    # arrive late (the four a before/after snapshot of every section found).
    assert "window.initHelpToggles?.(host);" in BODY_JS
    # The dock-menu, chord and title sweeps moved into `surfaceBuild` itself, over the stamped host, so every
    # surface gets them (row 21 review); `test_surface_templates` holds that shape.
    for sweep in ("hideClosedDockMenuLists", "localizeStaticChords", "stampShortcutTitles"):
        assert f"window.{sweep}?.(host);" in BODY_JS
    assert 'onSurface("settings", syncNotifBlocked);' in _src("status.js")


def test_the_reveal_targets_and_the_guide_reach_ids_that_exist():
    # An id a reveal target names is in the template (or elsewhere in the page);
    # `revealFeature` asks `$`, which builds the body on the way.
    reveal = _src("reveal-targets.js")
    page_ids = set(re.findall(r'\bid="([^"]+)"', INDEX))
    wanted = set(re.findall(r'\b(?:el|fallback): "([\w-]+)"', reveal))
    assert len(wanted) > 50, "the reveal table was not read"
    missing = sorted(w for w in wanted if w not in page_ids)
    assert not missing, f"reveal targets name ids that are not in the page: {missing}"


def _run(body: str) -> dict:
    parts = [
        "const log = []; let built = 0;",
        "const content = { getElementById: (id) => (id === 'sync-now' ? { id } : null) };",
        "const host = {};",
        "const tpl = { dataset: { surface: 'settings' }, content, parentNode: host, replaceWith(c) { built++; log.push('replace'); } };",
        "const document = { querySelectorAll: () => [tpl], getElementById: (id) => (built && id === 'sync-now' ? { id, live: 1 } : null) };",
        "const window = { initHelpToggles: (h) => log.push(h === host ? 'help' : 'help-wrong-root') };",
        BODY_JS,
        body,
    ]
    out = subprocess.run(["node", "-e", "\n".join(parts)], capture_output=True, text=True, timeout=30)
    assert out.returncode == 0, out.stderr
    return json.loads(out.stdout)


@needs_node
def test_build_is_once_find_builds_on_demand_and_the_queue_runs_after_it():
    result = _run(
        """
        const first = surfaceFind('no-such-id');
        const afterMiss = built;
        onSurface('settings', () => log.push('queued'));
        const found = surfaceFind('sync-now');
        const again = surfaceBuild('settings');
        onSurface('settings', () => log.push('now'));
        console.log(JSON.stringify({ first, afterMiss, found, built, again, log }));
        """
    )
    assert result["first"] is None and result["afterMiss"] == 0, "a miss builds nothing"
    assert result["found"]["live"] == 1, "the control, from the page, after the build"
    assert result["built"] == 1 and result["again"] is False, "built once"
    assert result["log"] == ["replace", "help", "queued", "now"], result["log"]
