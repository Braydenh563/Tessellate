"""L-world-class-128 (WORLD_CLASS_PLAN decision 65): bulk edit is a feature of
selection. The Notes and Timeline selection bars share `fillBatchMore`, which
now sets or removes one property on every selected note with one Undo, beside
the move, tags, archive and delete those bars already had."""

from __future__ import annotations

from tests._app_js import app_js_text, frontend_text

JS = app_js_text()
#: The work is lazy, beside the bulk tag dialog, to keep the boot scripts under their gzip cap.
TAGS = frontend_text("tag-manager.js")


def _body(name: str) -> str:
    start = JS.index(f"function {name}(")
    return JS[start : JS.index("\n}\n", start)]


def test_more_menu_sets_a_property_through_one_undo():
    assert '"ph:list-dashes Set a property…", run: () => openBulkProperty(batchSelection())' in _body("fillBatchMore")
    start = TAGS.index("async function openBulkProperty(ids)")
    body = TAGS[start : TAGS.index("\n}\n", start)]
    assert "await batchEach(" in body, "one toast, one Undo, the shape every batch act has"
    assert "/entries/${id}/properties" in body
    assert "const { [name]: _, ...next } = had" in body, "an empty value removes the property"
    #: Review 5907752577: Undo puts back this one key, read fresh, rather
    #: than the whole block as it was, which reverted edits made since.
    assert "before.set(id, had[name])" in body and "setOne(id, before.get(id))" in body, "the undo restores each note's own value"


def test_both_selection_bars_use_the_shared_menu():
    assert 'fillBatchMore("timeline-batch-more-host")' in JS
    assert "fillBatchMore()" in JS


def test_the_bars_keep_move_tags_and_delete_with_undo():
    delete = _body("batchDelete")
    assert "pushUndo(" in delete and "toastAction(" in delete
    assert "openBulkTags(ids)" in _body("batchTag")
    assert "moveNotesToCategory(ids, category)" in _body("batchMove")
