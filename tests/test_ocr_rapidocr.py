"""RapidOCR, the second local reader (WORLD_CLASS_PLAN row 31 item 97).

An optional extra (`core/extras.py`'s "rapidocr" row), never a dependency:
nothing imports it at module level, and none of this suite has it installed.
So every test here puts a fake `rapidocr_onnxruntime` (or 2.x `rapidocr`)
module in `sys.modules` and checks the contract around it:

- Tesseract stays the reader whenever both its halves are ready;
- RapidOCR reads when Tesseract is not ready and it is installed;
- its lines come back as `extract_text`'s text and `extract_regions`' blocks,
  with the local reader's stable id (`source: "tesseract"`) and its own name;
- the status, the capabilities and `/models/status` say a local reader is
  there, and the messages name the engine that reads.
"""

from __future__ import annotations

import sys
import types
from pathlib import Path

import pytest

from tessellate.core import extras, ocr

#: Two lines of a paragraph, a gap, and a tall heading-sized line, in pixels on
#: a 200x100 page. Four corners each, clockwise from top-left, as RapidOCR
#: reports them.
LINES = [
    ([[10, 5], [190, 5], [190, 25], [10, 25]], "A big title", 0.98),
    ([[10, 40], [150, 40], [150, 50], [10, 50]], "first line of a paragraph", 0.9),
    ([[10, 52], [140, 52], [140, 62], [10, 62]], "and its second line", 0.8),
    ([[10, 85], [60, 85], [60, 95], [10, 95]], "footer", 0.7),
]


class _Reader1:
    """The 1.x call: `(result, elapse)`, a list of `[box, text, score]`."""

    calls: list[str] = []

    def __call__(self, path):
        _Reader1.calls.append(path)
        return [[box, text, score] for box, text, score in LINES], [0.1, 0.1, 0.1]


class _Output2:
    def __init__(self):
        self.boxes = [box for box, _, _ in LINES]
        self.txts = tuple(text for _, text, _ in LINES)
        self.scores = tuple(score for _, _, score in LINES)


class _Reader2:
    """The 2.x call: an object with `boxes`, `txts` and `scores`."""

    def __call__(self, path):
        return _Output2()


@pytest.fixture
def page(tmp_path: Path) -> Path:
    """A real 200x100 white PNG, written without Pillow: CI installs no
    imaging library, and the reader reads only the page's size from it."""
    import struct
    import zlib

    def chunk(kind: bytes, data: bytes) -> bytes:
        return struct.pack(">I", len(data)) + kind + data + struct.pack(">I", zlib.crc32(kind + data))

    width, height = 200, 100
    rows = b"".join(b"\x00" + b"\xff" * (width * 3) for _ in range(height))
    png = (
        b"\x89PNG\r\n\x1a\n"
        + chunk(b"IHDR", struct.pack(">IIBBBBB", width, height, 8, 2, 0, 0, 0))
        + chunk(b"IDAT", zlib.compress(rows))
        + chunk(b"IEND", b"")
    )
    path = tmp_path / "page.png"
    path.write_bytes(png)
    return path


def _install(monkeypatch, module_name: str, reader_cls) -> None:
    module = types.ModuleType(module_name)
    module.RapidOCR = reader_cls
    monkeypatch.setitem(sys.modules, module_name, module)
    real_find = ocr.importlib.util.find_spec
    monkeypatch.setattr(
        ocr.importlib.util,
        "find_spec",
        lambda name, *a: object() if name == module_name else (None if name in ocr.RAPIDOCR_MODULES else real_find(name, *a)),
    )
    ocr._rapidocr_reader.cache_clear()


@pytest.fixture
def no_tesseract(monkeypatch):
    monkeypatch.setattr(ocr, "tesseract_available", lambda: False)
    yield
    ocr._rapidocr_reader.cache_clear()


def test_nothing_installed_means_no_engine(monkeypatch, no_tesseract):
    monkeypatch.setattr(ocr, "rapidocr_available", lambda: False)
    assert ocr.engine() == "" and not ocr.local_available()
    status = ocr.engine_status()
    assert status["ready"] is False and status["engine"] == "" and status["fix"] == "install"
    assert "RapidOCR" in ocr.unavailable_reason()


def test_tesseract_stays_the_reader_when_it_is_ready(monkeypatch):
    _install(monkeypatch, "rapidocr_onnxruntime", _Reader1)
    monkeypatch.setattr(ocr, "tesseract_available", lambda: True)
    monkeypatch.setattr(ocr, "packages_available", lambda: True)
    assert ocr.rapidocr_available()
    assert ocr.engine() == "tesseract"
    assert ocr.engine_status()["engine_name"] == "Tesseract"


def test_rapidocr_reads_when_tesseract_is_not_ready(monkeypatch, no_tesseract, page):
    _install(monkeypatch, "rapidocr_onnxruntime", _Reader1)
    assert ocr.engine() == "rapidocr" and ocr.engine_name() == "RapidOCR"
    status = ocr.engine_status()
    assert status["ready"] is True and status["rapidocr"] is True and status["fix"] == ""
    assert ocr.unavailable_reason() == ""
    text = ocr.extract_text(page)
    assert text.split("\n") == [t for _, t, _ in LINES]


