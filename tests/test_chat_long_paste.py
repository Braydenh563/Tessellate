"""A message over the 20,000 character limit is named, kept, and can become a note (audit 1028 E8)."""

from __future__ import annotations

import json
import re
import shutil
import subprocess

import pytest

from tests._app_js import JS_DIR

pytestmark = pytest.mark.skipif(not shutil.which("node"), reason="needs node")


def _fn(source: str, name: str) -> str:
    match = re.search(rf"^function {name}\(.*?^\}}", source, re.S | re.M)
    assert match, f"{name} is gone"
    return match.group(0)


def test_the_too_long_message_keeps_the_draft_and_offers_a_note():
    edit = (JS_DIR / "chat-edit.js").read_text(encoding="utf-8")
    script = f"""
const text = "x".repeat(25000);
const box = {{ value: text, dispatchEvent() {{}} }};
const $ = () => box;
const out = {{ posts: [], sent: null, said: null, label: null }};
let act = null;
const toastAction = (m, l, f) => {{ out.said = m; out.label = l; act = f; }};
const toast = () => {{}};
const apiJson = async (u, o) => {{ out.posts.push([u, JSON.parse(o.body).content.length]); return {{ id: 9 }}; }};
const sendChatMessage = (q, o) => {{ out.sent = [q, o]; }};
{_fn(edit, "chatTooLong")}
chatTooLong(text, true);
out.draftKept = box.value.length;
act().then(() => process.stdout.write(JSON.stringify({{ ...out, afterSave: box.value.length }})));
"""
    got = json.loads(subprocess.run(["node", "-e", script], capture_output=True, text=True, check=True).stdout)
    assert "25,000" in got["said"] and "20,000" in got["said"]
    assert "!" not in got["said"] and chr(0x2014) not in got["said"]
    assert got["label"] == "Save as a note and ask about it"
    assert got["draftKept"] == 25000  # nothing cleared by showing the message
    assert got["posts"] == [["/entries", 25000]]
    assert got["sent"][1] == {"noteIds": [9]}
    assert got["afterSave"] == 0


def test_send_checks_the_length_before_anything_is_cleared():
    attach = (JS_DIR / "chat-attach.js").read_text(encoding="utf-8")
    guard = attach.index("question.length > 2e4")
    assert guard < attach.index("lastChatQuestion = question;")
