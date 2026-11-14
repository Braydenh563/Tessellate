"""L-documents-66: a Live view link chip's underline thickens while Ctrl (Meta on a Mac) is held.

Measured 2026-11-14 (scratchpad t646-mod.js, 1440x900): idle underline thickness auto; Ctrl down 2px with the
`doc-mod-held` class on `.cm-editor`; released auto; Ctrl held then a window blur auto.
"""

from __future__ import annotations

import re
from pathlib import Path

JS = Path(__file__).resolve().parents[1] / "frontend" / "js"
CM = (JS / "documents-cm.js").read_text(encoding="utf-8")
THEME = (JS / "documents-cm-theme.js").read_text(encoding="utf-8")


def _plugin() -> str:
    start = CM.index("docLivePluginCache = ViewPlugin.fromClass(")
    return CM[start : CM.index("rebuild(view) {", start)]


def test_the_cue_listeners_are_balanced_and_clear_on_blur_and_hide():
    body = _plugin()
    added = re.findall(r'(window|document)\.addEventListener\("([\w]+)", this\.modHeld\)', body)
    removed = re.findall(r'(window|document)\.removeEventListener\("([\w]+)", this\.modHeld\)', body)
    assert sorted(added) == sorted(removed) == [("document", "visibilitychange"), ("window", "blur"), ("window", "keydown"), ("window", "keyup")]
    assert "destroy() {" in body


def test_the_class_follows_either_open_key_and_the_theme_thickens_the_chip():
    assert "event.ctrlKey || event.metaKey" in _plugin()
    assert '"&.doc-mod-held .cm-md-link": { textDecorationThickness: "2px"' in THEME
