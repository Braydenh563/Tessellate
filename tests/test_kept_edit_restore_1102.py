"""A kept edit comes back by itself when it is the newest (audit 1102 DX31).

A reload within the autosave pause keeps the last words on this device. They
used to return only through a toast ("Put them back"), and the editor showed
the older server text until that was pressed. Now the kept copy remembers the
hash of the server text it was typed over (`base`, the `base_hash` a save
sends); on open, when that still equals the server's, the kept text is newer by
construction and is restored into the editor, with Undo in the toast. A kept
copy typed over text the server has since moved past still asks first.
"""

from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DOCUMENTS = (ROOT / "frontend" / "js" / "documents.js").read_text(encoding="utf-8")


def _body(name: str) -> str:
    start = DOCUMENTS.index(f"function {name}(")
    return DOCUMENTS[start: DOCUMENTS.index("\n}\n", start)]


def test_the_kept_copy_remembers_the_server_text_it_was_typed_over() -> None:
    assert "base: currentDoc.content_hash" in _body("keepDocEditLocally")


def test_a_newer_kept_copy_is_restored_on_open_with_an_undo() -> None:
    offer = _body("offerKeptDocEdit")
    assert "kept.base && kept.base === doc.content_hash" in offer
    assert '"Undo"' in offer
    assert '"Put them back"' in offer, "a kept copy over older server text still asks first"
    assert offer.index("kept.base === doc.content_hash") < offer.index('"Put them back"')


def test_undo_puts_the_server_text_back_and_forgets_the_kept_copy() -> None:
    offer = _body("offerKeptDocEdit")
    undo = offer[offer.index('"Undo"'):]
    assert "doc.content" in undo and "forgetDocEditLocally(doc.id)" in undo
