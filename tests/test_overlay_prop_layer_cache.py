"""L-general-72: the owner's log showed slow overlay ticks (35 to 88 ms) in the act state. Measured on FakeWin32 at
2560x1504 and dpi 192 over 20 s: act ticks had a median of 31.1 ms (542 of 822 over 30 ms), and the profile put 21 ms
of each in `props.draw`'s supersampled resize, redone on most ticks because the runner's decor cache keys on the whole
picture (figure frame, face, prop phase). The prop layer depends only on the prop and the figure's box, so it is
built once per (prop, phase, size, side, box) and only the composite runs per picture."""

from __future__ import annotations

import pytest

pytest.importorskip("PIL")

from PIL import Image  # noqa: E402

from tessellate.core.overlay import props  # noqa: E402
from tessellate.core.overlay import sprites as sp  # noqa: E402
from tessellate.core.overlay.sprites import SpriteSet  # noqa: E402


def _resizes(monkeypatch: pytest.MonkeyPatch) -> list[int]:
    seen: list[int] = []
    orig = Image.Image.resize

    def counted(self, *a, **kw):
        if not getattr(counted, "inside", False):  # PIL's RGBA resize calls itself once more
            seen.append(1)
        counted.inside = True
        try:
            return orig(self, *a, **kw)
        finally:
            counted.inside = False

    monkeypatch.setattr(Image.Image, "resize", counted)
    return seen


def test_the_prop_layer_is_built_once_for_pictures_that_share_a_box(monkeypatch: pytest.MonkeyPatch) -> None:
    spec, act, _w = props.PROP_ACTS["read_book"]
    frame = act.frame if isinstance(act.frame, str) else act.frame[0][1]
    base = SpriteSet("masculine").frame(frame, 192, False)
    other = sp.Frame(base.width, base.height, bytes(len(base.bgra)), base.pad_x, base.pad_y, base.box)  # a blink, say
    props.clear_layers()
    seen = _resizes(monkeypatch)
    first = props.draw(base, (spec.prop, 0, 3), False)
    props.draw(other, (spec.prop, 0, 3), False)
    assert len(seen) == 1
    props.draw(base, (spec.prop, 1, 3), False)  # a new phase is a new layer
    assert len(seen) == 2
    again = props.draw(base, (spec.prop, 0, 3), False)
    assert again == first and len(seen) == 2


def test_a_kept_layer_draws_the_same_picture_as_a_fresh_one() -> None:
    s = SpriteSet("feminine")
    for name, (spec, act, _w) in props.PROP_ACTS.items():
        frame = act.frame if isinstance(act.frame, str) else act.frame[0][1]
        base = s.frame(frame, 96, False)
        props.clear_layers()
        fresh = props.draw(base, (spec.prop, 0, 2), True)
        assert props.draw(base, (spec.prop, 0, 2), True) == fresh, name


def test_the_kept_layers_are_bounded() -> None:
    spec, act, _w = props.PROP_ACTS["read_book"]
    frame = act.frame if isinstance(act.frame, str) else act.frame[0][1]
    base = SpriteSet("masculine").frame(frame, 96, False)
    props.clear_layers()
    for i in range(props.LAYER_KEEP + 10):
        moved = base._replace(box=(base.box[0], base.box[1], base.box[2], base.box[3] - (i % 40) - 1 - i // 40))
        props.draw(moved, (spec.prop, 0, 3), False)
    assert props.layer_count() <= props.LAYER_KEEP
