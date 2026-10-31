"""The `[[` picker names a note once and previews it without repeating it (INBOX 784).

A note the sketch pad saves is its title, then the drawing with the title as
its alt text. The picker's row was the whole note flattened to one line
("Gary The Moss Monster :D Gary The Moss M...") and its preview was the whole
note flattened to lines: the title four times, no picture. The row is now the
opening line alone; the preview (`note-pick-preview.js`) shows an excerpt that
skips the title, picture-only lines and repeats, and the first picture.
"""

from __future__ import annotations

import json
import re
import shutil
import subprocess

import pytest
from tests._app_js import JS_DIR

pytestmark = pytest.mark.skipif(not shutil.which("node"), reason="needs node")

SKETCH = "Gary The Moss Monster :D\n\n![Gary The Moss Monster :D](/media/a.png)\n\n![Gary The Moss Monster :D](/media/b.png)\n\nGary The Moss Monster :D"


def _function(name: str, file: str) -> str:
    match = re.search(rf"^function {name}\(.*?^\}}", (JS_DIR / file).read_text(encoding="utf-8"), re.S | re.M)
    assert match, f"{name} is gone from {file}"
    return match.group(0)


def _constant(name: str, file: str) -> str:
    match = re.search(rf"^const {name} =.*?;$", (JS_DIR / file).read_text(encoding="utf-8"), re.S | re.M)
    assert match, f"{name} is gone from {file}"
    return match.group(0)


def _node(body: str):
    return json.loads(subprocess.run(["node", "-e", body], capture_output=True, text=True, check=True).stdout)


def _excerpt(content: str) -> list[str]:
    preview = (JS_DIR / "note-pick-preview.js").read_text(encoding="utf-8")
    head = re.search(r"^const NOTE_PICK_LINES.*?^function notePickThumb", preview, re.S | re.M).group(0).rsplit("//:", 1)[0]
    script = f"""
{_constant("INLINE_MD", "notes-list.js")}
{_function("stripFrontmatter", "shell-reminders.js")}
{_function("previewBlocks", "shell-reminders.js")}
{_function("notePreviewText", "shell-reminders.js")}
{head}
process.stdout.write(JSON.stringify(notePickExcerpt({json.dumps(content)})));
"""
    return _node(script)


def _label(content: str) -> str:
    source = (JS_DIR / "editor.js").read_text(encoding="utf-8")
    match = re.search(r"^function editorLinkMatches\(needle\) \{.*?^\}", source, re.S | re.M)
    assert match
    script = f"""
const allEntries = [{{ id: 1, content: {json.dumps(content)}, is_private: false }}];
const editorDocumentCache = [];
const editorFileCache = [];
// editorLinkMatches names a note by noteNamePlain (chat-attach.js, INBOX 820); its own tests cover the Markdown.
const noteNamePlain = (content, limit = 0) => {{ const name = String(content).split('\\n').find((l) => l.trim()).replace(/^#+\\s*/, '').trim(); return limit ? name.slice(0, limit) : name; }};
{match.group(0)}
process.stdout.write(JSON.stringify(editorLinkMatches("gary")[0].label));
"""
    return _node(script)


def test_the_row_names_a_sketch_note_by_its_opening_line_alone():
    assert _label(SKETCH) == "Gary The Moss Monster :D"


def test_the_excerpt_of_a_title_and_a_drawing_is_empty():
    assert _excerpt(SKETCH) == []


def test_the_excerpt_skips_the_title_pictures_and_repeats():
    text = SKETCH.replace("\n\nGary The Moss Monster :D", "\n\nHe lives under the bridge.\nHe lives under the bridge.\nGary is friendly.\n\nGary The Moss Monster :D")
    assert _excerpt(text) == ["He lives under the bridge.", "Gary is friendly."]


def test_the_excerpt_is_three_short_lines_at_most():
    text = "# Title\n" + "\n".join(f"Line {i} " + "x" * 200 for i in range(6))
    got = _excerpt(text)
    assert len(got) == 3 and all(len(line) <= 120 for line in got)


def test_a_note_that_opens_on_a_picture_keeps_its_first_words_as_the_title():
    assert _excerpt("![alt](/media/a.png)\n\nBridge troll\n\nHe waits.") == ["He waits."]


def test_the_preview_file_rides_the_note_panels_bundle():
    app = (JS_DIR / "app.js").read_text(encoding="utf-8")
    assert '"/js/note-edit-panels.js", "/js/note-pick-preview.js"]' in app
    assert '"renderEditForm", "richPickerNote"]' in app
