"""The user's own bubble drops a stray key typed against a word (OPEN row 556).

The server already reads "what is there about dentist\\" as the question
without the backslash (question_noise); the bubble showed it as typed.
`chatTidyTyped` takes the same trailing run off before the bubble is drawn,
and leaves an emoticon (":\\") and a lone key alone.
"""

from __future__ import annotations

import json
import re
import shutil
import subprocess

import pytest

from tests._app_js import with_pieces


def _tidy(text: str) -> str:
    source = with_pieces("chat-attach.js")
    match = re.search(r"^function chatTidyTyped\(text\) \{.*?^\}", source, re.S | re.M)
    assert match, "chatTidyTyped is gone from chat-attach.js"
    script = match.group(0) + f"\nprocess.stdout.write(JSON.stringify(chatTidyTyped({json.dumps(text)})));"
    return json.loads(subprocess.run(["node", "-e", script], capture_output=True, text=True, check=True).stdout)


@pytest.mark.skipif(not shutil.which("node"), reason="needs node")
@pytest.mark.parametrize(
    ("typed", "shown"),
    [
        ("what is there about dentist\\", "what is there about dentist"),
        ("summarise my week\\\\ ", "summarise my week"),
        ("how was the trip?|", "how was the trip?"),
        ("that is sad :\\", "that is sad :\\"),
        ("\\", "\\"),
        ("a\\b path", "a\\b path"),
    ],
)
def test_a_stray_trailing_key_is_dropped(typed, shown):
    assert _tidy(typed) == shown


def test_the_send_path_tidies_what_it_shows():
    source = with_pieces("chat-attach.js")
    assert "const typed = chatTidyTyped((preset ?? input.value).trim());" in source
