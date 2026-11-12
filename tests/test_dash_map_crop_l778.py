"""Source text: a tall map in the dashboard's short box is cropped around its
centre instead of shrunk to an unreadable strip (L778, owner decided
2026-11-12). Probe: a 25-topic tall map showed 25 nodes at 10 px in the plain
box; cropped, the window is 0 41.6 30 16.8 and shows 5 readable nodes."""

from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
JS = ROOT / "frontend" / "js"


def test_the_dashboard_asks_for_a_crop():
    assert 'mapPreview(board, { size: "card", crop: true })' in (JS / "dash-boards.js").read_text()


def test_the_crop_is_a_centred_window_of_the_box_shape():
    src = (JS / "map-preview.js").read_text()
    assert "vh / vw > geo.h / geo.w" in src, "only a map taller than the box is cropped"
    assert "(vh - cropH) / 2" in src, "the window sits around the centre"
    assert 'svg.dataset.crop = "centre"' in src


def test_a_raster_preview_is_cropped_the_same_way():
    src = (JS / "note-cards.js").read_text()
    assert 'if (crop) img.style.objectFit = "cover"' in src
    assert "mapPreviewDraw(svg, board, size, { crop })" in src
