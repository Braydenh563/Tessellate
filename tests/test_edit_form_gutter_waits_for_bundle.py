"""Source text: the race is between script loads in a browser; it is driven by
scratchpad/ui-sweeps/note-edit-rerender.js on a cold server, so this pins the code that closes it.

The edit form's gutter mount waits for the whole Library bundle (#224).

While the bundle loads, documents-preview.js's `mountGutterFor` replaces its stand-in before
documents-toolbar.js has defined `docGutterPref`, so an edit form drawn in that gap threw
"docGutterPref is not defined" (measured: the first run of the sweep on a fresh server).
"""

from tests._app_js import app_js_text

JS = app_js_text()


def test_the_loader_knows_when_a_bundle_has_finished():
    assert "ensureModule.ready = new Set();" in JS
    assert "ensureModule.ready.add(name)" in JS


def test_the_edit_form_mounts_its_gutter_only_once_the_bundle_is_in():
    assert 'ensureModule.ready.has("library")' in JS
    assert 'ensureModule("library").then(() => mountGutterFor(textarea))' in JS
