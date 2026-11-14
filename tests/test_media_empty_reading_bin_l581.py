"""Emptying a reading in a gallery card goes through the bin (L581).

The card's click-to-edit box used to send an empty `text` to the analyse
route, which cleared the field for good. An empty save now deletes the whole
reading the way the workspace and the lightbox do, so Undo can bring it back.
"""

from __future__ import annotations

from tests._app_js import frontend_text


def _card_save(source: str, kind: str) -> str:
    marker = f'analyseMediaRow(image, "{kind}", {{ text: next }})'
    at = source.index(marker)
    return source[max(0, at - 700) : at + 200]


def test_ocr_card_empty_save_bins_the_reading():
    near = _card_save(frontend_text("library.js"), "ocr")
    assert 'ocrBinField(image, "ocr")' in near
    assert "ocrOfferBinUndo" in near


def test_vision_card_empty_save_bins_the_reading():
    near = _card_save(frontend_text("library.js"), "vision-ocr")
    assert 'ocrBinField(image, "vision-ocr")' in near
    assert "ocrOfferBinUndo" in near
