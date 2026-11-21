"""RapidOCR reads a prepared picture (L703): a dark ground inverted and small
text enlarged, as Tesseract's read already gets, with the boxes put back on
the original and the plain read kept as the fallback. A fake reader stands in
for RapidOCR, which no test environment installs."""

from __future__ import annotations

from pathlib import Path

import pytest

PIL = pytest.importorskip("PIL")
numpy = pytest.importorskip("numpy")
from PIL import Image, ImageDraw  # noqa: E402

from tessellate.core import ocr, ocr_prep  # noqa: E402

BOX = [[10.0, 20.0], [110.0, 20.0], [110.0, 40.0], [10.0, 40.0]]


def _small_text(path: Path, *, dark: bool = False) -> Path:
    ground, ink = (20, 255) if dark else (255, 20)
    img = Image.new("L", (400, 120), ground)
    draw = ImageDraw.Draw(img)
    for row in range(6):
        draw.text((8, 6 + row * 18), "small print line " * 3, fill=ink)
    img.save(path)
    return path


class _Fake:
    def __init__(self, answers):
        self.calls, self.answers = [], list(answers)

    def __call__(self, arg):
        self.calls.append(arg)
        return self.answers.pop(0), [0.1]


@pytest.fixture
def fake(monkeypatch):
    def install(*answers):
        reader = _Fake(answers)
        monkeypatch.setattr(ocr, "_rapidocr_reader", lambda: reader)
        return reader

    return install


def test_small_text_is_enlarged_and_boxes_come_back_on_the_original(tmp_path, fake):
    """The reader gets a grey array bigger than the file, and a box it reports
    on that array is divided by the scale."""
    path = _small_text(tmp_path / "p.png")
    prepared = ocr._rapidocr_prepared(path)
    assert prepared is not None
    array, scale = prepared
    assert scale > 1.0 and array.ndim == 2 and array.shape[1] > 400
    reader = fake([[[[x * scale, y * scale] for x, y in BOX], "small print", 0.9]])
    lines = ocr._rapidocr_lines(path)
    assert len(reader.calls) == 1 and not isinstance(reader.calls[0], str)
    assert lines[0][1] == "small print"
    assert [v for corner in lines[0][0] for v in corner] == pytest.approx([v for corner in BOX for v in corner])


def test_a_dark_ground_is_inverted(tmp_path):
    """Light text on a dark page reaches the reader as dark on light."""
    array, _ = ocr._rapidocr_prepared(_small_text(tmp_path / "d.png", dark=True))
    assert float(numpy.median(array)) > 200


def test_a_picture_that_needs_nothing_is_read_as_the_file(tmp_path, fake):
    """A light page with no small text to enlarge: no preparation, the path
    is read as before."""
    img = Image.new("L", (300, 200), 255)
    img.save(tmp_path / "big.png")
    assert ocr_prep.prepare_for_detector(Image.open(tmp_path / "big.png")) is None
    reader = fake([[BOX, "BIG", 0.9]])
    assert ocr._rapidocr_lines(tmp_path / "big.png")[0][1] == "BIG"
    assert reader.calls == [str(tmp_path / "big.png")]


def test_an_empty_prepared_read_falls_back_to_the_plain_file(tmp_path, fake):
    """A prepared picture that finds nothing never costs the read the plain
    file would have given."""
    path = _small_text(tmp_path / "p.png")
    reader = fake(None, [[BOX, "plain", 0.8]])
    lines = ocr._rapidocr_lines(path)
    assert [t for _, t, _ in lines] == ["plain"]
    assert len(reader.calls) == 2 and reader.calls[1] == str(path)
    assert lines[0][0] == BOX


def test_a_preparation_fault_reads_the_file(tmp_path, fake, monkeypatch):
    """Pillow failing on the picture still leaves the plain read."""
    path = _small_text(tmp_path / "p.png")

    def broken(_img):
        raise OSError("bad picture")

    monkeypatch.setattr(ocr_prep, "prepare_for_detector", broken)
    assert ocr._rapidocr_prepared(path) is None
    reader = fake([[BOX, "plain", 0.8]])
    assert ocr._rapidocr_lines(path)[0][1] == "plain"
    assert reader.calls == [str(path)]
