"""Block references parse and write the way the plan's decision says.

DOCUMENTS_PLAN Phase 4 item 2. The model lives between `DOC-BLOCKREF-BEGIN`
and `DOC-BLOCKREF-END` in documents.js and is pure string work with no DOM and
no app globals in it, so python can run it in node. That is a property this
test enforces by existing, the same way the table, frontmatter and columns
models are tested.

What matters here is not the happy case. It is that the shapes around it do
not silently become block ids: a `^` in prose ("2^31") is arithmetic, a `^id`
inside a code fence is an example of the syntax rather than a use of it, and a
link written yesterday has to keep resolving, which means an id is never
regenerated for a block that has one.
"""

from __future__ import annotations
from tests._app_js import frontend_text

import json
import shutil
import subprocess
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
DOCUMENTS_JS = ROOT / "frontend" / "js" / "documents.js"

BEGIN = "// DOC-BLOCKREF-BEGIN"
END = "// DOC-BLOCKREF-END"
SYNCED_JS = ROOT / "frontend" / "js" / "documents-synced.js"


def blockref_source() -> str:
    text = frontend_text("documents.js")
    start = text.find(BEGIN)
    stop = text.find(END)
    assert start != -1, f"{BEGIN} marker is missing from documents.js"
    assert stop > start, f"{END} marker is missing or before {BEGIN}"
    return text[start + len(BEGIN) : stop]


def synced_source() -> str:
    """The synced-block model (documents-synced.js), which reads the block-reference helpers above it."""
    text = SYNCED_JS.read_text(encoding="utf-8")
    start = text.index("// DOC-SYNCED-BEGIN")
    return text[start : text.index("// DOC-SYNCED-END")]


