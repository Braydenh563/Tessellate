"""The engine line's wiring (INBOX 443 (3)), which the suite cannot see in a DOM.

The behaviour is driven by `scratchpad/ui-sweeps/ocrflow.js`; these are the
ratchets that keep it from drifting back into the shapes it replaced: a second
install flow, a boot-time piece, a tooltip standing in for a status.
"""

from __future__ import annotations

import re
from pathlib import Path

from tests._app_js import app_js_text
from tests._app_js import index_html_text

ROOT = Path(__file__).resolve().parents[1]
JS = ROOT / "frontend" / "js"
INDEX = index_html_text()


def test_the_engine_line_is_a_lazy_piece_not_a_boot_script():
    assert "/js/ocr-engine.js" not in INDEX
    app = (JS / "app.js").read_text(encoding="utf-8")
    assert 'ocrEngine: ["/js/ocr-engine.js"]' in app
    assert 'ocrEngine: ["ocrEngineMount"]' in app


def test_the_workspace_has_the_line_and_mounts_it():
    assert 'id="ocr-engine"' in INDEX
    library = (JS / "library.js").read_text(encoding="utf-8")
    assert 'ocrEngineMount($("ocr-engine")' in library


def test_one_install_flow_for_the_ocr_extra():
    """The install of the OCR extra is posted by the Packages row (its own
    buttons) and by the engine line, and by nothing else. The engine line
    installs Tesseract or RapidOCR (WORLD_CLASS_PLAN 28.4 row 5), one route
    named from `OCR_ENGINE_EXTRAS`."""
    marks = ("/extras/ocr/install", "`/extras/${extra}/install`")
    sources = {path.name for path in JS.glob("*.js") if any(m in path.read_text(encoding="utf-8") for m in marks)}
    assert sources == {"ocr-engine.js"}, sources
    engine = (JS / "ocr-engine.js").read_text(encoding="utf-8")
    assert "const OCR_ENGINE_EXTRAS = {" in engine and "rapidocr: {" in engine
    status = (JS / "settings-packages.js").read_text(encoding="utf-8")
    assert "`/extras/${extra.id}/install" in status


def test_the_packages_row_hands_the_language_to_the_engine_line_only():
    status = (JS / "settings-packages.js").read_text(encoding="utf-8")
    assert "ocrEngineMount(li.appendChild(document.createElement(\"div\")), { settings: true })" in status
    # The row does not grow a language control of its own.
    assert "ocr/language" not in status


def test_no_copy_sends_anyone_to_a_section_that_is_not_there():
    """The section is Packages. "Optional extras" was its old name. Scoped to the
    OCR files: other messages still carry it and are not this change's to fix."""
    assert "Install the “OCR” extra" not in app_js_text()
    for name in ("api/routes_files.py", "core/ocr.py", "core/extras.py"):
        path = ROOT / "src" / "tessellate" / name
        body = path.read_text(encoding="utf-8")
        assert not re.search(r"Settings\s*→\s*Optional extras", body), path.name


def test_a_read_goes_through_the_chooser():
    """Every read in the workspace asks which reader can actually run."""
    library = (JS / "library.js").read_text(encoding="utf-8")
    assert library.count("await ocrChooseReader()") >= 4
    # The old shape: the picker's raw value sent as the reader.
    assert "reader=${ocrReader()}" not in library
