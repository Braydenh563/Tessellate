"""INBOX 1568: Tesseract read nothing from a region of a board export.

The owner drew a region round the "Goal" box of a board export and got "No text
was found in that region"; the whole page read as garbage. The labels are about
8 px tall, dark on a light box, over a dark canvas. Tesseract wants dark text
about 30 px tall on a light ground, so every read now goes through
`core/ocr_prep.py` first (grey, inverted when the ground is dark, enlarged to
about 30 px, Otsu's two tones at full contrast), and a region is read as one
block with sparse text as the fallback.

The decisions are numbers over a histogram and run everywhere; the pixel steps
need Pillow; the real read needs the `tesseract` binary too and is skipped
without it. The fixture is drawn here, not committed.
"""

from __future__ import annotations

import shutil
from pathlib import Path

import pytest

from tessellate.core import ocr, ocr_prep


def _hist(*pairs: tuple[int, int]) -> list[int]:
    hist = [0] * 256
    for level, count in pairs:
        hist[level] += count
    return hist


# ---- the decisions, no pixels ------------------------------------------------


def test_otsu_splits_two_clusters_between_them():
    level = ocr_prep.otsu_threshold(_hist((30, 700), (220, 300)))
    assert 30 <= level < 220
    # Every grey from the dark cluster is on the low side, the light one above.
    assert 30 <= level and level + 1 <= 220


def test_otsu_ignores_a_thin_third_tone():
    # Dark canvas, a few mid-grey strokes, a light box: the cut is between the
    # canvas and the box, not through the strokes' own small bump.
    level = ocr_prep.otsu_threshold(_hist((24, 5000), (130, 200), (235, 4000)))
    assert 24 <= level < 235


def test_otsu_of_a_flat_or_empty_picture_does_not_divide_by_zero():
    assert ocr_prep.otsu_threshold(_hist((200, 1000))) in range(256)
    assert ocr_prep.otsu_threshold([0] * 256) == 128


def test_class_means_are_the_two_tones():
    hist = _hist((20, 100), (40, 100), (200, 50), (240, 50))
    low, high = ocr_prep.class_means(hist, ocr_prep.otsu_threshold(hist))
    assert (low, high) == (30.0, 220.0)


def test_the_stretch_sends_the_two_tones_to_black_and_white():
    table = ocr_prep.stretch_table(_hist((30, 700), (220, 300)))
    assert table[30] == 0 and table[220] == 255
    assert table[0] == 0 and table[255] == 255
    assert table == sorted(table)  # never reverses a tone


def test_a_flat_picture_is_not_stretched():
    assert ocr_prep.stretch_table(_hist((120, 500), (124, 500))) == list(range(256))


def test_a_dark_ground_is_inverted_and_a_light_one_is_not():
    assert ocr_prep.is_dark_ground(_hist((24, 800), (235, 200))) is True
    assert ocr_prep.is_dark_ground(_hist((24, 200), (235, 800))) is False
    assert ocr_prep.is_dark_ground([0] * 256) is False


def test_the_scale_brings_small_text_to_about_thirty_pixels():
    assert ocr_prep.scale_factor(8, 400, 160) == pytest.approx(3.75)
    assert ocr_prep.scale_factor(6, 126, 42) == pytest.approx(5.0)


def test_text_that_is_big_enough_or_unmeasured_is_not_scaled():
    assert ocr_prep.scale_factor(30, 400, 160) == 1.0
    assert ocr_prep.scale_factor(26, 400, 160) == 1.0  # under the useful ratio
    assert ocr_prep.scale_factor(0, 400, 160) == 1.0
    assert ocr_prep.scale_factor(8, 0, 0) == 1.0


def test_the_scale_is_capped_and_the_result_stays_under_the_pixel_budget():
    assert ocr_prep.scale_factor(1, 100, 100) == ocr_prep.MAX_SCALE
    scale = ocr_prep.scale_factor(8, 4000, 3000)
    assert scale == 1.0 or 4000 * 3000 * scale * scale <= ocr_prep.MAX_PIXELS * 1.001
    big = ocr_prep.scale_factor(8, 2000, 1500)
    assert 1.0 < big < 3.75
    assert 2000 * 1500 * big * big <= ocr_prep.MAX_PIXELS * 1.001


def test_bands_are_runs_of_inked_rows_and_borders_are_not_lines():
    ink = [0, 0.1, 0.1, 0.1, 0.1, 0, 0, 0.5, 0, 0.1, 0.1, 0.1, 0.1, 0]
    assert ocr_prep.band_heights(ink) == [4, 1, 4]
    assert ocr_prep.text_height_from_bands([4, 1, 4]) == 4.0  # the 1-row rule is dropped
    assert ocr_prep.text_height_from_bands([1, 2]) == 0.0
    assert ocr_prep.text_height_from_bands([]) == 0.0