DRIVER = r"""
const results = [];
function check(name, ok, detail) {
  results.push({ name, ok: !!ok, detail: detail === undefined ? null : detail });
}
// A generator with no randomness in it, so every assertion below is exact.
let counter = 0;
const fixedIds = ['aaaaaa', 'bbbbbb', 'cccccc'];
const fixed = () => {
  const id = fixedIds[Math.min(counter, fixedIds.length - 1)];
  counter++;
  return parseInt(id, 36) / 36 ** 6;
};

// --- splitting a reference -------------------------------------------------
{
  const cases = [
    ['Design notes', { name: 'Design notes', blockId: null }],
    ['Design notes#^abc123', { name: 'Design notes', blockId: 'abc123' }],
    ['  Design notes  #^abc123 ', { name: 'Design notes', blockId: 'abc123' }],
    ['Design notes#^', { name: 'Design notes', blockId: null }],
    ['Design notes#^not an id', { name: 'Design notes', blockId: null }],
    ['#^abc123', { name: '', blockId: 'abc123' }],
    ['', { name: '', blockId: null }],
  ];
  for (const [spec, want] of cases) {
    const got = docBlockRefSplit(spec);
    check(`split/${spec}/name`, got.name === want.name, got.name);
    check(`split/${spec}/id`, got.blockId === want.blockId, String(got.blockId));
  }
}

// --- what a block is -------------------------------------------------------
{
  const text = [
    '# A heading',            // 0
    '',
    'One paragraph line.',    // 2
    'Its second line.',       // 3
    '',
    '- first item',           // 5
    '- second item',          // 6
    '',
    '```',                    // 8
    'code ^notanid',          // 9
    '```',                    // 10
  ].join('\n');
  const at = (line, col) => {
    const lines = text.split('\n');
    let pos = 0;
    for (let i = 0; i < line; i++) pos += lines[i].length + 1;
    return pos + (col || 0);
  };
  const para = docBlockBounds(text, at(2, 3));
  check('bounds/paragraph joins its lines', text.slice(para.from, para.to) === 'One paragraph line.\nIts second line.', text.slice(para.from, para.to));
  check('bounds/the last line is the id line', text.slice(para.lastFrom, para.lastTo) === 'Its second line.', text.slice(para.lastFrom, para.lastTo));
  const item = docBlockBounds(text, at(6, 3));
  check('bounds/a list item is its own block', text.slice(item.from, item.to) === '- second item', text.slice(item.from, item.to));
  check('bounds/a blank line has no block', docBlockBounds(text, at(1, 0)) === null, '');
  check('bounds/inside a fence has no block', docBlockBounds(text, at(9, 2)) === null, '');
  const heading = docBlockBounds(text, at(0, 2));
  check('bounds/a heading is a block of its own', text.slice(heading.from, heading.to) === '# A heading', text.slice(heading.from, heading.to));
}

// --- giving a block an id --------------------------------------------------
{
  counter = 0;
  const text = 'One paragraph line.\nIts second line.\n\nAnother.';
  const first = docBlockEnsureIdEdits(text, 3, fixed);
  check('ensure/an id is added', first.reason === 'added', first.reason);
  check('ensure/one edit only', first.edits.length === 1, String(first.edits.length));
  const applied = text.slice(0, first.edits[0].from) + first.edits[0].insert + text.slice(first.edits[0].to);
  check('ensure/it lands at the end of the last line', applied === 'One paragraph line.\nIts second line. ^aaaaaa\n\nAnother.', JSON.stringify(applied));
  check('ensure/and nothing else moved', applied.replace(' ^aaaaaa', '') === text, JSON.stringify(applied));

  const again = docBlockEnsureIdEdits(applied, 3, fixed);
  check('ensure/a block that has one keeps it', again.id === 'aaaaaa' && again.edits.length === 0, `${again.id}/${again.reason}`);

  const blank = docBlockEnsureIdEdits('para\n\n', 5, fixed);
  check('ensure/a blank line refuses', blank.reason === 'no-block' && blank.id === null, blank.reason);

  // Two trailing spaces are a markdown hard break: the id must not move it.
  counter = 1;
  const hard = 'A line with a break  \nnext line.';
  const edits = docBlockEnsureIdEdits(hard, 2, fixed).edits;
  const after = hard.slice(0, edits[0].from) + edits[0].insert + hard.slice(edits[0].to);
  check('ensure/a hard break is not padded around', after === 'A line with a break  \nnext line. ^bbbbbb', JSON.stringify(after));
}

// --- collisions ------------------------------------------------------------
{
  counter = 0;
  const text = 'first ^aaaaaa\n\nsecond';
  const made = docBlockEnsureIdEdits(text, text.length - 1, fixed);
  check('ids/a taken id is not handed out twice', made.id === 'bbbbbb', String(made.id));
  const ids = docBlockIds('one ^abc123\ntwo\nthree ^def456\n');
  check('ids/every id in the text is seen', ids.size === 2 && ids.has('abc123') && ids.has('def456'), String(ids.size));
}

// --- finding a block by its id ---------------------------------------------
{
  const text = [
    '# Doc',
    '',
    'The block we want.',
    'Its second line. ^abc123',
    '',
    'Another block.',
    '',
    '```',
    'not the block ^abc123',
    '```',
  ].join('\n');
  const found = docBlockFind(text, 'abc123');
  check('find/the whole block comes back', found.text === 'The block we want.\nIts second line.', JSON.stringify(found && found.text));
  check('find/the marker is not part of it', !found.text.includes('^abc123'), found.text);
  check('find/the span is the block in the document', text.slice(found.from, found.to).startsWith('The block we want.'), '');
  check('find/an id nobody carries is null', docBlockFind(text, 'zzzzzz') === null, '');
  check('find/an id that is not an id is null', docBlockFind(text, 'not an id') === null, '');
}

// --- the shapes that are not block ids -------------------------------------
{
  const cases = [
    ['2^31 is a big number.', 'arithmetic'],
    ['x ^ y is a caret.', 'a bare caret'],
    ['A line ending in ^ nothing else', 'a caret not at the end'],
    ['trailing ^UPPER-case-ok', null],
  ];
  for (const [line, why] of cases) {
    const bounds = docBlockBounds(line, 1);
    const id = docBlockIdOf(line, bounds);
    if (why === null) check(`notid/${line}`, id !== null && id.id === 'UPPER-case-ok', String(id && id.id));
    else check(`notid/${why}`, id === null, String(id && id.id));
  }
}

// --- the reader's copy has no markers in it --------------------------------
{
  const text = [
    'A paragraph. ^abc123',
    '',
    'Another one.',
    '',
    '```',
    'shell ^keepme',
    '```',
    '',
    'A link to [[Doc#^abc123]] keeps its reference.',
  ].join('\n');
  const stripped = docBlockStripIds(text);
  check('strip/the marker is gone', !stripped.includes('^abc123\n') && stripped.startsWith('A paragraph.\n'), JSON.stringify(stripped.split('\n')[0]));
  check('strip/a fence is left alone', stripped.includes('shell ^keepme'), '');
  check('strip/a reference in prose is not a marker', stripped.includes('[[Doc#^abc123]]'), '');
  check('strip/nothing else changed', stripped.replace(' ^abc123', '') === text.replace(' ^abc123', ''), '');
  check('strip/empty text is empty', docBlockStripIds(null) === '', JSON.stringify(docBlockStripIds(null)));
}

// --- a synced block: rewriting the block an id names (DOCUMENTS_PLAN 26) ----
{
  const text = 'Intro.\n\nFirst line.\nSecond line. ^abc123\n\nTail ^other';
  const next = replace(text, 'abc123', 'Rewritten.');
  check('replace/the block is swapped and keeps its id', next === 'Intro.\n\nRewritten. ^abc123\n\nTail ^other', JSON.stringify(next));
  const two = replace(text, 'abc123', 'New one.\nNew two.  \n');
  check('replace/lines stay lines, the trailing space goes', two === 'Intro.\n\nNew one.\nNew two. ^abc123\n\nTail ^other', JSON.stringify(two));
  check('replace/an id nothing carries refuses', replace(text, 'zzzzzz', 'x') === null, '');
  check('replace/an empty block refuses', replace(text, 'abc123', '  \n') === null, '');
  check('replace/a blank line would make two blocks, so it refuses', replace(text, 'abc123', 'One.\n\nTwo.') === null, '');
  check('replace/the same text changes nothing', replace(text, 'abc123', 'First line.\nSecond line.') === text, '');
  const code = '```\nlet a ^abc123\n```\n\nReal ^abc123';
  const fenced = replace(code, 'abc123', 'Changed.');
  check('replace/an id in a fence is an example, not the block', fenced === '```\nlet a ^abc123\n```\n\nChanged. ^abc123', JSON.stringify(fenced));
}

process.stdout.write(JSON.stringify(results));
"""


