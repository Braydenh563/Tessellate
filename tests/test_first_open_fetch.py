"""L-world-class-40: the first document open finds the Library's files and the editor in the HTTP cache."""

from tests._app_js import frontend_text


def _tail():
    js = frontend_text("library.js")
    return js[js.index("//: **The first document open's bytes come before the open**") :]


def test_the_librarys_first_arrival_fetches_the_rest_of_the_bundle_and_the_editor_in_idle():
    tail = _tail()
    assert "...LAZY_MODULES.library" in tail
    assert '"/vendor/codemirror/codemirror.min.js"' in tail
    assert "lazyAssetStamp(file)" in tail  # the cache key lazyScript will ask for
    assert 'priority: "low"' in tail
    assert "requestIdleCallback" in tail
    assert "lazyScript" not in tail.split("if (!navigator", 1)[1]  # fetched, never run here


def test_it_keeps_the_paced_warms_gate():
    tail = _tail()
    assert "!navigator.connection?.saveData" in tail and "hardwareConcurrency" in tail and ">= 4" in tail


def test_the_fetched_editor_path_is_the_one_the_documents_file_loads():
    assert 'const DOC_CM_BUNDLE = "/vendor/codemirror/codemirror.min.js";' in frontend_text("documents.js")