# ---- the pixel steps, Pillow only ---------------------------------------------


def _drawn(size: int = 8):
    """A board export in miniature: a dark canvas, light boxes, dark labels."""
    pil = pytest.importorskip("PIL")
    from PIL import Image, ImageDraw, ImageFont

    del pil
    image = Image.new("RGB", (420, 160), (24, 26, 32))
    draw = ImageDraw.Draw(image)
    font = ImageFont.load_default(size=size)
    boxes = [
        (20, 20, 110, "Goal"),
        (160, 20, 130, "Launch plan"),
        (310, 20, 90, "Budget"),
        (20, 90, 150, "Review notes"),
        (210, 90, 160, "Open questions"),
    ]
    for x, y, w, label in boxes:
        draw.rectangle([x, y, x + w, y + 30], fill=(235, 238, 242), outline=(120, 130, 150))
        draw.text((x + 8, y + 10), label, fill=(30, 34, 44), font=font)
    return image


def test_a_dark_board_is_inverted_scaled_and_given_full_contrast():
    board = _drawn()
    out = ocr_prep.prepare(board)
    grey = out.image
    assert grey.mode == "L"
    # Measured on the fixture: the label bands are 6 to 7 px, so about 4.5x.
    assert 3.0 <= out.scale <= 6.0
    assert grey.size == (round(420 * out.scale), round(160 * out.scale))
    hist = grey.histogram()
    assert hist[0] > 0 and hist[255] > 0  # both tones reach the ends
    assert not ocr_prep.is_dark_ground(hist)  # the ground is light now


def test_a_crop_of_a_light_box_is_scaled_but_not_inverted():
    crop = _drawn().crop((14, 14, 140, 56))
    out = ocr_prep.prepare(crop)
    assert out.scale > 3.0
    assert not ocr_prep.is_dark_ground(out.image.histogram())
    # The box is the majority and stays light (white), the strokes dark.
    hist = out.image.histogram()
    assert sum(hist[200:]) > sum(hist[:56])


def test_big_text_is_not_enlarged():
    pytest.importorskip("PIL")
    from PIL import Image, ImageDraw, ImageFont

    page = Image.new("L", (600, 120), 255)
    font = ImageFont.load_default(size=36)
    ImageDraw.Draw(page).text((10, 30), "A page title", fill=0, font=font)
    out = ocr_prep.prepare(page)
    assert out.scale == 1.0


def test_a_box_border_is_not_measured_as_a_line_of_text():
    from PIL import Image, ImageDraw

    image = Image.new("L", (200, 100), 255)
    ImageDraw.Draw(image).rectangle([10, 10, 190, 90], outline=0, width=2)
    assert ocr_prep.estimate_text_height(image) == 0.0


def test_a_transparent_ground_is_flattened_onto_white_not_black():
    from PIL import Image

    transparent = Image.new("RGBA", (40, 40), (0, 0, 0, 0))
    assert ocr_prep.to_grey(transparent).getpixel((5, 5)) == 255
    assert not ocr_prep.is_dark_ground(ocr_prep.to_grey(transparent).histogram())


def test_prepare_leaves_its_input_alone():
    board = _drawn()
    before = board.tobytes()
    ocr_prep.prepare(board)
    assert board.tobytes() == before


# ---- every entry goes through the one step -------------------------------------


class _FakeTesseract:
    """Records the pictures and modes it is handed; answers from a script."""

    def __init__(self, answers):
        self.answers = list(answers)
        self.calls: list[tuple[object, str]] = []

    def image_to_string(self, img, **kwargs):
        self.calls.append((img, kwargs.get("config", "")))
        return self.answers.pop(0) if self.answers else ""


def test_a_region_is_read_as_one_block_then_as_sparse_text_then_as_it_came():
    pytest.importorskip("PIL")
    fake = _FakeTesseract(["", "", "Goal"])
    crop = _drawn().crop((14, 14, 140, 56))
    assert ocr._read_with_fallbacks(fake, crop, ocr._REGION_MODES) == "Goal"
    modes = [config for _, config in fake.calls]
    assert modes == ["--psm 6", "--psm 11", "--psm 6"]
    assert fake.calls[0][0] is not crop and fake.calls[1][0] is not crop
    assert fake.calls[2][0] is crop  # the last resort is the original picture


