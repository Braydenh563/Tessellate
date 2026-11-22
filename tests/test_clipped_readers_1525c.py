"""Readers that took a clipped list row for the whole note (INBOX 1525 review, item 7).

A list row holds a note's first 300 characters (`content_truncated`). A reader of
the row's text sees only that: a word count, a cited passage past character 300, a
picker's search, Copy. Each reads the whole note, or the server's answer about it.
"""

from __future__ import annotations

from tests._app_js import frontend_text
import json
import re
import shutil
import subprocess
from pathlib import Path

import pytest

JS = Path(__file__).resolve().parent.parent / "frontend" / "js"
needs_node = pytest.mark.skipif(not shutil.which("node"), reason="needs node")


def _text(name: str) -> str:
    return frontend_text(name) if name.startswith("whiteboard") else (JS / name).read_text(encoding="utf-8")


def _block(text: str, head: str, tail: str = "\n}\n") -> str:
    start = text.index(head)
    #: A script wrapped whole (row 37a) indents its functions: the close is as deep as the head.
    indent = len(text[text.rfind("\n", 0, start) + 1 : start])
    if tail == "\n}\n" and text[start - indent : start].strip() == "":
        tail = "\n" + " " * indent + "}\n"
    return text[start : text.index(tail, start) + len(tail)]


def _node(script: str) -> dict:
    done = subprocess.run(["node", "-e", script], capture_output=True, text=True, timeout=30)
    assert done.returncode == 0, done.stderr
    return json.loads(done.stdout)


def test_the_embed_card_counts_the_servers_words_not_the_previews():
    card = _block(_text("reply-kit.js"), "function replyNoteCard(")
    assert "entry?.word_count ?? (content ? wordCount(plainText(content)) : 0)" in card


@needs_node
def test_a_cited_passage_past_the_preview_is_cut_from_the_whole_note():
    whole = "x" * 300 + " the quoted passage here"
    script = f"""
const allEntries = [{{ id: 4, content: "x".repeat(300), content_truncated: true }}];
const plainText = (s) => s;
let fullEntry = async (id) => ({{ id, content: {json.dumps(whole)} }});
const marker = {{ dataset: {{ start: "301", end: "324" }} }};
const from = {{ closest: () => ({{ querySelector: () => marker }}) }};
{_block(_text("reveal-targets.js"), "async function notePassageFor(")}
(async () => {{
  const got = await notePassageFor(4, from);
  const failed = await (async () => {{ fullEntry = async () => {{ throw new Error("gone"); }}; return notePassageFor(4, from); }})();
  process.stdout.write(JSON.stringify({{ got, failed }}));
}})();
"""
    out = _node(script)
    assert out["got"] == "the quoted passage here"
    assert out["failed"] == ""  # the clipped row cannot supply it: empty, not a throw


def test_an_evidence_card_and_the_reveal_open_the_card_to_find_a_passage_past_the_preview():
    answer = _text("answer-kit.js")
    assert "if (entry?.content_truncated) fullEntry(g.note_id).then(" in answer
    reveal = _block(_text("reveal-targets.js"), "async function markNotePassage(")
    assert "await body.fillWhole?.()" in reveal


@needs_node
def test_a_picker_asks_the_server_for_a_word_and_a_failed_ask_leaves_the_local_match():
    """`noteEngine.literal` is the one ask the list, the `[[` menu and Attach notes share."""
    engine = _block(_text("notes-list.js"), "const noteEngine = {", "\n};\n")
    script = f"""
const calls = []; let answer = {{ ids: [7] }}; let redraws = 0;
const clipFor = (kind, text) => text;
const renderEntries = () => (redraws += 1);
async function apiJson(path) {{ calls.push(path); if (answer instanceof Error) throw answer; return answer; }}
{engine}
(async () => {{
  const out = {{}};
  out.first = noteEngine.literal(noteEngine.pick, "late word", () => (redraws += 10));
  await new Promise((r) => setTimeout(r, 5));
  out.landed = [...noteEngine.literal(noteEngine.pick, "late word", () => {{}})];
  out.redraws = redraws;
  answer = new Error("down");
  out.failedFirst = noteEngine.literal(noteEngine.pick, "other", () => {{}});
  await new Promise((r) => setTimeout(r, 5));
  out.failedAfter = noteEngine.literal(noteEngine.pick, "other", () => {{}});
  out.calls = calls;
  process.stdout.write(JSON.stringify(out));
}})();
"""
    out = _node(script)
    assert out["first"] is None and out["landed"] == [7] and out["redraws"] == 10
    assert out["failedFirst"] is None and out["failedAfter"] is None  # null: the caller keeps its own match
    assert all("ids_only=true" in c and "kind=note" in c for c in out["calls"]) and len(out["calls"]) == 2


