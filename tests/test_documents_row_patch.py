"""A document write patches its sidebar row from the answer (audit 1031 DC7,
second half): a rename or a mention link used to read the whole document list
again (two pages at 230 documents) and reopen the open document. Run in node
over `documents.js`'s own functions; every other name is a stand-in."""

from __future__ import annotations

import json
import shutil
import subprocess
from pathlib import Path

import pytest

JS = Path(__file__).resolve().parent.parent / "frontend" / "js" / "documents.js"
SOURCE = JS.read_text(encoding="utf-8")


def _function(head: str) -> str:
    start = SOURCE.index(head)
    return SOURCE[start : SOURCE.index("\n}\n", start) + 3]


def _run(scenario: str) -> dict:
    fns = "\n".join(
        _function(head)
        for head in (
            "async function renameDocumentWithUndo(doc, next) {",
        )
    )
    script = (
        """
const calls = [];
const stub = new Proxy(function () {}, { get: (t, k) => (k === "then" ? undefined : k === Symbol.toPrimitive ? () => "" : stub), apply: () => stub, set: () => true });
let docs = [{ id: 1, title: "one", words: 1 }, { id: 2, title: "two", words: 2 }];
let currentDoc = { id: 2, title: "two", content_hash: "h", updated_at: "t0" };
const titleBox = { value: "two" };
const $ = () => titleBox;
function renderDocList() { calls.push("render"); }
function loadDocuments() { calls.push("loadDocuments"); return Promise.resolve(); }
function docPutFields(id, fields) { calls.push("PUT " + id); return Promise.resolve({ id, title: fields.title, updated_at: "t1", words: 7, content_hash: "other" }); }
function offerUndo() {}
function clipText(s) { return s; }
"""
        + fns.replace("async function renameDocumentWithUndo", "globalThis.renameDocumentWithUndo = async function")
        + "\n;(async () => {\n"
        + scenario
        + "\nconsole.log(JSON.stringify({ calls, docs, currentDoc, title: titleBox.value }));\n})();\n"
    )
    result = subprocess.run(["node", "-e", script], capture_output=True, text=True, timeout=30)
    assert result.returncode == 0, result.stderr
    return json.loads(result.stdout.strip().splitlines()[-1])


pytestmark = pytest.mark.skipif(not shutil.which("node"), reason="needs node")


def test_a_rename_of_another_document_is_one_request_and_no_list_read():
    out = _run('await renameDocumentWithUndo(docs[0], "uno");')
    assert out["calls"] == ["PUT 1", "render"], out
    assert out["docs"][0]["title"] == "uno" and out["docs"][0]["words"] == 7
    assert out["currentDoc"]["title"] == "two"


def test_a_rename_of_the_open_document_moves_its_title_box_not_its_text_hash():
    out = _run('await renameDocumentWithUndo(docs[1], "dos");')
    assert out["calls"] == ["PUT 2", "render"], out
    assert out["title"] == "dos"
    assert out["currentDoc"]["title"] == "dos" and out["currentDoc"]["updated_at"] == "t1"
    assert out["currentDoc"]["content_hash"] == "h"


def test_a_row_the_list_does_not_hold_falls_back_to_the_read():
    out = _run('docs = [docs[0]];\nawait renameDocumentWithUndo({ id: 2, title: "two" }, "dos");')
    assert out["calls"] == ["PUT 2", "loadDocuments"], out


def test_the_mention_link_patches_the_row_too():
    #: The links panel's rows moved to their lazy piece (L327).
    piece = (JS.parent / "documents-backlinks.js").read_text(encoding="utf-8")
    assert "} else await loadDocuments(currentDoc?.id);" in piece
