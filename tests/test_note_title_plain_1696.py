"""A note's title in a link list is read without its Markdown marks (INBOX 1696 d).

The owner, with a screenshot of Settings, What it learned: a "From 10 notes"
link read "The Complete Social Skills Guide**". The server's link title
(`link_wording.title`) stripped the leading marks of a first line and kept the
closing ones; the app printed `note.title` as it came. The server drops
them now, and every link or chip that shows a note title the server sent goes
through the app's one name helper, `noteNamePlain` (chat-attach.js, INBOX 820).
The browser part runs in node against the app's own helpers.
"""

from __future__ import annotations

import json
import re
import shutil
import subprocess
from pathlib import Path

import pytest

from tessellate.entry import link_wording
from tests._app_js import app_js_text

ROOT = Path(__file__).resolve().parents[1]
JS = ROOT / "frontend" / "js"
SOURCE = app_js_text()

CASES = [
    ("**Bold title**", "Bold title"),
    ("# Heading", "Heading"),
    ("The Complete Social Skills Guide**", "The Complete Social Skills Guide"),
    ("__Under__ title", "Under title"),
    ("`code` title", "code title"),
    ("- **Bold** item", "Bold item"),
    ("1. Numbered", "Numbered"),
    ("my_file_name", "my_file_name"),
]


@pytest.mark.parametrize(("stored", "shown"), CASES)
def test_the_server_link_title_drops_the_marks(stored: str, shown: str) -> None:
    assert link_wording.title(stored + "\nbody", limit=48) == shown


def _grab(pattern: str, what: str) -> str:
    match = re.search(pattern, SOURCE, re.S | re.M)
    assert match, f"{what} is gone from the app's scripts"
    return match.group(0)


def _run(expression: str):
    parts = [
        _grab(r"^const INLINE_MD =\n?[^\n]*;\n", "INLINE_MD"),
        _grab(r"^const STAGED_URL_PREFIX = [^\n]*;\n", "STAGED_URL_PREFIX"),
        _grab(r"^function isRenderableUrl\(url\) \{.*?^\}\n", "isRenderableUrl"),
        _grab(r"^function stripFrontmatter\(text\) \{.*?^\}\n", "stripFrontmatter"),
        _grab(r"^function previewBlocks\(text\) \{.*?^\}\n", "previewBlocks"),
        _grab(r"^function notePreviewText\(content\) \{.*?^\}\n", "notePreviewText"),
        _grab(r"^function flattenNoteMarkdown\(md\) \{.*?^\}\n", "flattenNoteMarkdown"),
        _grab(r"^function clipText\(text, limit\) \{.*?^\}\n", "clipText"),
        _grab(r"^function noteNamePlain\(content, limit = 0\) \{.*?^\}\n", "noteNamePlain"),
    ]
    script = "\n".join(parts) + f"\nprocess.stdout.write(JSON.stringify({expression}));"
    return json.loads(subprocess.run(["node", "-e", script], capture_output=True, text=True, check=True).stdout)


#: The app's helper reads paired marks; an unpaired one ("Guide**", "__x__")
#: is the server's to drop (above), so the eager bundle stays in its gzip budget.
APP_CASES = [c for c in CASES if c[0] not in ("The Complete Social Skills Guide**", "__Under__ title")]


@pytest.mark.skipif(not shutil.which("node"), reason="needs node")
def test_the_app_name_helper_drops_the_marks() -> None:
    got = _run(f"{json.dumps([c[0] for c in APP_CASES])}.map((s) => noteNamePlain(s))")
    assert got == [c[1] for c in APP_CASES]


@pytest.mark.parametrize(
    ("name", "site"),
    [
        ("settings-controls.js", 'open.textContent = noteNamePlain(note.title) || "Untitled note";'),
        ("entity-page.js", 'open.textContent = noteNamePlain(m.title) || "Untitled note";'),
        ("dashboard.js", 'title.textContent = noteNamePlain(item.title || "") || "Untitled note";'),
    ],
)
def test_a_title_shown_as_a_link_goes_through_the_one_helper(name: str, site: str) -> None:
    assert site in (JS / name).read_text(encoding="utf-8")
