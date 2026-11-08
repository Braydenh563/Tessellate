"""INBOX 1696 n, the owner: "the writing room doesnt handle or render attachments" (a note added from
the Tray landed in Your thoughts as a raw [[link]]). A note given to Your thoughts becomes a note the
draft is written from, through the one adder; anything else is still its link in the box."""

from __future__ import annotations

import re
from pathlib import Path

from tests._objmove_node import needs_node, run

ROOT = Path(__file__).resolve().parent.parent


def _adder() -> str:
    src = (ROOT / "frontend" / "js" / "writing-desk.js").read_text(encoding="utf-8")
    return re.search(r"^function addDraftSource\(entry\) \{.*?^\}", src, re.S | re.M).group(0)


@needs_node
def test_a_note_from_the_tray_is_a_note_it_writes_from_not_a_link_in_the_box() -> None:
    body = """
    const toasts = [], status = [], inserted = [];
    globalThis.toast = (t) => toasts.push(t);
    globalThis.DRAFT_MAX_SOURCES = 2; globalThis.draftSources = [];
    globalThis.renderDraftSources = () => {}; globalThis.saveDraftLocally = () => {};
    globalThis.setDraftStatus = (t, bad) => status.push([t, !!bad]);
    globalThis.clipText = (t) => t; globalThis.notePreviewText = (t) => t;
    globalThis.document = { execCommand: (cmd, ui, text) => inserted.push(text) > 0 };
    """ + _adder().replace("function addDraftSource", "globalThis.addDraftSource = function") + """
    const box = { isConnected: true, matches: (sel) => sel.includes("textarea"), focus() {}, closest: (sel) => (sel.includes("#draft-thoughts") ? box : null) };
    const dest = objDestinationAt(box);
    const a = objRender(objRef("note", "7", "Uni is done"), dest);
    const again = objRender(objRef("note", 7, "Uni is done"), dest);
    const b = objRender(objRef("note", 8, "Second"), dest);
    const full = objRender(objRef("note", 9, "Third"), dest);
    const doc = objRender(objRef("document", 3, "Essay"), dest);
    __out({ type: dest.type, a, again, b, full, doc, sources: draftSources, toasts, status, inserted });
    """
    out = run(["obj-ref.js"], body)
    assert out["type"] == "writing"
    assert out["a"] and out["again"] and out["b"] and out["full"]
    assert out["sources"] == [{"id": 7, "label": "Uni is done"}, {"id": 8, "label": "Second"}]
    assert out["toasts"] == [] and out["status"][0] == ["Writing from “Uni is done” too.", False]
    assert out["status"][-1] == ["Six notes is the most one draft can be written from.", True]
    # A note never becomes a raw link in the box; a document is still its link.
    assert len(out["inserted"]) == 1 and "Essay" in out["inserted"][0] and out["doc"]


def test_the_adder_button_and_the_tray_share_one_function_loaded_with_the_desk() -> None:
    wiring = (ROOT / "frontend" / "js" / "wiring.js").read_text(encoding="utf-8")
    assert "addDraftSource(entry);" in wiring and "draftSources.push" not in wiring
    app = (ROOT / "frontend" / "js" / "app.js").read_text(encoding="utf-8")
    assert 'writingDesk: ["addDraftSource", ' in app
