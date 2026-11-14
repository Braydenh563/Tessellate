"""Source text: "Bring hidden key handlers into the shortcut table and palette."

L-ui-modernisation-14: F8 and Shift+F8 walk (and Alt+Enter opens) a document's writing suggestions
(the listener beside `docFindingKeyBox`, documents.js) and were in neither the
`?` sheet nor the palette. Both read `DOC_COMMANDS`, so a row there lists them;
the row runs the same step the keys do."""

from tests._app_js import frontend_text

DOCS = frontend_text("documents.js")


def _row(row_id: str) -> str:
    start = DOCS.index(f'{{ id: "{row_id}"')
    return DOCS[start : DOCS.index("},", start)]


def test_f8_and_shift_f8_are_rows_of_the_command_table() -> None:
    table = DOCS[DOCS.index("const DOC_COMMANDS") :]
    table = table[: table.index("\n];")]
    assert '{ id: "finding-next"' in table and '{ id: "finding-previous"' in table
    assert 'keys: "F8"' in _row("finding-next")
    assert 'keys: "Shift+F8"' in _row("finding-previous")


def test_each_row_runs_the_step_the_keys_take() -> None:
    assert "docFindingStep(" in _row("finding-next") and ", false)" in _row("finding-next")
    assert "docFindingStep(" in _row("finding-previous") and ", true)" in _row("finding-previous")
    # Alt+Enter is listed on the quick-fix row, whose label names both jobs: one chord, one row
    # (test_doc_commands); the prose row stays in the palette for the same step.
    assert "docOpenSuggestFor(" in _row("finding-here")
    assert 'writing suggestions, at the caret", keys: "Alt+Enter"' in _row("quick-fix")
    # The listener is still the one place the keys are read.
    assert 'if (event.key !== "F8") return;' in DOCS
