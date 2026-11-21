"""L703: RapidOCR reads small text enlarged (and nothing else done to the picture), with the boxes it
reports put back on the original page. Measured over nine rendered pages with the real model: mean
similarity 0.853 as read, 0.805 through Tesseract's full preparation, 0.876 enlarged only."""

from pathlib import Path

import pytest

PIL = pytest.importorskip("PIL")
from PIL import Image, ImageDraw  # noqa: E402

from tessellate.core import ocr  # noqa: E402


def _page(tmp_path: Path, text_px: int) -> Path:
    path = tmp_path / f"page{text_px}.png"
    image = Image.new("RGB", (40 * text_px, 6 * text_px), "white")
    draw = ImageDraw.Draw(image)
    for row in range(3):
        top = text_px + row * 2 * text_px
        for col in range(12):
            left = text_px + col * 3 * text_px
            draw.rectangle([left, top, left + 2 * text_px, top + text_px - 1], fill="black")
    image.save(path)
    return path


class _Recorder:
    def __init__(self):
        self.seen = []

    def __call__(self, picture):
        self.seen.append(picture)
        width = picture.shape[1] if hasattr(picture, "shape") else Image.open(picture).width
        return ([[[[0, 0], [width, 0], [width, 10], [0, 10]], "line", 0.9]], 0.1)


@pytest.fixture
def reader(monkeypatch):
    recorder = _Recorder()
    monkeypatch.setattr(ocr, "_rapidocr_reader", lambda: recorder)
    return recorder


def test_small_text_is_enlarged_and_boxes_come_back_to_the_page(tmp_path, reader):
    path = _page(tmp_path, 6)
    lines = ocr._rapidocr_lines(path)
    picture = reader.seen[0]
    assert hasattr(picture, "shape") and picture.shape[1] > 240
    assert lines[0][0][1][0] == pytest.approx(240, abs=1)


def test_big_text_is_read_from_the_file_as_before(tmp_path, reader):
    path = _page(tmp_path, 40)
    ocr._rapidocr_lines(path)
    assert reader.seen == [str(path)]


def test_an_unreadable_file_still_goes_to_the_reader(tmp_path, reader):
    path = tmp_path / "broken.png"
    path.write_bytes(b"not a picture")
    ocr._rapidocr_lines(path)
    assert reader.seen == [str(path)]
