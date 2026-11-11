"""A save re-reads the notes it touched, not the notebook (audit 2026-10-05,
FE-05).

`loadEntries()` pages through every note: at 5,010 notes that was 27
requests and 5.3 MB per save, from 132 call sites. `refreshEntries(ids)`
(notes-list.js) asks `GET /entries?ids=` for the touched notes and patches
them into `allEntries`, falling back to the full read whenever it cannot
patch (tests/test_entries_by_ids.py holds the server half). The browser half
is `scratchpad/ui-sweeps/fe1005-save.js`: requests per save at 5,000 notes.

These hold the shape: the paths the audit named go through the patch, and the
count of full re-reads can only go down.
"""

from __future__ import annotations

import re
from pathlib import Path

JS = Path(__file__).resolve().parents[1] / "frontend" / "js"


def _function(file: str, name: str) -> str:
    text = (JS / file).read_text(encoding="utf-8")
    start = re.search(rf"^(async )?function {name}\(", text, re.M).start()
    end = text.index("\n}\n", start)
    return text[start:end]


def _code(text: str) -> str:
    return "\n".join(line for line in text.split("\n") if not line.lstrip().startswith("//"))


def test_refresh_patches_from_one_request_and_checks_the_total():
    body = _code(_function("notes-list.js", "refreshEntries"))
    assert body.count("api(") == 1 and "/entries?ids=" in body
    assert 'headers.get("X-Total-Count")' in body
    # Anything it cannot patch is the full read, never a partial list.
    assert body.count("return loadEntries()") >= 3
    assert "entriesComplete" in body and "semantic" in body


def test_the_named_paths_patch_rather_than_re_read():
    for file, name in (
        ("capture-ask.js", "saveEntry"),
        ("capture-ask.js", "saveEntryAsDraft"),
        ("capture-ask.js", "watchFiling"),
        ("note-cards.js", "binNoteWithUndo"),
        ("entry-card.js", "publishDraft"),  # moved with its only callers (boot gzip budget)
        ("status.js", "pushEntryPutUndo"),
        ("selection.js", "appendSelectionToNote"),
    ):
        body = _code(_function(file, name))
        assert "refreshEntries([" in body, f"{file} {name} does not patch"
        assert "loadEntries()" not in body, f"{file} {name} still re-reads the notebook"


#: Full re-reads of the notebook left in the frontend (`loadEntries()` call
#: sites, comments excluded, `refreshEntries`'s own four fallbacks included).
#: 2026-10-05: 126 before, 82 after the first
#: pass. Only ever lowered: a new path that knows its notes calls
#: `refreshEntries([...])`.
LOAD_ENTRIES_SITES = 82


def test_full_re_reads_only_go_down():
    sites = 0
    for path in JS.glob("*.js"):
        for line in path.read_text(encoding="utf-8").split("\n"):
            stripped = line.lstrip()
            if stripped.startswith("//") or "function loadEntries" in line:
                continue
            sites += line.count("loadEntries()")
    assert sites <= LOAD_ENTRIES_SITES, (
        f"{sites} full re-reads of the notebook (cap {LOAD_ENTRIES_SITES}): "
        "a change that knows which notes it touched calls refreshEntries([...])"
    )
