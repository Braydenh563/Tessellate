"""Sh1 P12: settings-prefs.js (renderPrefs, renderWebSearch, the Preferences dirty
marks, syncEmbeddingPickerState) was moved out of settings-panes.js for the boot gzip
budget. settings-controls.js calls `wirePrefsDirtyMarks()` while it loads, so the
new file must be in the same bundle and ahead of it: the lazy loader keeps list
order (`el.async = false`), and a control file that threw halfway left the whole
Settings window without its listeners and `ensureSettingsFoldAll`.
"""

from __future__ import annotations

import re
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
JS = ROOT / "frontend" / "js"


def _bundle() -> list[str]:
    app = (JS / "app.js").read_text(encoding="utf-8")
    line = re.search(r"^  settingsControls: \[(.*?)\],$", app, re.M).group(1)
    return re.findall(r'"(/[^"]+)"', line)


def test_the_prefs_file_loads_ahead_of_the_controls_that_call_it_at_load():
    files = _bundle()
    assert "/js/settings-prefs.js" in files and "/js/settings-controls.js" in files
    assert files.index("/js/settings-prefs.js") < files.index("/js/settings-controls.js")
    controls = (JS / "settings-controls.js").read_text(encoding="utf-8")
    assert re.search(r"^  wirePrefsDirtyMarks\(\);$", controls, re.M), "the load-time call this order protects"


def test_what_the_file_defines_is_no_longer_defined_at_boot():
    prefs = (JS / "settings-prefs.js").read_text(encoding="utf-8")
    panes = (JS / "settings-panes.js").read_text(encoding="utf-8")
    for name in ("renderPrefs", "renderWebSearch", "wirePrefsDirtyMarks", "syncEmbeddingPickerState", "renderAutonomousSettings"):
        assert re.search(rf"^(?:async )?function {name}\(", prefs, re.M), name
        assert not re.search(rf"^(?:async )?function {name}\(", panes, re.M), f"{name} is defined twice"


def test_the_callers_outside_the_bundle_reach_it_through_a_stand_in():
    app = (JS / "app.js").read_text(encoding="utf-8")
    stubs = re.search(r"^  settingsControls: \[\"(?!/).*?\],$", app, re.M).group(0)
    for name in ("renderPrefs", "renderWebSearch", "syncEmbeddingPickerState"):
        assert f'"{name}"' in stubs, name
