"""JPG, WebP and copy as an image (whiteboard-1018 step 9; WHITEBOARD_PLAN
section 14). The export dialog drew PNG, SVG and PDF; the other two raster
formats and the clipboard are rows in the same format list, sharing the PNG's
size and ground. The file bytes and the clipboard are checked in a browser
(the sweep named in HISTORY); this holds the shape of the code."""

import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
WB = (ROOT / "frontend" / "js" / "whiteboard.js").read_text(encoding="utf-8")
CMD = (ROOT / "frontend" / "js" / "whiteboard-commands.js").read_text(encoding="utf-8")


def _function(name: str, prefix: str = "") -> str:
    start = WB.index(f"{prefix}function {name}(")
    return WB[start : WB.index("\n}\n", start) + 3]


def _format_row(value: str) -> str:
    start = WB.index(f'value: "{value}"')
    return WB[start : WB.index("\n  },", start)]


def test_the_format_list_offers_jpg_webp_and_copy():
    for value in ("jpg", "webp", "copy"):
        row = _format_row(value)
        assert 'scopes: ["selection", "visible", "whole"]' in row, value
        assert "picture: true" in row, value
    #: A JPEG has no alpha, so the dialog must not offer a transparent ground for it.
    assert "noAlpha: true" in _format_row("jpg")
    assert "wbExportPicture(scope, \"webp\")" in _format_row("webp")
    assert "wbExportCopyImage(scope)" in _format_row("copy")


def test_the_dialog_reads_picture_from_the_row_not_a_name_list():
    dialog = _function("wbExportBoard")
    assert "format.picture" in dialog and 'format.value === "png"' not in dialog
    assert "noAlpha" in dialog
    for value in ("png", "library"):
        assert "picture: true" in _format_row(value), value


def test_the_picture_formats_name_their_mime_and_extension():
    table = WB[WB.index("const WB_EXPORT_PICTURES") :]
    table = table[: table.index("});")]
    assert '"image/jpeg"' in table and '"image/webp"' in table
    assert "extension: \"jpg\"" in table and "extension: \"webp\"" in table
    picture = _function("wbExportPicture", "async ")
    assert "wbRasterizeSvg(" in picture and "spec.quality" in picture and "spec.mime" in picture
    #: A browser that cannot encode a type hands back a PNG; saying so beats a ".webp" that is a PNG.
    assert "blob.type !== spec.mime" in picture
    assert "transparent && spec.alpha" in picture
    assert "saveFile(" in picture


def test_the_rasteriser_takes_a_quality():
    raster = _function("wbRasterizeSvg", "async ")
    assert re.search(r"wbRasterizeSvg\(svgInput, width, height, mime, quality\)", raster)
    assert "mime,\n        quality" in raster or "mime, quality" in raster


def test_copy_as_an_image_writes_a_png_to_the_clipboard():
    copy = _function("wbExportCopyImage", "async ")
    assert "navigator.clipboard" in copy and "ClipboardItem" in copy and '"image/png"' in copy
    #: Without the API the person is told what to do instead, not left with nothing.
    assert "Export a PNG instead" in copy
    assert "wbBuildExportSvg(" in copy


def test_a_command_copies_the_picture_and_its_errors_are_said():
    row = re.search(r'\{ id: "copy-image".*', CMD).group(0)
    assert 'group: "Board"' in row and 'surface: "both"' in row and "wbCopyAsImage" in row
    handler = _function("wbCopyAsImage", "async ")
    assert "wbExportCopyImage(" in handler and "toast(" in handler