@pytest.fixture(scope="module")
def blockref_checks(tmp_path_factory) -> list[dict]:
    node = shutil.which("node")
    if not node:  # pragma: no cover - node is in the sandbox and in CI
        pytest.skip("node is not available")
    script = tmp_path_factory.mktemp("docblockrefs") / "run.js"
    script.write_text(blockref_source() + "\nvar window = { docBlockFind };\n" + synced_source() + DRIVER, encoding="utf-8")
    out = subprocess.run(
        [node, str(script)], capture_output=True, text=True, timeout=60, check=False
    )
    assert out.returncode == 0, out.stderr
    return json.loads(out.stdout)


def test_the_model_runs_without_a_browser(blockref_checks: list[dict]) -> None:
    assert len(blockref_checks) > 30, "the driver did not reach the end"


def test_block_references_parse_and_write_as_decided(blockref_checks: list[dict]) -> None:
    failed = [c for c in blockref_checks if not c["ok"]]
    assert not failed, "\n".join(f"{c['name']}: {c['detail']}" for c in failed[:20])


def test_a_synced_block_is_edited_through_a_lazy_module_the_embed_asks_for() -> None:
    embeds = (ROOT / "frontend" / "js" / "documents-embeds.js").read_text(encoding="utf-8")
    cm = (ROOT / "frontend" / "js" / "documents-cm.js").read_text(encoding="utf-8")
    synced = SYNCED_JS.read_text(encoding="utf-8")
    # The pencil is on a block from another document only; its press loads the module, which is not a boot script.
    assert 'ensureModule("docSynced")' in embeds and "currentDoc?.id !== target.doc.id" in embeds
    assert 'docSynced: ["/js/documents-synced.js"]' in (ROOT / "frontend" / "js" / "lazy-entries.js").read_text(encoding="utf-8")
    # Save goes through the document's own guarded save, so it has history and refuses a stale write.
    assert 'method: "PUT"' in synced and "base_hash: hash" in synced
    assert "writeSource(target.doc.id, source.content_hash, next, cache)" in synced, "the write carries the hash of the text the box opened on"
    # The save is one step on the undo stack, with a redo, each a guarded write of the whole document (the undo contract).
    assert "window.offerUndo(" in synced and "() => move(before)" in synced and "() => move(after)" in synced
    # The redraw after Save or Cancel is handed in by the embed (docEmbedNode is private to its file, so a reference to it threw).
    assert "draw: () => docEmbedNode(target, name)" in embeds and "docEmbedNode" not in synced.replace("`docEmbedNode`", "")
    # A block changed elsewhere since the box opened is refused, not overwritten.
    assert ".text !== text" in synced
    # A click in the box must not fall through to the Live widget's "open the document".
    assert '"button, a, input, textarea"' in cm


