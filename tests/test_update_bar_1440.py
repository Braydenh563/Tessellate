"""INBOX 1440: an update is a bar the person can close, never a dialog, and
nothing installs without a press.

The owner: "i feel like auto updates may be unwanted by the user, if one is
detected, a notification bar or smth at the top should appear that is
closable and the user can choose to hide the bar from showing in settings,
but that bar will have an update button that they can willingly and
intentionally press."
"""

from __future__ import annotations

import shutil
import subprocess
import textwrap
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
JS = (ROOT / "frontend" / "js" / "update-dialogs.js").read_text(encoding="utf-8")


def _fn(name: str) -> str:
    start = JS.index(f"function {name}(")
    return JS[start : JS.index("\n}\n", start)]


def test_the_modal_path_is_gone():
    for path in (ROOT / "frontend" / "js").glob("*.js"):
        assert "showUpdateAvailableDialog" not in path.read_text(encoding="utf-8"), path.name
    assert "modal-overlay" not in _fn("checkForUpdate")


def test_the_bar_is_shown_once_per_version_and_only_when_the_switch_is_on():
    body = _fn("checkForUpdate")
    assert "showUpdateBar(result)" in body
    gate = body[body.index("if (silent") :]
    assert "UPDATE_SEEN_KEY" in gate and "show_update_bar" in gate
    assert "!== false" in gate, "the switch defaults on"


def test_closing_the_bar_records_the_version_and_the_bar_is_a_labelled_region():
    bar = _fn("showUpdateBar")
    assert "prefs.set(UPDATE_SEEN_KEY, result.latest)" in bar
    assert "data-dismiss" in bar
    assert '"region"' in bar and "aria-label" in bar
    assert "notice" in bar
    assert "applyUpdateNow" in bar and "can_auto_apply" in bar
    assert "result.url" in bar, "where it cannot apply itself the button opens the release page"


def test_the_switch_is_wired_everywhere():
    html = (ROOT / "frontend" / "index.html").read_text(encoding="utf-8")
    assert 'id="pref-update-bar"' in html
    assert "Show the update bar" in html
    rows = (ROOT / "frontend" / "js" / "settings-rows.js").read_text(encoding="utf-8")
    assert '{ key: "show_update_bar", id: "pref-update-bar" }' in rows
    assert "show_update_bar" in (ROOT / "frontend" / "js" / "settings.js").read_text(encoding="utf-8")
    assert "show_update_bar" in (ROOT / "frontend" / "js" / "settings-controls.js").read_text(encoding="utf-8")


def test_the_preference_defaults_on_and_round_trips(client, app_state):
    assert client.get("/preferences").json()["show_update_bar"] is True
    saved = client.put("/preferences", json={"show_update_bar": False})
    assert saved.status_code == 200
    assert client.get("/preferences").json()["show_update_bar"] is False
    assert app_state.get_preference("show_update_bar", True) is False


def test_apply_from_the_bar_needs_no_auto_update_switch(client, app_state):
    """The press is the consent: with the install switch off the request gets
    past the guard and stops at the build check, not at a 403."""
    app_state.set_preference("update_check_enabled", True)
    app_state.set_preference("auto_update_enabled", False)
    response = client.post("/update/apply")
    assert response.status_code == 409
    assert "packaged Windows" in response.json()["detail"]


def test_saying_yes_to_checking_never_turns_on_a_pull_on_start(client, app_state):
    answered = client.post("/update/choice", json={"check": True})
    assert answered.status_code == 200
    assert app_state.get_preference("update_check_enabled") is True
    assert app_state.get_preference("auto_update_enabled") is False


@pytest.mark.skipif(not shutil.which("node"), reason="node is not installed")
def test_closing_the_bar_stores_the_seen_version(tmp_path):
    src = "async " + _fn("showUpdateBar") + "\n}\n"
    script = textwrap.dedent(
        """
        const UPDATE_SEEN_KEY = "update-seen-version";
        const store = {};
        const prefs = { get: (k, d) => (k in store ? store[k] : d), set: (k, v) => { store[k] = v; } };
        const made = [];
        function mk(tag) {
          return { tag, children: [], attrs: {}, classList: { add() {}, remove() {} }, listeners: {},
            setAttribute(k, v) { this.attrs[k] = v; }, append(...c) { this.children.push(...c); },
            appendChild(c) { this.children.push(c); }, addEventListener(t, f) { this.listeners[t] = f; },
            remove() { made.length = 0; }, after(n) { made.push(n); }, focus() {} };
        }
        const document = { createElement: mk, getElementById: () => null,
          querySelector: () => ({ after(n) { made.push(n); }, remove() {} }) };
        const setLabel = () => {};
        const smallButton = (a, b, fn) => { const el = mk("button"); el.listeners.click = fn; return el; };
        const applyUpdateNow = async () => true;
        const toast = () => {};
        const lazyScript = async () => true;
        const $ = () => null;
        const window = { open() {} };
        %s
        (async () => {
        await showUpdateBar({ latest: "9.9.9", current: "1.0.0", url: "https://x", can_auto_apply: false });
        const bar = made[0];
        if (!bar) throw new Error("no bar");
        function find(n, f) { if (f(n)) return n; for (const c of n.children || []) { const r = find(c, f); if (r) return r; } return null; }
        const close = find(bar, (n) => n.attrs && n.attrs["data-dismiss"] === "notice");
        if (!close) throw new Error("no close button");
        close.listeners.click();
        if (store[UPDATE_SEEN_KEY] !== "9.9.9") throw new Error("seen not stored");
        console.log("ok");
        })().catch((e) => { console.error(e); process.exit(1); });
        """
    ) % src
    path = tmp_path / "ub1440_latch.js"
    path.write_text(script, encoding="utf-8")
    out = subprocess.run(["node", str(path)], capture_output=True, text=True, timeout=30)
    assert out.stdout.strip() == "ok", out.stderr
