"""F2, draw.io's "connection arrows and points as View toggles": two switches in the View menu hide the
arrow grips and the join dots, kept on this device; off hides the drawing only.

The module runs in node against a small stand-in for the page; the menu rows and the rule are read from the source."""

from __future__ import annotations

import json
import shutil
import subprocess

import pytest

from tests import _js_scope
from tests._app_js import frontend_text, script_file_text


def _run(stored: dict[str, str], click: str | None = None) -> dict:
    node = shutil.which("node")
    if not node:
        pytest.skip("node is not installed")
    script = f"""
const saved = {json.dumps(stored)};
const classes = new Set();
const boxes = {{}};
for (const id of ["wb-view-grips", "wb-view-ports"]) {{
  boxes[id] = {{ checked: true, on: {{}}, addEventListener(type, fn) {{ this.on[type] = fn; }} }};
}}
const document = {{ getElementById: (id) => (id === "library-view-whiteboard" ? {{ classList: {{ toggle: (c, on) => (on ? classes.add(c) : classes.delete(c)) }} }} : boxes[id] ?? null) }};
const onSurface = (name, run) => run();
const wbFmtState = {{}};
const toast = () => {{}};
const prefs = {{ get: (k, d) => saved[k] ?? d, set: (k, v) => (saved[k] = v) }};
{frontend_text("whiteboard-hints.js")}
{"boxes[" + json.dumps(click) + "].checked = false; boxes[" + json.dumps(click) + "].on.change();" if click else ""}
console.log(JSON.stringify({{ classes: [...classes].sort(), saved, grips: boxes["wb-view-grips"].checked, ports: boxes["wb-view-ports"].checked }}));
"""
    out = subprocess.run([node, "-e", script], capture_output=True, text=True, timeout=30, check=True)
    return json.loads(out.stdout)


def test_both_are_on_until_turned_off():
    assert _run({}) == {"classes": [], "saved": {}, "grips": True, "ports": True}


def test_a_stored_off_hides_that_one_only():
    got = _run({"wb-view-ports": "off"})
    assert got["classes"] == ["wb-hide-ports"] and got["ports"] is False and got["grips"] is True


def test_turning_a_switch_off_is_kept_on_the_device():
    got = _run({}, click="wb-view-grips")
    assert got["classes"] == ["wb-hide-grips"] and got["saved"] == {"wb-view-grips": "off"}


def test_the_menu_rows_the_rule_and_the_bundle_agree():
    html = frontend_text("index.html")
    for ident, word in (("wb-view-grips", "Connection arrows"), ("wb-view-ports", "Connection points")):
        row = html[html.rindex("<label", 0, html.index(f'id="{ident}"')) : html.index(f'id="{ident}"')]
        assert word in row and "wb-menu-row" in row
    css = frontend_text("css/library-lazy.css")
    rule = css[css.index("#library-view-whiteboard.wb-hide-grips #wb-clone-grips") :]
    rule = rule[: rule.index("}")]
    assert "#library-view-whiteboard.wb-hide-ports #wb-anchor-hints" in rule and "display: none;" in rule and "!important" not in rule
    assert "/js/whiteboard-hints.js" in frontend_text("lazy-entries.js")
    assert _js_scope.is_wrapped(script_file_text("whiteboard-hints.js")) and _js_scope.global_names(script_file_text("whiteboard-hints.js")) == set()
