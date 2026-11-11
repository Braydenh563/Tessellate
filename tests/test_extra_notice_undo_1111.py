"""The optional-package notice's button turns to Undo once pressed (owner, 2026-11-11).

"Make it readily evident ... one click to install ... the button turns to an undo
if pressed", for every optional package. The Install click is the consent, so
there is no dialog; the same button is Undo while the install runs (it stops the
download) and after it lands (it removes the package). The OCR workspace and the
lightbox show the RapidOCR notice when nothing can read text.
"""

from __future__ import annotations

import re
from pathlib import Path

from tessellate.core import jobs

ROOT = Path(__file__).resolve().parents[1]
JS = (ROOT / "frontend" / "js" / "extra-notice.js").read_text(encoding="utf-8")
LIBRARY = (ROOT / "frontend" / "js" / "library.js").read_text(encoding="utf-8")
LIGHTBOX = (ROOT / "frontend" / "js" / "lightbox-view.js").read_text(encoding="utf-8")


def test_the_pressed_button_becomes_undo_and_the_click_is_the_consent() -> None:
    check = JS[JS.index("async function extraNoticeCheck") :]
    assert 'install.textContent = "Undo"' in check
    assert "const pressed = new Map()" in JS
    assert "confirmDialog" not in JS, "the Install click is the consent"
    assert "/tasks/cancel" in JS and 'kind: "extra"' in JS, "Undo while installing stops the download"
    assert "/extras/${id}/uninstall" in JS, "Undo once installed removes the package"
    assert "/websearch/searxng/stop" in JS, "SearXNG has no uninstall: its Undo stops it"


def test_a_finished_install_keeps_its_notice_so_undo_stays_reachable() -> None:
    check = JS[JS.index("async function extraNoticeCheck") :]
    assert 'pressed.set(id, "installed")' in check
    assert "const show = Boolean(phase) ||" in check
    #: Closing a finished install ends the Undo and is not remembered as "never ask".
    assert re.search(r'if \(phase === "installed"\) pressed\.delete\(id\);\s*else if \(!phase\) dismiss\(id\)', check)


def test_the_extra_cancel_kind_is_the_installers() -> None:
    assert jobs.CANCELLERS["extra"] == "tessellate.core.extras:cancel"


def test_rapidocr_sentence_says_quickest() -> None:
    assert re.search(r'rapidocr: "RapidOCR is the quickest way to read text in images\."', JS)


def test_the_ocr_workspace_shows_it_when_nothing_can_read() -> None:
    area = LIBRARY[LIBRARY.index("Nothing can read text (no Tesseract") :][:900]
    assert 'extraNoticeMount(ocrHead, "rapidocr"' in area
    assert "needed: !ocrReaders.vision && !ocrReaders.ocr" in area
    #: Not gated on RapidOCR being absent: an install pressed here keeps its Undo.
    assert "!rapidReady" not in area.split("} else {")[0]


def test_the_lightbox_shows_it_for_an_image_with_no_reader() -> None:
    assert re.search(r'tesseract_available === false && !modelStatus\.vision_model_resolved\) \{\s*extraNoticeMount\(info, "rapidocr"\)', LIGHTBOX)
