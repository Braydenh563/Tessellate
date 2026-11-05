"""Audit 160 (D23) and 161 (D24): the CodeMirror theme has its own file, and the
document editor's drop target lookup lives with the documents, not in settings-wiring."""
from tests._app_js import JS_DIR


def _t(name):
    return (JS_DIR / name).read_text(encoding="utf-8")


def test_the_theme_is_its_own_module_loaded_with_the_library_bundle():
    assert "function docCmTheme(CM) {" in _t("documents-cm-theme.js")
    assert "function docCmTheme" not in _t("documents-cm.js")
    app = _t("app.js")
    assert app.index('"/js/documents-cm-theme.js"') < app.index('"/js/documents.js"')


def test_the_document_surface_as_a_drop_target_is_answered_by_documents():
    assert "doc-content-code" not in _t("settings-wiring.js")
    assert "docFileDropBox" in _t("documents-embeds.js")
    assert "docFileDropBox" in _t("settings-wiring.js")
