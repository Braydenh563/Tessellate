"""A status item that paints the same words again leaves its button alone (L323).

Every document keystroke asks the status bar to repaint Undo and Redo; the buttons
were rebuilt each time (children replaced, title and aria-label rewritten), which
cost style and layout work per key that a bare CodeMirror editor does not pay
(60 keys at 4x CPU: UpdateLayoutTree 7.7 ms a key against 2.3 bare).
"""

import json
import shutil
import subprocess

import pytest

from tests._app_js import app_js_text

needs_node = pytest.mark.skipif(shutil.which("node") is None, reason="node is not installed")


def _function(source: str, head: str) -> str:
    start = source.index(head)
    return source[start : source.index("\n}\n", start) + 3]


def _run(steps: str) -> dict:
    body = _function(app_js_text(), "function paintStatusItem(")
    script = (
        """
const writes = [];
const mk = () => {
  const el = { id: "b", children: [], attrs: {}, classes: new Set(), _title: "" };
  el.replaceChildren = () => { writes.push("children"); el.children = []; };
  el.appendChild = (c) => { el.children.push(c); };
  el.append = (c) => { el.children.push(c); };
  el.setAttribute = (k, v) => { writes.push("attr"); el.attrs[k] = v; };
  el.removeAttribute = (k) => { writes.push("attr"); delete el.attrs[k]; };
  Object.defineProperty(el, "title", { get: () => el._title, set: (v) => { writes.push("title"); el._title = v; } });
  Object.defineProperty(el, "firstChild", { get: () => el.children[0] || null });
  el.classList = { toggle: (n, on) => { writes.push("class"); on ? el.classes.add(n) : el.classes.delete(n); } };
  return el;
};
const button = mk();
const $ = () => button;
const shortcutTitle = (t) => t;
const setLabel = () => {};
const document = { createElement: () => ({ setAttribute() {}, textContent: "" }) };
"""
        + body
        + steps
    )
    out = subprocess.run(["node", "-e", script], capture_output=True, text=True, check=True)
    return json.loads(out.stdout)


@needs_node
def test_the_same_paint_twice_writes_nothing_the_second_time():
    out = _run('paintStatusItem("b", { icon: "i", title: "Undo: x" }); const n = writes.length; paintStatusItem("b", { icon: "i", title: "Undo: x" }); console.log(JSON.stringify({ n, after: writes.length, aria: button.attrs["aria-label"] }));')
    assert out["n"] > 0 and out["after"] == out["n"] and out["aria"] == "Undo: x"


@needs_node
def test_a_changed_title_or_tone_paints_again():
    out = _run(
        'paintStatusItem("b", { icon: "i", title: "A" }); const n = writes.length; paintStatusItem("b", { icon: "i", title: "B" });'
        ' const m = writes.length; paintStatusItem("b", { icon: "i", title: "B", tone: "due" });'
        " console.log(JSON.stringify({ n, m, k: writes.length, aria: button.attrs['aria-label'], due: button.classes.has('status-due') }));"
    )
    assert out["m"] > out["n"] and out["k"] > out["m"] and out["aria"] == "B" and out["due"] is True
