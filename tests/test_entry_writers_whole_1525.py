"""Every writer of a note's text reads the whole note first, per function (INBOX 1525, and its review).

The Notes list asks for `preview=300`, so a row in `allEntries` can hold only
a note's first 300 characters (`content_truncated`). A write of that text cuts
the note. The first version of this lint passed per file (`"fullEntry(" in
text`) and only saw a PUT whose literal body said `content`; a body in a
variable, an undo store and `POST /entries` (Duplicate) went unseen.

Now every write that can carry a note's text (a `PUT /entries/{id}` or a
`POST /entries` whose body is not a literal free of `content`, and every
undo store given a body with text or a body in a variable) is placed in the
innermost function around it. That function reads the whole note itself
(`fullEntry(`, or a `GET /entries/{id}` of its own), or the write is listed in
ALLOWED under its nearest named function, with the reason it is safe. A new
writer fails here until it does one or the other; an entry nothing matches
any more fails too, so the list cannot rot.
"""

from __future__ import annotations

import re
from pathlib import Path

from tests._js_functions import function_spans

JS = Path(__file__).resolve().parent.parent / "frontend" / "js"

#: `file:function` -> why its write carries whole text without its own read beside it.
_NEW = "a new note from text typed, heard, read or answered here, never from a row"
ALLOWED = {
    #: A map's note node (wbMapOpenNote.save): `before` and the box were filled by wbMapOpenNote.load's whole
    #: `/entries/{id}` read, and the box stays read-only until that read lands, so `after` is the whole note edited.
    "whiteboard-map.js:<top>": "wbMapOpenNote.save writes the box wbMapOpenNote.load filled from the whole note, read-only until it lands",
    #: The writers' own plumbing: what they store is checked at every caller.
    "status.js:pushEntryPutUndo": "the undo store itself replays the bodies its callers gave it",
    "undo-kit.js:putEach": "pushEntriesPutUndo replays the bodies its callers gave it",
    "quick-note.js:flushNoteOutbox": "sends edits the editor queued from the whole text while offline",
    "quick-note.js:createNoteSafely": "the create path every new note goes through; its callers pass fresh text",
    "documents-prose.js:docSelectionToNote": "its POST makes a new note from the selection (nothing to lose); the Add to note path reads the note whole first",
    "skills.js:batchPut": "its callers pass flag bodies only ({pinned}, {is_draft}), never content",
    "graph-canvas.js:gcWireSelectionDock": "the undo list holds tag bodies only, built just above it",
    #: Edits of text read whole somewhere this lint cannot follow.
    "connections.js:linkNoteMention": "reads the source whole by GET sourcePath before and after the link",
    "selection.js:appendSelectionToNote": "pickEntryDialog resolves the chosen note through fullEntry",
    "graph.js:saveGraphPopup": "the popup text is loaded by GET /entries/{id}?open=1 in openGraphPopup",
    #: New notes: the text is the person's, not a clipped row's.
    "ask-compose.js:digestOffer": _NEW,
    "capture-ask.js:saveEntry": _NEW,
    "capture-ask.js:saveEntryAsDraft": _NEW,
    "chat-edit.js:chatTooLong": _NEW,
    "editor.js:offerToCreateWikiTarget": _NEW,
    "graph-canvas.js:gcWriteUnresolved": _NEW,
    "graph.js:saveGraphNewNote": _NEW,
    "library.js:<top>": _NEW,
    "entry-card.js:renderInlineAction": _NEW,
    "media.js:saveSketch": _NEW,
    "whiteboard-convert.js:cvKeepEmf": "a new note made to hold an imported EMF file, its text only the file's name",
    "meetings.js:saveVoiceNoteText": _NEW,
    "meetings.js:transcribeRecording": _NEW,
    "note-properties.js:openNoteTypesSheet": _NEW,
    "quick-note.js:saveChatAnswerAsNote": _NEW,
    "selection.js:saveSelectionAsNote": _NEW,
    "web-clip.js:saveWebPageAsNote": _NEW,
}

