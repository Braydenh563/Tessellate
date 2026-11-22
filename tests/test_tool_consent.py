"""L-world-class-181: the agent asks as a turn of the chat, and an edit is a suggestion.

The confirm event says what, why and whether it removes; `edit_document` parks
like `edit_note`; the press can skip hunks of the suggested edit, numbered by
the page's own diff (`core/linediff` is its port, checked here against node).
"""

from __future__ import annotations

import json
import shutil
import subprocess

import pytest

from tessellate.ai import tools
from tessellate.core import linediff
from tests._app_js import JS_DIR


def _events(client, question):
    with client.stream("POST", "/chat/stream", json={"question": question}) as response:
        assert response.status_code == 200
        return [json.loads(line) for line in response.iter_lines() if line]


def _document(client, content):
    response = client.post("/documents", json={"title": "Trip plan", "content": content})
    assert response.status_code in (200, 201), response.text
    return response.json()


OLD = "Day one\nTrain to Leeds\nLunch\nDay two\nWalk the moor\nHome"
NEW = "Day one\nTrain to York\nLunch\nDay two\nWalk the moor\nPub supper\nHome"


def _card(client, fake_ollama, document, content=NEW):
    fake_ollama.calls(("edit_document", {"document_id": document["id"], "content": content}))
    events = _events(client, "Change Leeds to York and add a pub supper")
    return next(e for e in events if e["type"] == "confirm")


def test_edit_document_is_a_change_that_parks():
    assert "edit_document" in tools.CHANGE_TOOLS and "edit_document" in tools.WRITE_TOOLS
    assert tools.needs_confirm("edit_document", {"document_id": 1, "content": "x"})


def test_the_card_says_what_why_and_whether_it_removes(ai_client, fake_ollama):
    document = _document(ai_client, OLD)
    card = _card(ai_client, fake_ollama, document)
    assert card["name"] == "edit_document" and card["consent_id"]
    assert card["removes"] is False
    assert "Leeds to York" in card["why"]
    unchanged = ai_client.get(f"/documents/{document['id']}").json()
    assert unchanged["content"] == OLD, "nothing is written before the press"


def test_a_removal_says_it_removes(ai_client, fake_ollama):
    document = _document(ai_client, OLD)
    fake_ollama.calls(("delete_document", {"document_id": document["id"]}))
    card = next(e for e in _events(ai_client, "bin the trip plan") if e["type"] == "confirm")
    assert card["removes"] is True


def test_a_press_that_skips_a_hunk_keeps_those_lines_and_undo_restores(ai_client, fake_ollama):
    document = _document(ai_client, OLD)
    card = _card(ai_client, fake_ollama, document)
    press = {"name": card["name"], "arguments": card["arguments"], "consent_id": card["consent_id"], "skip_hunks": [1]}
    pressed = ai_client.post("/chat/tools/execute", json=press)
    assert pressed.status_code == 200, pressed.text
    saved = ai_client.get(f"/documents/{document['id']}").json()
    assert saved["content"] == "Day one\nTrain to York\nLunch\nDay two\nWalk the moor\nHome"
    undo = pressed.json()["undo"]
    undone = ai_client.post("/chat/tools/execute", json={"name": undo["tool"], "arguments": undo["arguments"]})
    assert undone.status_code == 200, undone.text
    restored = ai_client.get(f"/documents/{document['id']}").json()
    assert restored["content"] == OLD


def test_skipping_every_hunk_spends_nothing(ai_client, fake_ollama):
    document = _document(ai_client, OLD)
    card = _card(ai_client, fake_ollama, document)
    base = {"name": card["name"], "arguments": card["arguments"], "consent_id": card["consent_id"]}
    every = ai_client.post("/chat/tools/execute", json={**base, "skip_hunks": [0, 1]})
    assert every.status_code == 400
    beyond = ai_client.post("/chat/tools/execute", json={**base, "skip_hunks": [5]})
    assert beyond.status_code == 400
    whole = ai_client.post("/chat/tools/execute", json=base)
    assert whole.status_code == 200, "a refused narrowing leaves the card pressable"
    saved = ai_client.get(f"/documents/{document['id']}").json()
    assert saved["content"] == NEW


def test_skipping_needs_the_card(ai_client):
    document = _document(ai_client, OLD)
    bare = ai_client.post("/chat/tools/execute", json={"name": "edit_document", "arguments": {"document_id": document["id"], "content": NEW}, "skip_hunks": [0]})
    assert bare.status_code == 400
    saved = ai_client.get(f"/documents/{document['id']}").json()
    assert saved["content"] == OLD


def test_the_old_text_goes_into_the_document_history(ai_client, fake_ollama):
    document = _document(ai_client, OLD)
    card = _card(ai_client, fake_ollama, document)
    ai_client.post("/chat/tools/execute", json={"name": card["name"], "arguments": card["arguments"], "consent_id": card["consent_id"]})
    revisions = ai_client.get(f"/documents/{document['id']}/revisions").json()
    rows = revisions.get("revisions", revisions) if isinstance(revisions, dict) else revisions
    assert any(r.get("source") == "ai" for r in rows), rows


def test_a_private_document_is_refused(ai_client, app_state):
    from tessellate.core import deps
    from tessellate.core.database import Document

    document = _document(ai_client, OLD)
    with deps.get_db().session() as session:
        session.get(Document, document["id"]).is_private = True
        session.commit()
    with deps.get_db().session() as session:
        result = tools.execute_tool(session, "edit_document", {"document_id": document["id"], "content": NEW})
    assert "error" in result


PAIRS = [
    ("", "one"),
    ("one", ""),
    ("a\nb\nc", "a\nb\nc"),
    (OLD, NEW),
    ("x\ny\nz\nw", "x\nY\nz\nW\nv"),
    ("same\nold line\nsame", "same\nnew line\nsame"),
    ("a\nb\nc\nd\ne\nf", "f\ne\nd\nc\nb\na"),
    ("ends\n", "ends\nmore\n"),
]


@pytest.mark.skipif(not shutil.which("node"), reason="needs node")
def test_the_port_numbers_hunks_as_the_page_does():
    source = (JS_DIR / "documents-history.js").read_text(encoding="utf-8")
    block = source.split("// DOC-DIFF-BEGIN", 1)[1].split("// DOC-DIFF-END", 1)[0]
    script = block + f"""
const pairs = {json.dumps(PAIRS)};
const out = pairs.map(([a, b]) => {{
  const ops = docDiffLines(a, b);
  const hunks = docDiffHunks(ops);
  return {{ ops: ops.map((o) => [o.op, o.text]), hunks: hunks.map((h) => [h.from, h.to]),
    applied: hunks.map((_, i) => docDiffApply(ops, hunks, [i])) }};
}});
process.stdout.write(JSON.stringify(out));
"""
    page = json.loads(subprocess.run(["node", "-e", script], capture_output=True, text=True, check=True).stdout)
    for (before, after), want in zip(PAIRS, page):
        ops = linediff.lines(before, after)
        assert [list(o) for o in ops] == want["ops"]
        assert [list(h) for h in linediff.hunks(ops)] == want["hunks"]
        assert [linediff.apply(before, after, {i})[0] for i in range(len(want["hunks"]))] == want["applied"]
