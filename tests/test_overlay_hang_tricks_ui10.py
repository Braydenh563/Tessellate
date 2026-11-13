"""The desk's two other hanging tricks, `hang_sloth` and `hang_feet` (L-ui-modernisation-10). A fixed clock and seeded randomness,
the shipped frames' own boxes; real Windows is unverified."""
from __future__ import annotations

import pytest

from tessellate.core.overlay import behaviour as bh
from tessellate.core.overlay import runner, sprites
from tests.test_overlay_ride_1670 import LOOKS, make

TICK = 0.1
TRICKS = {"hang_one": "hang_one_hand", "hang_sloth": "sloth", "hang_feet": "hang_by_feet"}


@pytest.mark.parametrize("look", LOOKS)
def test_each_new_hang_picture_is_registered_to_the_hang_and_differs_from_the_stand(look: str) -> None:
    """Source text: "Draw the missing desk frames: hang by feet, sloth, chair, lean, tail-curl pot." The sloth and the flip are
    drawn about the hang's grip (the same top row, the engine places a hang by it) and are not the stand or the hang."""
    pytest.importorskip("PIL")
    from PIL import Image, ImageChops

    s = sprites.SpriteSet(look)
    assert {"hang_sloth", "hang_feet"} <= s.extras()
    box = s.metrics(96)
    top = box[("hang", False)][1]
    with Image.open(s.directory / "stand.png").convert("RGBA") as stand:
        want = stand.getchannel("A").point(lambda a: 255 if a >= 230 else 0)
        for name in ("hang_sloth", "hang_feet"):
            assert abs(box[(name, False)][1] - top) <= 2, (name, box[(name, False)], top)
            with Image.open(s.directory / f"{name}.png").convert("RGBA") as im:
                solid = im.getchannel("A").point(lambda a: 255 if a >= 230 else 0)
                assert sum(ImageChops.difference(solid, want).point(lambda v: 1 if v else 0).histogram()[1:]) > 3000, name


def test_the_hang_tricks_are_hang_only_acts_that_the_table_never_picks() -> None:
    """Source text: "Draw the missing desk frames: hang by feet, sloth, chair, lean, tail-curl pot." Each trick is a
    `where="hang"` activity drawing its own picture, so the weighted table of a floor or a perch never has it."""
    for frame, act in TRICKS.items():
        assert bh.ACTIVITIES[act].where == "hang" and bh.ACTIVITIES[act].frame == frame
    assert all(frame in runner.BLENDED for frame in TRICKS)
    assert {sprites.EXTRA_FALLBACK["hang_sloth"], sprites.EXTRA_FALLBACK["hang_feet"]} == {"hang"}


@pytest.mark.parametrize("look", LOOKS)
@pytest.mark.parametrize("gait", ["walk", "float"])
def test_a_long_hang_shows_each_trick_inside_a_calm_hang_and_feeds_the_mind(look: str, gait: str) -> None:
    """Source text: "Draw the missing desk frames: hang by feet, sloth, chair, lean, tail-curl pot." Over a few long hangs the
    one-handed hold, the sleeping hang and the flip all come, only in a calm hang and not in its last seconds."""
    seen: set[str] = set()
    done: set[str] = set()
    for seed in range(1, 13):
        e, s = make(look, gait, seed)
        e.extra_frames = s.extras()
        t = 1.0
        e.update(t)
        e._perform("hang", t)
        while t < 300 and (e.state == "hang" or t < 5):
            t += TICK
            out = e.update(t)
            if out.frame in TRICKS:
                assert e.state == "hang" and e.pulling is None and e.swing_to is None and not e.releasing
                assert e.state_until - t >= 1.5 or e.hang_one_until > t
                seen.add(out.frame)
        done |= {a for a in TRICKS.values() if e.mind.done.get(a) is not None}
    assert seen == set(TRICKS) and done == set(TRICKS.values()), (seen, done)


@pytest.mark.parametrize("look", LOOKS)
def test_a_look_without_the_new_pictures_draws_the_plain_hang(look: str) -> None:
    """Source text: "Draw the missing desk frames: hang by feet, sloth, chair, lean, tail-curl pot." Without the picture of a
    trick it never begins, and a name drawn for it falls back to the hang."""
    e, _s = make(look, "walk", 3)
    e.extra_frames = frozenset({"hang_one"})
    for _ in range(40):
        e._hang_one_reset(1.0)
        e.hang_one_until = 99.0
        assert e._extra_name("hang", 2.0) in ("hang_one",)
    e.extra_frames = frozenset()
    assert e._extra_name("hang_sloth", 2.0) == "hang" and e._extra_name("hang_feet", 2.0) == "hang"