def test_the_first_mode_that_finds_text_stops_the_search():
    pytest.importorskip("PIL")
    fake = _FakeTesseract(["", "Budget", "never asked"])
    assert ocr._read_with_fallbacks(fake, _drawn(), ocr._PAGE_MODES) == "Budget"
    assert [config for _, config in fake.calls] == ["", "--psm 11"]


def test_a_page_read_keeps_tesseracts_default_call_first():
    pytest.importorskip("PIL")
    fake = _FakeTesseract(["Hello"])
    ocr._read_with_fallbacks(fake, _drawn(), ocr._PAGE_MODES)
    assert fake.calls[0][1] == ""  # no config: the call it always was


def test_a_preparation_fault_costs_the_improvement_not_the_read(monkeypatch):
    def broken(img):
        raise RuntimeError("no pixels today")

    monkeypatch.setattr(ocr_prep, "prepare", broken)
    marker = object()
    fake = _FakeTesseract(["still read"])
    assert ocr._read_with_fallbacks(fake, marker, ocr._PAGE_MODES) == "still read"
    assert fake.calls[0][0] is marker


def test_the_three_entries_all_prepare_before_they_read():
    """Whole page, region and the region-of-words read each call `_prepared`;
    a fourth entry added without it would put the old failure back."""
    source = Path(ocr.__file__).read_text(encoding="utf-8")
    assert source.count("_prepared(img)") >= 2  # `_read_with_fallbacks` and `_region_data`
    for name in ("extract_text", "extract_region_text"):
        body = source.split(f"def {name}(")[1].split("\ndef ")[0]
        assert "_read_with_fallbacks(" in body, name
    regions = source.split("def extract_regions(")[1].split("\ndef ")[0]
    assert "_region_data(pytesseract, img)" in regions and "/ scale" in regions
    assert "_prepared(img)" in source.split("def _region_data(")[1].split("\ndef ")[0]


def test_the_region_route_reads_through_the_region_entry():
    from tessellate.api import routes_files

    source = Path(routes_files.__file__).read_text(encoding="utf-8")
    body = source.split("def _region_text(")[1].split("\ndef ")[0]
    assert "_local_region_text(" in body and "_local_text(" not in body


# ---- the real binary -----------------------------------------------------------

needs_tesseract = pytest.mark.skipif(
    shutil.which("tesseract") is None, reason="the tesseract binary is not installed"
)


@pytest.fixture
def real_engine(monkeypatch):
    pytest.importorskip("PIL")
    wrapper = pytest.importorskip("pytesseract")
    #: Another test adopts a fake Windows path into this global; the real
    #: binary is on PATH here (the tests below are skipped when it is not).
    monkeypatch.setattr(wrapper.pytesseract, "tesseract_cmd", "tesseract")
    monkeypatch.setattr(ocr, "effective_language", lambda: "")
    monkeypatch.setattr(ocr, "engine", lambda choice="": "tesseract")


@needs_tesseract
def test_a_region_round_a_small_label_is_read(tmp_path, real_engine):
    """The owner's case: before the preparation this was an empty read."""
    crop = tmp_path / "region.png"
    _drawn().crop((14, 14, 140, 56)).save(crop)
    assert "goal" in ocr.extract_region_text(crop).lower()


@needs_tesseract
def test_the_whole_board_gives_its_labels_not_garbage(tmp_path, real_engine):
    board = tmp_path / "board.png"
    _drawn().save(board)
    text = ocr.extract_text(board).lower()
    # Every label is small and on a dark canvas. Measured with Tesseract 5.3.4:
    # "goal launch plan / review notes open questons" (no "Budget": the page
    # mode drops a lone label, the real read has no sparse pass once it found
    # text). Before the preparation this was garbage or empty.
    found = [w for w in ("goal", "launch", "plan", "review", "notes", "open") if w in text]
    assert len(found) == 6, text


@needs_tesseract
def test_word_boxes_land_on_the_original_not_the_enlarged_picture(tmp_path, real_engine):
    board = tmp_path / "board.png"
    _drawn().save(board)
    out = ocr.extract_regions(board)
    assert out is not None and out["width"] == 420 and out["height"] == 160
    words = [w for region in out["regions"] for w in region["words"]]
    assert words, out
    for word in words:
        assert 0 <= word["x"] <= 1 and word["x"] + word["w"] <= 1.02
        assert 0 <= word["y"] <= 1 and word["y"] + word["h"] <= 1.02
    # The "Goal" label sits in the top-left box of a 420 x 160 board.
    goal = [w for w in words if w["text"].lower().startswith("goal")]
    if goal:
        assert goal[0]["x"] < 0.2 and goal[0]["y"] < 0.4
