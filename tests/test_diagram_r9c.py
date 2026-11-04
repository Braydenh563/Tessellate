"""DOCUMENTS_PLAN 22.4 R9c (INBOX 1621): the chat chip and Save to Library.

A diagram attached to a chat is a card of its own (kind "diagram") and the model reads the row's source, within the cap the
chat applies to any attached document; after the source is edited the next turn reads the new text (fake transport). Save to
Library makes the `mmd` row from a fence or a board object and only offers the swap: a fence becomes `![[Title]]`, an object
gains `data.diagram_id`. The pure range of the swap runs under node; the DOM half is read for what it must hold.
"""

from __future__ import annotations

import json
import shutil
import subprocess
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
JS = ROOT / "frontend" / "js"
EMBED = (JS / "diagram-embed.js").read_text(encoding="utf-8")
MERMAID = (JS / "documents-mermaid.js").read_text(encoding="utf-8")
INTER = (JS / "whiteboard-interchange.js").read_text(encoding="utf-8")
SRC = "flowchart TD\n  A --> B"
needs_node = pytest.mark.skipif(not shutil.which("node"), reason="needs node")


def _swap(text: str, source: str, near: int = 0):
    """The fence's lines (the app's own `diagramModel.fence`) and the whole-fence range `swapRange` makes of them."""
    region = MERMAID[MERMAID.index("// DIAGRAM-MODEL-BEGIN") : MERMAID.index("// DIAGRAM-MODEL-END")]
    script = (
        region
        + EMBED
        + f"\nconst at=diagramModel.fence({json.dumps(text)},{json.dumps(source)},{near});"
        + f"process.stdout.write(JSON.stringify(at&&diagramModel.embed.swapRange({json.dumps(text)},at)));"
    )
    return json.loads(subprocess.run(["node", "-e", script], capture_output=True, text=True, check=True, timeout=60).stdout)


@needs_node
def test_the_swap_takes_the_whole_fence_and_nothing_round_it():
    text = f"Intro\n\n```mermaid\n{SRC}\n```\n\nEnd\n"
    at = _swap(text, SRC)
    assert text[at["from"] : at["to"]] == f"```mermaid\n{SRC}\n```"
    assert text[: at["from"]] + "![[Flow]]" + text[at["to"] :] == "Intro\n\n![[Flow]]\n\nEnd\n"


@needs_node
def test_the_swap_works_for_a_fence_at_both_ends_of_the_text():
    only = f"```mermaid\n{SRC}\n```"
    at = _swap(only, SRC)
    assert (at["from"], at["to"]) == (0, len(only))
    spaced = f"x\n```mermaid\n{SRC}\n```  \ny"
    at = _swap(spaced, SRC)
    assert spaced[at["from"] : at["to"]] == f"```mermaid\n{SRC}\n```  "


@needs_node
def test_of_two_equal_fences_the_swap_takes_the_one_nearest_the_figure():
    text = f"```mermaid\n{SRC}\n```\n\nmid\n\n```mermaid\n{SRC}\n```\n"
    second = _swap(text, SRC, text.rindex("```mermaid"))
    assert second["from"] > text.index("mid")


def test_save_to_library_makes_a_diagram_row_and_only_offers_the_swap():
    save = EMBED[EMBED.index("async function save(") : EMBED.index("async function link(")]
    assert 'file_type: "mmd"' in save and 'method: "POST"' in save
    assert "toastAction(said, offer.label" in save and "offer.run(made)" in save
    # The swap is the button's: nothing in `save` itself touches the fence or the object.
    assert "diagram_id" not in save and save.index("toastAction(") > save.index("run: (row) =>")
    assert 'makeMenuItem("ph:books Save to Library"' in EMBED


def test_a_fence_offers_save_to_library_beside_edit_as_blocks():
    live = MERMAID[MERMAID.index("//: Edit as blocks (1546 D6)") : MERMAID.index("class DocMermaidReason")]
    assert 'smallButton("ph:books", "Save to Library"' in live
    assert "wrap.append(figure, edit, keep)" in live
    assert "offer: { fence: [view, this.source, near] }" in live
    # The swap itself is in the lazy file: the whole fence, found again by its text, becomes the link.
    assert "`![[${row.title}]]`" in EMBED and "...swapRange(text, at)" in EMBED and "That diagram is no longer in the document" in EMBED


def test_a_board_object_offers_the_link_and_the_save_keeps_the_snapshot():
    assert 'offer: d && { link: d }' in INTER
    assert "link(offer.link, row, history[at])" in EMBED
    link = EMBED[EMBED.index("async function link(") : EMBED.index("// --- the dialog (D6)")]
    assert "diagram_id: row.id" in link and "wbPushUndo(" in link and "mermaid: String(source).trim()" in link


def _row(client, content=SRC):
    return client.post("/documents", json={"title": "Flow", "content": content, "file_type": "mmd"}).json()


def test_the_model_reads_an_attached_diagrams_source_and_the_edited_one_next_turn(ai_client, fake_ollama):
    row = _row(ai_client)
    ai_client.post("/chat", json={"question": "what does this diagram show?", "document_ids": [row["id"]]})
    sent = next(c for c in reversed(fake_ollama.chat_calls) if any("what does this diagram show?" in m["content"] for m in c))
    assert any("A --> B" in m["content"] for m in sent)
    # The builder's Done writes the row; the reference and the next turn both read it back.
    edited = f"{SRC}\n  B --> C"
    assert ai_client.put(f"/documents/{row['id']}", json={"content": edited}).status_code == 200
    assert ai_client.get(f"/documents/{row['id']}").json()["content"] == edited
    ai_client.post("/chat", json={"question": "and now, what changed?", "document_ids": [row["id"]]})
    sent = next(c for c in reversed(fake_ollama.chat_calls) if any("and now, what changed?" in m["content"] for m in c))
    assert any("B --> C" in m["content"] for m in sent)


def test_a_diagram_sent_in_chat_comes_back_as_a_diagram_card(client):
    row = _row(client)
    plain = client.post("/documents", json={"title": "Brief"}).json()
    made = client.post("/conversations", json={"question": "q", "answer": "a", "document_ids": [row["id"], plain["id"]]}).json()
    got = client.get(f"/conversations/{made['id']}").json()["messages"][0]["attachments"]
    assert got == [{"id": row["id"], "kind": "diagram", "name": "Flow"}, {"id": plain["id"], "kind": "document", "name": "Brief"}]


def test_the_chip_is_a_diagram_card_that_opens_its_page():
    chat = (JS / "chat-agent.js").read_text(encoding="utf-8")
    assert 'NOTEBOOK_KINDS.diagram = { ...NOTEBOOK_KINDS.document, icon: "ph-flow-arrow", word: "Diagram" }' in chat
    assert 'attachDocumentToChat(ref.id, ref.title, "diagram")' in (JS / "obj-ref.js").read_text(encoding="utf-8")
    attach = (JS / "chat-attach.js").read_text(encoding="utf-8")
    assert "kind: document_.kind || \"document\"" in attach and "function attachDocumentToChat(id, name, kind)" in attach
    assert 'item.kind === "diagram"' in (JS / "attachment-peek.js").read_text(encoding="utf-8")
