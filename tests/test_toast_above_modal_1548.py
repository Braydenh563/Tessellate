"""INBOX 1548 (the owner): "why is that notification hidden when Im on the
settings?" A toast raised with Settings open was drawn at opacity 0.12 with
clicks passing through to the dialog.

Measured at 1440 by 900 (a28t, scratchpad): the toast stack (`#toast-box`,
z-index 2150) is above Settings (1010), which is a `div[role=dialog]` and so
not in the top layer, and `elementFromPoint` at the toast's centre returned
`#settings-modal`. The cause was not the layer: `toastYield` (WCAG 2.4.11)
counted the dialog's resize grip, a `button.panel-grip` in its bottom-right
corner, as a control the toast hides, so every toast that landed in that corner
stepped aside. A native `<dialog>` modal is covered by `toastHost` (INBOX 470),
which puts the stack inside the open dialog."""

from __future__ import annotations

import json
import shutil
import subprocess
import textwrap

import pytest

from tests._app_js import frontend_text

NODE = shutil.which("node")


def _body(js: str, head: str) -> str:
    start = js.index(head)
    return js[start : js.index("\n}\n", start)] + "\n}"


def _yields(buttons: list[dict], toast: list[int]) -> bool:
    """Run the real `toastYield` in a dialog whose buttons are `buttons`."""
    script = textwrap.dedent(
        """
        const cfg = %s;
        const rect = (r) => ({ left: r[0], top: r[1], right: r[0] + r[2], bottom: r[1] + r[3], width: r[2], height: r[3] });
        const classes = new Set();
        const toastEl = { toastTimer: 1, getBoundingClientRect: () => rect(cfg.toast) };
        const box = { id: "toast-box", children: [toastEl], contains: () => false, classList: {
          remove: (c) => classes.delete(c), toggle: (c, on) => (on ? classes.add(c) : classes.delete(c)) } };
        const $ = () => box;
        const document = { body: {}, activeElement: null };
        const innerWidth = 1440, innerHeight = 900;
        const area = {
          role: "dialog",
          querySelectorAll: (selector) => cfg.buttons
            .filter((b) => !(selector.includes(":not(.panel-grip)") && b.grip))
            .map((b) => ({ checkVisibility: () => true, getBoundingClientRect: () => rect(b.rect) })),
        };
        const target = { closest: () => area, getBoundingClientRect: () => rect([20, 20, 30, 30]) };
        %s
        toastYield(target);
        console.log(JSON.stringify(classes.has("is-yielding")));
        """
    ) % (json.dumps({"buttons": buttons, "toast": toast}), _body(frontend_text("status.js"), "function toastYield("))
    out = subprocess.run([NODE, "-e", script], capture_output=True, text=True)
    assert out.returncode == 0, out.stderr
    return json.loads(out.stdout)


@pytest.mark.skipif(NODE is None, reason="node is not installed")
def test_a_toast_over_the_resize_grip_of_an_open_dialog_stays_whole():
    grip = {"grip": True, "rect": [1390, 770, 32, 32]}
    assert _yields([grip], [1211, 761, 212, 38]) is False


@pytest.mark.skipif(NODE is None, reason="node is not installed")
def test_a_toast_over_a_real_button_of_the_dialog_still_steps_aside():
    button = {"grip": False, "rect": [1300, 770, 90, 32]}
    assert _yields([button], [1211, 761, 212, 38]) is True


def test_a_native_modal_dialog_still_gets_the_stack_inside_it():
    """Top layer: a `<dialog>` shown with showModal draws over every z-index,
    so its toasts live inside it (`toastHost`)."""
    body = _body(frontend_text("status.js"), "function toastHost(")
    assert 'document.querySelector("dialog:modal")' in body
    assert "dialog.appendChild(host)" in body
