"""INBOX 1692, the owner 2026-11-08 (screenshot: the desk Atlas, its resize ring far up and right of it): "the
resize circle is still really far away". The ring hangs off the head (standing) or the feet (hanging), not off
the corner of a box that a tail swirl or a hair trail widens."""

from __future__ import annotations

import pytest

pytest.importorskip("PIL")

from tessellate.core.overlay import sizing  # noqa: E402
from tessellate.core.overlay.sprites import Frame, premultiplied_bgra  # noqa: E402


def atlas_like(hanging: bool) -> Frame:
    """A narrow head and body over a wide tail swirl to the right (flipped top to bottom when hanging)."""
    from PIL import Image, ImageDraw

    image = Image.new("RGBA", (400, 400), (0, 0, 0, 0))
    draw = ImageDraw.Draw(image)
    draw.ellipse((120, 60, 200, 140), fill=(200, 180, 255, 255))  # the head
    draw.rectangle((130, 140, 190, 280), fill=(200, 180, 255, 255))  # the body
    draw.ellipse((100, 260, 330, 340), fill=(200, 180, 255, 255))  # the tail swirl, wide and to the right
    if hanging:
        image = image.transpose(Image.FLIP_TOP_BOTTOM)
    return Frame(400, 400, premultiplied_bgra(image), 0, 0, (0, 0, 400, 400))


@pytest.mark.parametrize("hanging", [False, True])
def test_the_ring_hangs_by_the_head_not_off_the_tail(hanging: bool) -> None:
    frame = atlas_like(hanging)
    box = sizing.corner_box(frame, hanging)
    hit = sizing.hit_box(box, hanging, 96)
    head_right = 201  # the head's right edge (its bbox is exclusive)
    assert 0 <= hit[0] - head_right <= 8, (hit, box)
    edge = sizing.solid_box(frame)
    if hanging:
        assert 0 <= hit[1] - edge[3] <= 8, (hit, edge)
    else:
        assert 0 <= edge[1] - hit[3] <= 8, (hit, edge)


def test_a_plain_figure_keeps_its_corner() -> None:
    """A figure as wide at the head as anywhere keeps the solid corner (the 1692 h test's shape)."""
    from PIL import Image, ImageDraw

    image = Image.new("RGBA", (300, 300), (0, 0, 0, 0))
    ImageDraw.Draw(image).rectangle((100, 120, 180, 260), fill=(200, 100, 50, 255))
    frame = Frame(300, 300, premultiplied_bgra(image), 0, 0, (100, 120, 181, 261))
    assert sizing.corner_box(frame, False) == sizing.solid_box(frame) == (100, 120, 181, 261)


def test_the_runner_places_the_ring_by_the_corner_box() -> None:
    import inspect

    from tessellate.core.overlay import runner

    src = inspect.getsource(runner)
    assert "sizing.corner_box(frame, hanging)" in src and "sizing.solid_box(frame)" not in src
