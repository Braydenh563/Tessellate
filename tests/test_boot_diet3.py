"""Boot diet 3 (audit row 21, 2026-11-01): what the boot scripts no longer carry,
and the boot document's size, held down.

`buildTableBlock`, `paletteCommands` and `entryItem` (with the Quick access
draw that reads the palette's rows) were 8 to 9 KB, 5 KB and 3 KB gzipped of
script that nothing needs before the first input. They live in lazy files now;
this fails if one comes back to a boot script, or a boot script reads one
without a way to wait for it (the lazy-bundle lints say how:
`test_lazy_bundle_calls.py`).
"""

from __future__ import annotations

import re
from html.parser import HTMLParser
from pathlib import Path

from tests._app_js import app_js_files

FRONTEND = Path(__file__).resolve().parents[1] / "frontend"
JS = FRONTEND / "js"

#: function -> the lazy file that holds it, and the bundle that loads that file.
MOVED = {
    "buildTableBlock": ("table-block.js", "tableBlock"),
    "paletteCommands": ("app-features.js", "featureRows"),
    "quickCatalogue": ("app-features.js", "featureRows"),
    "renderQuickLinks": ("app-features.js", "featureRows"),
}


def _defines(text: str, name: str) -> bool:
    return re.search(rf"^(?:async )?function {name}\(", text, re.M) is not None


def test_the_moved_functions_are_in_lazy_files_and_not_at_boot():
    boot = {path.name: path.read_text(encoding="utf-8") for path in app_js_files()}
    entries = (JS / "lazy-entries.js").read_text(encoding="utf-8") + (JS / "app.js").read_text(encoding="utf-8")
    for name, (file, bundle) in MOVED.items():
        assert _defines((JS / file).read_text(encoding="utf-8"), name), f"{name} is not in {file}"
        at_boot = [f for f, text in boot.items() if _defines(text, name)]
        assert not at_boot, f"{name} is back in a boot script: {at_boot}"
        assert file not in boot, f"{file} is a boot script"
        assert re.search(rf"\b{bundle}: \[[^\]]*\"/js/{re.escape(file)}\"", entries), f"bundle {bundle} does not load {file}"


def test_the_dashboards_quick_access_draw_waits_for_its_file_through_a_stand_in():
    entries = (JS / "lazy-entries.js").read_text(encoding="utf-8")
    assert 'featureRows: ["renderQuickLinks"]' in entries


class _Count(HTMLParser):
    def __init__(self) -> None:
        super().__init__()
        self.elements = 0

    def handle_starttag(self, tag, attrs):
        self.elements += 1

    def handle_startendtag(self, tag, attrs):
        self.elements += 1


#: The elements `index.html` itself carries: 7,879 on 2026-11-01. Live, after a
#: sign-in on an empty notebook, 8,038 (the rest is what the first draw adds);
#: with a notebook of notes and a dashboard of widgets it is more (11,168 in the
#: audit). Every surface's DOM is in this page, so each tab pays on open: the
#: next step is surfaces as `<template>`s stamped on first visit (row 21), and
#: this number only goes down when that lands.
BOOT_ELEMENTS_CAP = 7_879


def test_the_boot_document_does_not_grow():
    counter = _Count()
    counter.feed((FRONTEND / "index.html").read_text(encoding="utf-8"))
    assert counter.elements <= BOOT_ELEMENTS_CAP, (
        f"index.html carries {counter.elements} elements, cap {BOOT_ELEMENTS_CAP}: "
        "a new surface is built on first visit, not shipped in the page"
    )
