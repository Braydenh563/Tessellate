"""The `[[` picker offers the note you are naming before the notes that mention it.

`editorLinkMatches` (frontend/js/editor.js) kept every note whose text held the
typed words anywhere, in list order (newest first), and showed the first six.
Typing `[[Alpha` in a notebook where several newer notes link to "Alpha
project" listed those, with Enter taking the first, and the note called Alpha
project was sixth or missing altogether. Found by
`scratchpad/ui-sweeps/deepflows.js`'s capture probe (Enter put `[[# Theta
fitness]]` in the text after `[[Alph`).

Notes whose opening line starts with the words come first, then those whose
opening line holds them, then the ones that only mention them in the body; the
list keeps its own order within each.
"""

from __future__ import annotations

import json
import re
import shutil
import subprocess

import pytest
from tests._app_js import JS_DIR

pytestmark = pytest.mark.skipif(not shutil.which("node"), reason="needs node")


def _run(entries: list[dict], query: str) -> list[str]:
    source = (JS_DIR / "editor.js").read_text(encoding="utf-8")
    match = re.search(r"^function editorLinkMatches\(needle\) \{.*?^\}", source, re.S | re.M)
    assert match, "editorLinkMatches is gone"
    script = f"""
const allEntries = {json.dumps(entries)};
const editorDocumentCache = [];
const editorFileCache = [];
// editorLinkMatches names a note by noteNamePlain (chat-attach.js, INBOX 820); its own tests cover the Markdown.
const noteNamePlain = (content, limit = 0) => {{ const name = String(content).split('\\n').find((l) => l.trim()).replace(/^#+\\s*/, '').trim(); return limit ? name.slice(0, limit) : name; }};
{match.group(0)}
process.stdout.write(JSON.stringify(editorLinkMatches({json.dumps(query)}).filter((i) => i.group === 'Notes').map((i) => i.value)));
"""
    return json.loads(subprocess.run(["node", "-e", script], capture_output=True, text=True, check=True).stdout)


def _note(i: int, content: str) -> dict:
    return {"id": i, "content": content, "is_private": False}


def test_the_note_named_comes_before_the_notes_that_link_to_it():
    # Newest first, as the list is: eight notes that point at the target, then the target.
    entries = [_note(20 - i, f"# Note {i}\n\nSee [[Alpha project]] for more.") for i in range(8)]
    entries.append(_note(1, "# Alpha project\n\nThe plan."))
    got = _run(entries, "Alph")
    #: The inserted text has no heading marker (audit 1031 N34); the ranking is what this pins.
    assert got[0] == "Alpha project", got
    assert len(got) == 6


def test_an_opening_line_that_holds_the_words_beats_a_mention_in_the_body():
    entries = [
        _note(3, "# Weekly review\n\nThe alpha release slipped."),
        _note(2, "# The alpha release\n\nNotes."),
        _note(1, "# Alpha plan\n\nNotes."),
    ]
    assert _run(entries, "alpha") == ["Alpha plan", "The alpha release", "Weekly review"]


def test_with_nothing_typed_the_list_keeps_its_own_order():
    entries = [_note(3, "# C"), _note(2, "# B"), _note(1, "# A")]
    assert _run(entries, "") == ["C", "B", "A"]


def test_private_notes_are_still_never_offered():
    entries = [{"id": 1, "content": "# Alpha secret", "is_private": True}, _note(2, "# Alpha open")]
    assert _run(entries, "alpha") == ["Alpha open"]