def test_the_guide_has_a_topic_and_a_lead_for_a_synced_block() -> None:
    from tessellate.ai import help_chat, help_leads

    topics = {t["id"]: t for t in help_chat.HELP_TOPICS}
    assert "document-synced" in topics and len(topics["document-synced"]["body"]) < 1900
    assert "document-synced" in help_leads.TOPIC_LEADS
    assert "pencil" in topics["document-synced"]["body"]


# --- decision 82 a, b, c (L-documents-69 to 71): a copy that reads as one, the pencil at home, live refresh ----------------


def _doc(client, title: str, content: str) -> dict:
    return client.post("/documents", json={"title": title, "content": content}).json()


def test_block_uses_counts_the_places_a_block_is_embedded_or_linked(client) -> None:
    source = _doc(client, "Source doc", "A line to share ^abc123\n\nAnother ^zzz999\n")
    _doc(client, "Reader one", "Here: ![[Source doc#^abc123]]\n\nand [[Source doc#^abc123|again]]")
    client.post("/entries", json={"content": "A note: ![[source doc#^zzz999]] and [[Other#^abc123]]"})
    uses = client.get(f"/documents/{source['id']}/block-uses").json()["uses"]
    assert uses == {"abc123": 2, "zzz999": 1}
    assert client.get("/documents/999999/block-uses").status_code == 404


def test_block_uses_ignores_its_own_text_and_an_untitled_document(client) -> None:
    own = _doc(client, "Alone", "Mentions itself ![[Alone#^abc123]] ^abc123")
    assert client.get(f"/documents/{own['id']}/block-uses").json() == {"uses": {}}
    blank = _doc(client, "Soon blank", "text ^abc123")
    client.put(f"/documents/{blank['id']}", json={"title": "   "})
    assert client.get(f"/documents/{blank['id']}/block-uses").json() == {"uses": {}}


def test_a_block_is_copied_as_an_embed_and_pasted_by_the_slash_menu() -> None:
    js = frontend_text("documents.js")
    piece = (ROOT / "frontend" / "js" / "documents-blockref.js").read_text(encoding="utf-8")
    editor = (ROOT / "frontend" / "js" / "editor.js").read_text(encoding="utf-8")
    # One id, written once into the block; the embed is the same reference with a bang, kept for the paste in another document.
    assert 'const reference = `${synced ? "!" : ""}[[${title}#^${made.id}]]`' in piece
    assert 'prefs.set("doc-synced-clip", reference)' in piece and 'prefs.get("doc-synced-clip", "")' in piece
    assert 'id: "syncedcopy"' in editor and 'id: "syncedpaste"' in editor
    assert 'action.custom === "syncedpaste"' in js and '"paste"' in js and 'if (mode === "paste") return docPasteSyncedBlock()' in piece
    # The embed reads as a copy: pressing its text opens the same box as the pencil.
    embeds = (ROOT / "frontend" / "js" / "documents-embeds.js").read_text(encoding="utf-8")
    assert 'body.addEventListener("click"' in embeds and "edit.click()" in embeds


def test_the_block_in_its_own_document_carries_a_pencil_with_the_count() -> None:
    cm = (ROOT / "frontend" / "js" / "documents-cm.js").read_text(encoding="utf-8")
    synced = SYNCED_JS.read_text(encoding="utf-8")
    assert "/block-uses" in cm and "class DocBlockUseWidget" in cm and "new DocBlockUseWidget(match[1])" in cm
    assert 'ensureModule("docSynced")' in cm and '"synced-own"' in cm
    # The box there writes into the open editor (never a PUT over the text being typed) and is refused on a changed or split block.
    assert 'document.addEventListener("synced-own"' in synced and "docTableDispatch({ surface, text }" in synced and "markDocDirty()" in synced
    assert "own.save(text, area.value)" in synced


def test_a_synced_save_redraws_the_other_places_that_show_the_document() -> None:
    synced = SYNCED_JS.read_text(encoding="utf-8")
    embeds = (ROOT / "frontend" / "js" / "documents-embeds.js").read_text(encoding="utf-8")
    assert 'new BroadcastChannel("memorymap-doc-synced")' in synced and "channel?.postMessage({ id })" in synced
    assert '"synced-saved"' in synced and 'document.addEventListener("synced-saved"' in embeds
    assert 'new BroadcastChannel("memorymap-doc-synced")' in embeds
    # A box with its edit box open is not redrawn under the person typing; the document being typed in is not reopened.
    assert 'box.querySelector("textarea")) continue' in embeds and "if (docDirty) toast(" in embeds
