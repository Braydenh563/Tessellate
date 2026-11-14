"""L-world-class-40: the first document open finds the Library's files and the editor in the HTTP cache."""

from tests._app_js import frontend_text


def test_the_first_press_prefetches_the_library_bundle_and_the_editor_without_running_them():
    warm = frontend_text("lazy-entries.js")
    warm = warm[warm.index("function warmLibraryAfterInput() {") : warm.index("warmLibraryAfterInput();")]
    # The library files are in `files` (graph's and library's scripts); the editor bundle is added by path.
    assert "...LAZY_MODULES.library" in warm
    fetch = warm[warm.index("calmAt || (setTimeout(warmNext), idle(") :]
    fetch = fetch[: fetch.index(";")]
    assert "files.map((f) => f + lazyAssetStamp(f))" in fetch
    assert '"/vendor/codemirror/codemirror.min.js"' in fetch
    assert 'priority: "low"' in fetch
    assert "lazyScript" not in fetch  # fetched into the cache, never evaluated here
    # Same gate as the paced evaluation: no data saving, four cores.
    assert warm.index("saveData") < warm.index("calmAt || (setTimeout(warmNext)")


def test_the_prefetched_editor_path_is_the_one_the_documents_file_loads():
    assert 'const DOC_CM_BUNDLE = "/vendor/codemirror/codemirror.min.js";' in frontend_text("documents.js")
