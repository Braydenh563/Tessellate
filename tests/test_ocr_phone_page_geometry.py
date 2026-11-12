"""L-general-50: the Library reader on a phone is the whole screen.

`library-lazy.css` loads after the boot CSS, so `.ocr-card`'s width and height
(96vw by 92vh) beat the `page` variant's `.sheet-card-page` at equal weight: the
reader was 374 by 776 in a 390 by 844 window (`libreader.js`)."""
from pathlib import Path

CSS = (Path(__file__).resolve().parent.parent / "frontend" / "css" / "library-lazy.css").read_text(encoding="utf-8")


def test_the_reader_size_does_not_apply_to_the_phone_page() -> None:
    at = CSS.index(".ocr-card:not(.sheet-card-page) {")
    block = CSS[at : CSS.index("}", at)]
    assert "width: min(96vw, 1500px)" in block and "height: min(92vh, 1000px)" in block
    plain = CSS[CSS.index(".ocr-card {") :]
    plain = plain[: plain.index("}")]
    assert "width:" not in plain and "height:" not in plain
