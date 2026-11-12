"""Source text: a Settings section switched to before settings-controls.js has
arrived no longer throws: `ensureSettingsFoldAll` has a stand-in like the
module's other entry points.

Found by the L418 sweep: pressing a Settings nav button with the module not
yet fetched threw "ensureSettingsFoldAll is not defined" from
`showSettingsSection` (settings.js, a boot file); with the stand-in there is
no page error and the module loads on that press.
"""

from __future__ import annotations

from tests._app_js import app_js_text, script_file_text


def test_the_boot_caller_has_a_stand_in():
    assert "ensureSettingsFoldAll($(`settings-${name}`))" in script_file_text("settings.js")
    assert 'settingsControls: ["ensureSettingsFoldAll", "refreshSearxngHost"' in app_js_text()
