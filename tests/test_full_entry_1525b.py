"""`fullEntry` after the INBOX 1525 review: callers use what it returns, and it reaches every note by id.

The Notes list holds each note's first 300 characters. A writer that awaited
`fullEntry` and then sent its own row's text saved 300 characters whenever a
list refresh had swapped that row for a new, clipped one meanwhile (the image
remove on a card). And `fullEntry` read `/entries?ids=`, which leaves out
archived notes, so "Link" on an archived backlink said the note was gone.
"""

from __future__ import annotations

import json
import re
import shutil
import subprocess
from pathlib import Path

import pytest

JS = Path(__file__).resolve().parent.parent / "frontend" / "js"


def _full_entry_source() -> str:
    text = (JS / "notes-lazy.js").read_text(encoding="utf-8")
    start = text.index("function fullEntry(")
    return text[start : text.index("\n};\n", start) + 4]


def _run(prelude: str, body: str) -> dict:
    script = f"""
let allEntries = [];
const asked = [];
{prelude}
{_full_entry_source()}
(async () => {{ const out = {{}}; {body}; process.stdout.write(JSON.stringify(out)); }})();
"""
    done = subprocess.run(["node", "-e", script], capture_output=True, text=True, timeout=30)
    assert done.returncode == 0, done.stderr
    return json.loads(done.stdout)


NOTES = """
const whole = { 1: "one whole", 2: "two whole", 3: "three archived whole", 7: "seven whole" };
const archived = new Set([3]);
async function apiJson(path) {
  asked.push(path);
  await new Promise((r) => setTimeout(r, 5));
  const many = /^\\/entries\\?ids=([\\d,]+)&boards=include$/.exec(path);
  if (many) return many[1].split(",").map(Number).filter((id) => whole[id] && !archived.has(id)).map((id) => ({ id, content: whole[id], content_truncated: false }));
  const one = /^\\/entries\\/(\\d+)$/.exec(path);
  if (one && whole[one[1]]) return { id: Number(one[1]), content: whole[one[1]], content_truncated: false };
  throw new Error("That note could not be found.");
}
"""

needs_node = pytest.mark.skipif(not shutil.which("node"), reason="needs node")


@needs_node
def test_the_answer_is_whole_even_when_the_row_was_replaced_while_it_was_asked():
    out = _run(NOTES, """
      const held = { id: 7, content: "seven", content_truncated: true };
      allEntries = [held];
      const asking = fullEntry(7);
      allEntries = [{ id: 7, content: "seven", content_truncated: true }];  // a list refresh
      const got = await asking;
      out.content = got.content; out.isHeld = got === held; out.isRow = got === allEntries[0];
      out.asked = asked;
    """)
    assert out["content"] == "seven whole"
    assert out["isRow"] and not out["isHeld"]  # the row on screen now is the one made whole
    assert out["asked"] == ["/entries/7"]  # by id: archived notes and boards answer too


@needs_node
def test_asks_in_one_tick_go_as_one_request_and_an_archived_note_is_read_by_id():
    out = _run(NOTES, """
      allEntries = [1, 2, 3].map((id) => ({ id, content: "x", content_truncated: true }));
      const got = await Promise.all([fullEntry(1), fullEntry(2), fullEntry(3), fullEntry(1)]);
      out.contents = got.map((e) => e.content); out.asked = asked;
    """)
    assert out["contents"] == ["one whole", "two whole", "three archived whole", "one whole"]
    assert out["asked"] == ["/entries?ids=1,2,3&boards=include", "/entries/3"]


@needs_node
def test_a_whole_row_is_not_asked_for_and_a_gone_note_rejects_with_the_reason():
    out = _run(NOTES, """
      allEntries = [{ id: 1, content: "short", content_truncated: false }];
      out.same = (await fullEntry(1)) === allEntries[0];
      out.error = await fullEntry(99).then(() => "", (e) => e.message);
      out.asked = asked;
    """)
    assert out["same"] and out["error"] == "That note could not be found." and out["asked"] == ["/entries/99"]


#: `fullEntry(...)` whose answer is thrown away: `.then(() =>`, `.then(() => true`, or `await fullEntry(x);` alone.
DISCARDED = re.compile(r"fullEntry\([^()]*\)\.then\(\s*\(\)\s*=>|(?:^|[;{]\s*)await fullEntry\([^()]*\)\s*;", re.M)


def test_no_caller_throws_the_whole_note_away_and_reads_its_own_row():
    found = [
        f"{path.name}:{text[: m.start()].count(chr(10)) + 1}"
        for path in sorted(JS.glob("*.js"))
        for text in [path.read_text(encoding="utf-8")]
        for m in DISCARDED.finditer(text)
    ]
    assert not found, f"use the note fullEntry returns, not the row you held: {found}"


def _function(text: str, head: str) -> str:
    start = text.index(head)
    return text[start : text.index("\n}\n", start)]


def test_a_card_drawn_open_from_a_clipped_row_fills_itself_with_the_whole_note():
    """INBOX 1525 review, items 3 and 4: one way to the whole text for every opened card (cards, rows, the phone page).

    Measured (fix1525 sweep, port 8796): a 2,314-character note's list row holds 272; opened by Show more and then
    redrawn, by the row chevron and then reloaded, and as the phone note page, each shows all 2,314 with its end word.
    """
    card = _function((JS / "entry-card.js").read_text(encoding="utf-8"), "function entryItem(")
    #: Keyed on how the card was drawn: `fullEntry` fills the shared row in place, so a row another reader filled
    #: first (Copy, the editor, a cited passage) no longer says clipped while this card still shows 300 characters.
    assert "let clipped = entry.content_truncated;" in card
    assert "content.fillWhole = () => clipped && (content.whole ||= fullEntry(entry.id).then((whole) => {" in card
    assert "entry = whole;" in card  # the card's menus and Copy read the whole note too
    assert "if (expandedNotes.has(entry.id) || expandedRows.has(entry.id)) content.fillWhole();" in card
    assert "if (expandedNotes.has(entry.id)) content.fillWhole();" in card  # the Show more press
    toggle = _function((JS / "notes-lazy.js").read_text(encoding="utf-8"), "function toggleRowExpanded(")
    #: The row's text is filled in place, never swapped for a new element its Show more is not bound to.
    assert "replaceWith" not in toggle and '.querySelector(".entry-content")?.fillWhole?.()' in toggle
    page = _function((JS / "phone-shell.js").read_text(encoding="utf-8"), "function dropRepeatedTitle(")
    assert '"note-whole"' in page