SINKS = [
    ("PUT", re.compile(r"`/entries/\$\{[^}`]+\}`\s*,\s*\{\s*method:\s*\"PUT\"")),
    ("POST", re.compile(r"api(?:Json)?\(\s*\"/entries\"\s*,\s*\{\s*method:\s*\"POST\"")),
    ("undo", re.compile(r"(?<![\w$.])(?:pushEntryPutUndo|pushEntriesPutUndo|pushRequestUndo)\(")),
]
#: A read of the whole note: `fullEntry(`, or `api`/`apiJson` of `/entries/${id}` with no method.
WHOLE = re.compile(r"(?<![\w$.])fullEntry\(|api(?:Json)?\(\s*`/entries/\$\{[^}`]+\}(?:\?[^`]*)?`\s*(?:\)|,\s*\{(?![^}]*method))")


def _close(text: str, at: int, opener: str, closer: str) -> int:
    level = 0
    for k in range(at, len(text)):
        level += {opener: 1, closer: -1}.get(text[k], 0)
        if level == 0 and text[k] == closer:
            return k
    return len(text)


def _top_level(source: str, separators: str) -> list[int]:
    """Offsets of `separators` outside any bracket, string or template in `source`."""
    depth, quote, found = 0, "", []
    for k, c in enumerate(source):
        if quote:
            quote = "" if c == quote and source[k - 1] != "\\" else quote
        elif c in "\"'`":
            quote = c
        elif c in "([{":
            depth += 1
        elif c in ")]}":
            depth -= 1
        elif depth == 0 and c in separators:
            found.append(k)
    return found


def _object_carries(arg: str) -> bool:
    """A body that can hold a note's text: anything but an object literal, or one with a `content` key or a spread."""
    arg = arg.strip()
    if not (arg.startswith("{") and arg.endswith("}")):
        return True
    inner = arg[1:-1]
    cuts = [-1, *_top_level(inner, ","), len(inner)]
    members = [inner[a + 1 : b].strip() for a, b in zip(cuts, cuts[1:])]
    #: `content: "New note"`, a string literal, is no row's text.
    text = (re.match(r"[\"']?content[\"']?\s*(?::\s*(.*)|$)", m, re.S) for m in members)
    literal = re.compile(r"\"[^\"\\]*\"|'[^'\\]*'")
    return any(m.startswith("...") for m in members) or any(t and not literal.fullmatch((t.group(1) or "").strip()) for t in text)


def _args(text: str, paren: int) -> list[str]:
    inner = text[paren + 1 : _close(text, paren, "(", ")")]
    cuts = [-1, *_top_level(inner, ","), len(inner)]
    return [inner[a + 1 : b].strip() for a, b in zip(cuts, cuts[1:])]


#: The undo stores and which of their arguments are note bodies (`pushRequestUndo`'s path decides it is a note).
UNDO_BODIES = {"pushEntryPutUndo": (2, 3), "pushEntriesPutUndo": (1,), "pushRequestUndo": (3, 4)}


def _carries_text(text: str, start: int, end: int, kind: str) -> bool:
    """A body in a variable, a spread, or a literal naming `content` can carry a note's text."""
    if kind in ("PUT", "POST"):
        brace = text.rindex("{", start, end)  # the options object the match ends inside
        options = text[brace : _close(text, brace, "{", "}") + 1]
        body = re.search(r"body:\s*JSON\.stringify\(", options)
        return bool(body) and _object_carries(_args(options, body.end() - 1)[0])
    name = text[start : text.index("(", start)]
    args = _args(text, text.index("(", start))
    if name == "pushRequestUndo" and len(args) > 1 and re.search(r"[`\"']", args[1]) and "/entries/" not in args[1]:
        return False  # a conversation, a file or a document, not a note
    if name == "pushEntriesPutUndo":
        return True  # a list of bodies, never a literal one
    return any(_object_carries(args[i]) for i in UNDO_BODIES[name] if i < len(args))


def _writers_in(name: str, text: str) -> list[tuple[str, str, bool]]:
    """(`file:function`, `file:line kind`, reads the whole note first) for every text write in one file."""
    hits = [(kind, m.start(), m.end()) for kind, pattern in SINKS for m in pattern.finditer(text)]
    hits = [(kind, at) for kind, at, end in hits if not text[max(0, at - 9) : at].endswith("function ") and _carries_text(text, at, end, kind)]
    if not hits:
        return []
    spans = function_spans(text)
    #: Each whole read, with the function it runs in (a read inside a sibling callback does not count).
    read_in = [(m.start(), _innermost(spans, m.start())) for m in WHOLE.finditer(text)]
    found = []
    for kind, at in hits:
        around = _around(spans, at)
        named = next((s[2] for s in around if s[2] != "arrow"), "<top>")
        #: Safe when the whole note is read before the write, in its own function or one it is a closure of.
        reads = any(r < at and fn in around for r, fn in read_in)
        found.append((f"{name}:{named}", f"{name}:{text.count(chr(10), 0, at) + 1} {kind}", reads))
    return found


