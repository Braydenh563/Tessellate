"""Markdown in the dashboard widgets that lacked it (L-world-class-178). A
sweep rendered all 35 widgets over notes and a reminder written in Markdown
(scratchpad sweep dashmd.js): the Reminders widget showed "**Sam**" and
"[the venue](https://...)" raw, and every note-row widget (Favourites, Recently
added, Recent activity, Loose ends) showed a task line as "[ ] email Sam".
After: no raw bold, link or task box in any widget. `__x__` stays as typed:
the note body's inline grammar (INLINE_MD) does not read it either."""

from __future__ import annotations

import json
import re
import shutil
import subprocess

import pytest

from tests._app_js import frontend_text


def _dash() -> str:
    return frontend_text("dashboard.js")


def _function(src: str, name: str) -> str:
    start = src.index(f"function {name}(")
    depth, i = 0, src.index("{", start)
    while True:
        depth += {"{": 1, "}": -1}.get(src[i], 0)
        i += 1
        if depth == 0:
            return src[start:i]


def test_the_reminders_widget_draws_its_text_as_inline_markdown():
    body = _function(_dash(), "renderRemindersWidget")
    assert "renderInlineMarkdown(what, reminder.text, [], true)" in body
    assert "what.textContent = reminder.text" not in body


@pytest.mark.skipif(not shutil.which("node"), reason="needs node")
def test_a_note_rows_task_box_goes_with_its_bullet():
    body = _function(_dash(), "miniEntryList")
    line = re.search(r"const flat = raw\.replace\((/.*?/gm), \"\"\)\.trim\(\);", body).group(1)
    raw = "## Reading list\n- [ ] email Sam\n- [x] book the hall\n* plain bullet\n> a quote\n1. first"
    script = f"process.stdout.write(JSON.stringify({json.dumps(raw)}.replace({line}, '')))"
    flat = json.loads(subprocess.run(["node", "-e", script], capture_output=True, text=True, check=True).stdout)
    assert flat.split("\n") == ["Reading list", "email Sam", "book the hall", "plain bullet", "a quote", "first"]