def test_the_reader_is_built_once_per_process(monkeypatch, no_tesseract, page):
    built = []

    class Counting(_Reader1):
        def __init__(self):
            built.append(1)

    _install(monkeypatch, "rapidocr_onnxruntime", Counting)
    ocr.extract_text(page)
    ocr.extract_text(page)
    assert len(built) == 1


def test_regions_group_lines_into_blocks_with_the_local_id(monkeypatch, no_tesseract, page):
    _install(monkeypatch, "rapidocr_onnxruntime", _Reader1)
    out = ocr.extract_regions(page)
    assert out["source"] == "tesseract" and out["engine"] == "rapidocr"
    assert (out["width"], out["height"]) == (200, 100)
    regions = out["regions"]
    # The title, the two-line paragraph joined, and the footer after a gap.
    assert [r["text"] for r in regions] == [
        "A big title",
        "first line of a paragraph\nand its second line",
        "footer",
    ]
    assert regions[0]["kind"] == "heading" and regions[1]["kind"] == "text"
    assert regions[1]["box"] == {"x": 0.05, "y": 0.4, "w": 0.7, "h": 0.22}
    assert regions[1]["confidence"] == 85.0


def test_the_2x_package_and_result_shape_are_read(monkeypatch, no_tesseract, page):
    _install(monkeypatch, "rapidocr", _Reader2)
    assert ocr.engine() == "rapidocr"
    assert ocr.extract_text(page).startswith("A big title\n")
    assert len(ocr.extract_regions(page)["regions"]) == 3


def test_a_page_with_no_text_and_a_failing_reader(monkeypatch, no_tesseract, page):
    class Empty:
        def __call__(self, path):
            return None, None

    _install(monkeypatch, "rapidocr_onnxruntime", Empty)
    assert ocr.extract_text(page) == ""
    assert ocr.extract_regions(page)["regions"] == []

    class Broken:
        def __call__(self, path):
            raise RuntimeError("onnxruntime fell over")

    _install(monkeypatch, "rapidocr_onnxruntime", Broken)
    assert ocr.extract_text(page) == ""
    assert ocr.extract_regions(page) is None


def test_it_is_an_optional_extra_and_never_a_dependency():
    by_id = {extra.id: extra for extra in extras.EXTRAS}
    row = by_id["rapidocr"]
    assert row.packages == ("rapidocr_onnxruntime",) and row.module == "rapidocr_onnxruntime"
    assert "Tesseract stays the reader" in row.enables
    # In the Vision bundle beside Tesseract (the half that most often fails
    # to install is Tesseract's program), never in requirements.
    assert [b.id for b in extras.BUNDLES if "rapidocr" in b.extras] == ["vision"]
    root = Path(__file__).resolve().parents[1]
    # Never a requirement line. The "Optional extras" comment block in
    # requirements.txt does name it, as it names every extra
    # (test_failure_remedies), and a comment installs nothing.
    for name in ("requirements.txt", "pyproject.toml"):
        path = root / name
        if path.exists():
            live = [line for line in path.read_text(encoding="utf-8").lower().splitlines() if not line.lstrip().startswith("#")]
            assert not any("rapidocr" in line for line in live), name
    source = (root / "src" / "tessellate" / "core" / "ocr.py").read_text(encoding="utf-8")
    assert "\nimport rapidocr" not in source and "\nfrom rapidocr" not in source


def test_the_routes_say_a_local_reader_is_there(monkeypatch, no_tesseract, client):
    _install(monkeypatch, "rapidocr_onnxruntime", _Reader1)
    caps = client.get("/capabilities").json()
    ocr_caps = caps["features"]["ocr"]
    assert ocr_caps["tesseract"] is True and ocr_caps["engine"] == "rapidocr"
    readers = client.get("/ocr-readers").json()
    assert readers["tesseract"] is True and readers["engine"]["engine_name"] == "RapidOCR"


def test_a_dark_page_is_inverted_before_rapidocr_reads_it(monkeypatch, no_tesseract, tmp_path):
    """L703: light text on a dark ground is turned dark on light for RapidOCR,
    and the prepared copy is removed after the read; a plain page is read as
    it came."""
    image = pytest.importorskip("PIL.Image")
    dark = tmp_path / "dark.png"
    image.new("RGB", (200, 100), (10, 10, 10)).save(dark)
    seen: list[tuple[str, int]] = []

    class Peeking(_Reader1):
        def __call__(self, path):
            with image.open(path) as img:
                seen.append((path, img.convert("L").getpixel((5, 5))))
            return super().__call__(path)

    _install(monkeypatch, "rapidocr_onnxruntime", Peeking)
    lines = ocr._rapidocr_lines(dark)
    (read_path, ground), = seen
    assert read_path != str(dark) and ground > 200
    assert not Path(read_path).exists()
    assert lines and lines[0][0][0] == [10.0, 5.0]


def test_a_plain_page_is_read_as_it_came(monkeypatch, no_tesseract, page):
    _Reader1.calls.clear()
    _install(monkeypatch, "rapidocr_onnxruntime", _Reader1)
    ocr._rapidocr_lines(page)
    assert _Reader1.calls == [str(page)]
