"""Source text: the behaviour is front-end script that pytest cannot run without a browser, so these pin the code's text.

Two-finger zoom on the viewers (DOCUMENTS_PLAN owner bug, "I cant two finger
trackpad zoom in or out on documents or images on the ocr workspace?").

Measured in the running app 2026-11-12: a Ctrl wheel of -10 x5 took the OCR page
pane from Fit to 150% (`scratchpad/ui-sweeps/ocr79.js`, ONLY=zoom), and the same
events took the lightbox picture and a lightbox PDF page column to scale 1.648,
default prevented. These pin the handlers a refactor would otherwise drop."""

from __future__ import annotations

from pathlib import Path

JS = Path(__file__).resolve().parents[1] / "frontend" / "js"


def test_the_ocr_page_pane_zooms_on_a_ctrl_wheel_and_on_two_fingers():
    src = (JS / "library.js").read_text(encoding="utf-8")
    wheel = src[src.index('$("ocr-page-pane")?.addEventListener("wheel"') :][:700]
    assert "if (!event.ctrlKey) return;" in wheel and "event.preventDefault()" in wheel
    assert "{ passive: false }" in src[src.index('$("ocr-page-pane")?.addEventListener("wheel"') :][:1400]
    for ev in ("touchstart", "touchmove"):
        assert f'$("ocr-page-pane")?.addEventListener("{ev}"' in src


def test_the_lightbox_zooms_a_pdf_page_column_on_a_pinch_though_it_owns_plain_scroll():
    src = (JS / "lightbox-view.js").read_text(encoding="utf-8")
    wheel = src[src.index('stage.addEventListener(\n    "wheel"') :][:1800]
    assert "!doc.classList.contains(\"hidden\") && !e.ctrlKey) return" in wheel
    assert "{ passive: false }" in wheel
    assert "const zoomTarget = () => (!pdfPages.classList.contains(\"hidden\") ? pdfPages : img);" in src
