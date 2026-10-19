"""A shape's own keep-proportions property (INBOX 1313, plan row 5)."""

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
WB = (ROOT / "frontend" / "js" / "whiteboard.js").read_text(encoding="utf-8")
FMT = (ROOT / "frontend" / "js" / "whiteboard-format.js").read_text(encoding="utf-8")


def test_the_flag_lives_in_the_data_blob_of_objects_and_shapes() -> None:
    assert "data.keep_ratio = true" in WB
    assert "keep_ratio: on || undefined" in WB


def test_object_and_sketch_corner_drags_read_the_flag() -> None:
    assert 'wbKeepsRatio("object", d)' in WB
    assert 'wbKeepsRatio("sketch", sketch)' in WB


def test_the_link_button_sets_it_for_a_single_shape() -> None:
    assert "wbSetKeepRatio(only.kind, only.item" in FMT
    assert "wbKeepsRatio(only.kind, only.item)" in FMT