def writers() -> list[tuple[str, str, bool]]:
    return [row for path in sorted(JS.glob("*.js")) for row in _writers_in(path.name, path.read_text(encoding="utf-8"))]


def _around(spans: list, at: int) -> list:
    return sorted((s for s in spans if s[0] < at < s[1]), key=lambda s: s[1] - s[0]) or [(0, 10**9, "<top>")]


def _innermost(spans: list, at: int):
    return _around(spans, at)[0]


def test_every_write_of_a_notes_text_reads_the_whole_note_in_its_own_function():
    unread = sorted({f"{line} in {key}" for key, line, reads in writers() if not reads and key not in ALLOWED})
    assert not unread, "these write a note's text with no whole read in their own function: read it (`fullEntry`) or list the function in ALLOWED with why it is safe: " + "; ".join(unread)


def test_every_allowed_writer_still_exists_and_needs_its_entry():
    needed = {key for key, _line, reads in writers() if not reads}
    stale = sorted(set(ALLOWED) - needed)
    assert not stale, f"ALLOWED entries no write needs any more (remove them): {stale}"
    assert all(len(reason) > 20 for reason in ALLOWED.values())


def test_the_probe_sees_the_shapes_the_first_lint_missed():
    """The review's cases, as the first lint saw them: a body in a variable, an undo store, a POST copy."""
    text = (
        "function save(entry) {\n  const after = { content: entry.content };\n"
        "  await api(`/entries/${entry.id}`, { method: \"PUT\", body: JSON.stringify(after) });\n}\n"
        "function dup(entry) {\n  apiJson(\"/entries\", { method: \"POST\", body: JSON.stringify({ content: entry.content }) });\n}\n"
        "function made() {\n  apiJson(\"/entries\", { method: \"POST\", body: JSON.stringify({ content: \"New note\" }) });\n}\n"
        "function undoIt(entry) {\n  pushEntryPutUndo(entry.id, \"x\", { content: was }, { content: now });\n}\n"
        "function tag(entry) {\n  await api(`/entries/${entry.id}`, { method: \"PUT\", body: JSON.stringify({ tags: [] }) });\n}\n"
        "async function whole(entry) {\n  const got = await fullEntry(entry.id);\n"
        "  await api(`/entries/${entry.id}`, { method: \"PUT\", body: JSON.stringify({ content: got.content }) });\n}\n"
        #: A closure of a function that read the note first is safe; a read in a sibling callback is not.
        "async function later(entry) {\n  const got = await fullEntry(entry.id);\n"
        "  pushUndo(\"x\", () => api(`/entries/${entry.id}`, { method: \"PUT\", body: JSON.stringify(got) }));\n}\n"
        "async function sibling(entry) {\n  const fill = () => { return fullEntry(entry.id); };\n"
        "  const put = () => api(`/entries/${entry.id}`, { method: \"PUT\", body: JSON.stringify(entry) });\n}\n"
    )
    seen = {key.split(":")[1]: reads for key, _line, reads in _writers_in("probe.js", text)}
    assert seen == {"save": False, "dup": False, "undoIt": False, "whole": True, "later": True, "sibling": False}


def test_the_list_asks_for_the_preview_and_the_screens_read_the_flag_and_the_server_numbers():
    files = {path.name: path.read_text(encoding="utf-8") for path in JS.glob("*.js")}
    assert files["notes-list.js"].count("preview=300") >= 2  # the page read and the by-id refresh
    assert "preview=300" in files["notes-lazy.js"]  # the Semantic list
    #: The clamp: a clipped row is long whatever its 300 characters look like.
    assert "entry.content_truncated" in files["entry-card.js"]
    #: The dashboard counts words and open tasks on the server, over the whole text.
    dash = files["dashboard.js"]
    assert "entry.word_count ??" in dash and "entry.tasks_open ??" in dash and "entry.tasks_done ??" in dash
