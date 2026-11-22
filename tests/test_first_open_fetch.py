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
    assert "lazyScript" not in tail.split("if (!navigator", 1)[1]  # the fetch itself runs nothing


def test_the_editor_is_evaluated_in_a_later_idle_slot_once_the_bundle_is_in():
    # Why this test was added: the first step only filled the cache; the evaluation (documents.js, then the
    # editor's 80 ms) still landed on the click, so the second step runs it in idle, after the bytes.
    tail = _tail()
    assert tail.index("fetch(") < tail.index('ensureModule("library")') < tail.index("warmDocumentEngine()")
    assert "Promise.all" in tail  # after every fetch has settled, so evaluation never competes with the network


def test_it_keeps_the_paced_warms_gate():
    tail = _tail()
    assert "!navigator.connection?.saveData" in tail and "hardwareConcurrency" in tail and ">= 4" in tail


def test_the_fetched_editor_path_is_the_one_the_documents_file_loads():
    assert 'const DOC_CM_BUNDLE = "/vendor/codemirror/codemirror.min.js";' in frontend_text("documents.js")


def test_the_view_is_mounted_empty_in_idle_after_the_editor_has_loaded():
    # The click then pays the state swap and the render, not the 150 ms view mount.
    tail = _tail()
    assert tail.index("warmDocumentEngine()") < tail.index("loadCodeMirror()") < tail.index("ensureDocEditor()")
    # The phone and data-saving guard of the warm is the guard of the mount too: carried by the warm's return value,
    # since `docWarmed` is local to documents-cm-load.js (CI E2E on 392de364f: "docWarmed is not defined").
    assert "window.warmDocumentEngine() && window.loadCodeMirror()" in tail
    assert "docWarmed" not in tail
