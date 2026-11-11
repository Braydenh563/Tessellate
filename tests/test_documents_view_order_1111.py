"""documents.js calls into documents-view.js while it loads (setDocView reaches
docCmSyncLanguage, the toolbar reaches docCmSyncGutter), so the carved file has
to load first and its own top level may only declare. Found by driving the app
after the carve: loaded second, the whole Documents tab died on a
ReferenceError that no unit test saw."""

from pathlib import Path

JS = Path(__file__).resolve().parent.parent / "frontend" / "js"


def test_the_view_file_loads_before_documents_js():
    bundle = (JS / "app.js").read_text(encoding="utf-8")
    assert bundle.index('"/js/documents-view.js"') < bundle.index('"/js/documents.js"')


def test_the_view_files_top_level_reads_nothing_from_documents_js():
    view = (JS / "documents-view.js").read_text(encoding="utf-8")
    top = [line for line in view.splitlines() if line and not line.startswith((" ", "\t", "//", "}", ")", "]", "function ", "async function "))]
    # Declarations and listeners only; docToolPref lives in documents.js and runs there.
    assert not any("docToolPref" in line for line in top), top