def test_both_pickers_match_a_word_on_the_row_or_the_servers_ids():
    attach = _block(_text("attach-to.js"), "async function renderNotePickerList(")
    assert 'source === "notes" && query ? noteEngine.literal(noteEngine.pick, query, renderNotePickerList) : null' in attach
    assert "|| served?.has(row.id)" in attach
    editor = _text("editor.js")
    assert "noteEngine.literal(noteEngine.pick, query," in editor and "|| served?.has(e.id)" in editor
    #: The chat's Attach notes shape has no filter of its own: it rides the picker above.
    chat = _text("chat-attach.js")
    assert "noteEngine" not in chat and "shape.search" not in chat


def test_the_board_reads_a_clipped_card_through_the_batching_whole_read_only():
    board = _text("whiteboard.js")
    assert "entries?ids=" not in board  # one request per card is `fullEntry`'s batch, not the board's own call
    card = board[board.index("if (entry.content_truncated) fullEntry(entry.id).then(") :][:400]
    assert "wbScheduleCardClampSync()" in card


# --- Copy ---------------------------------------------------------------------


def _copy_script(body: str) -> dict:
    fn = _block(_text("entry-card.js"), "entryItem.copyText = async", "\n};\n").replace("entryItem.copyText", "const copyNoteText")
    return _node(
        f"""
const toasts = []; const wrote = []; let gestureOpen = true;
const toast = (m, bad) => toasts.push([m, Boolean(bad)]);
let fetchWhole = async () => ({{ content: "the whole text" }});
const fullEntry = (id) => fetchWhole(id);
async function copyToClipboard(t) {{ wrote.push(["text", t]); return true; }}
globalThis.ClipboardItem = class ClipboardItem {{ constructor(parts) {{ this.parts = parts; }} }};
const navigator = {{ clipboard: {{ async write(items) {{ const blob = await items[0].parts["text/plain"]; wrote.push(["item", await blob.text()]); }} }} }};
{fn}
(async () => {{ const out = {{}}; {body}; out.toasts = toasts; out.wrote = wrote; process.stdout.write(JSON.stringify(out)); }})();
"""
    )


@needs_node
def test_copy_of_a_whole_row_writes_the_text_and_says_so():
    out = _copy_script('await copyNoteText({ id: 1, content: "short", content_truncated: false });')
    assert out["wrote"] == [["text", "short"]] and out["toasts"] == [["Note copied.", False]]


@needs_node
def test_copy_of_a_clipped_row_hands_the_clipboard_a_promise_of_the_whole_text():
    out = _copy_script('await copyNoteText({ id: 1, content: "sho", content_truncated: true });')
    assert out["wrote"] == [["item", "the whole text"]] and out["toasts"] == [["Note copied.", False]]


@needs_node
def test_copy_of_a_clipped_row_whose_read_fails_says_why_and_does_not_throw():
    out = _copy_script(
        'fetchWhole = async () => { throw new Error("This note is no longer here."); };'
        ' await copyNoteText({ id: 1, content: "sho", content_truncated: true });'
    )
    assert out["wrote"] == [] and out["toasts"] == [["This note is no longer here.", True]]


@needs_node
def test_copy_without_clipboard_items_reads_the_whole_note_then_copies_it():
    out = _copy_script(
        "delete globalThis.ClipboardItem; navigator.clipboard.write = undefined;"
        ' await copyNoteText({ id: 1, content: "sho", content_truncated: true });'
    )
    assert out["wrote"] == [["text", "the whole text"]] and out["toasts"] == [["Note copied.", False]]


def test_copy_button_calls_the_one_copy_function():
    card = _text("entry-card.js")
    assert re.search(r'"Copy this note\'s text", \(\) => entryItem\.copyText\(entry\)\)', card)


def test_the_choose_a_note_dialog_and_the_map_chips_read_what_the_server_says_of_the_whole_text():
    dialog = _block(_text("selection.js"), "function pickEntryDialog(")
    assert "noteEngine.literal(noteEngine.pick, needle, paint)" in dialog and "served?.has(e.id)" in dialog
    chips = _block(_text("notes-list.js"), "function ensureMapChipsFor(")
    assert 'entry.wiki_linked ?? String(entry.content || "").includes("[[")' in chips


def test_the_picker_preview_reads_a_picture_past_the_rows_300_characters() -> None:
    """fix1525b found: note-pick-preview.js read a note's first picture from the clipped row."""
    body = _block(_text("note-pick-preview.js"), "function notePickThumb(")
    assert "entry.content_truncated" in body and "fullEntry(entry.id)" in body
