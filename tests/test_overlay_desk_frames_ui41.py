"""The desk frames still missing (L-ui-modernisation-41, -42): the lean at a side edge, the floater on its back, the chair, the pot
held in the tail curl and the note card under the card nap. A fixed clock and seeded randomness; real Windows is unverified."""
from __future__ import annotations

import pytest

pytest.importorskip("PIL")

from tessellate.core.overlay import behaviour as bh  # noqa: E402
from tessellate.core.overlay import extras, props, sprites  # noqa: E402
from pathlib import Path  # noqa: E402

from tessellate.core.overlay.sprites import SpriteSet  # noqa: E402
from tests.test_overlay_ride_1670 import LOOKS, make  # noqa: E402

NEW = ("lean", "back_float")


@pytest.mark.parametrize("look", LOOKS)
def test_the_lean_and_the_back_float_are_shipped_and_differ_from_the_stand(look: str) -> None:
    """Source text: "Draw the remaining desk frames: lean, back_float, chair prop; each needs a spec in render_desk_frames.js, an
    EXTRA_FRAMES entry and an act that draws it." Both are in the shipped set, not the stand, and have a fallback."""
    from PIL import Image, ImageChops

    s = SpriteSet(look)
    assert set(NEW) <= s.extras() and set(NEW) <= set(sprites.EXTRA_FRAMES) and set(NEW) <= set(sprites.EXTRA_FALLBACK)
    with Image.open(s.directory / "stand.png").convert("RGBA") as stand:
        want = stand.getchannel("A").point(lambda a: 255 if a >= 230 else 0)
        for name in NEW:
            with Image.open(s.directory / f"{name}.png").convert("RGBA") as im:
                solid = im.getchannel("A").point(lambda a: 255 if a >= 230 else 0)
                assert sum(ImageChops.difference(solid, want).point(lambda v: 1 if v else 0).histogram()[1:]) > 3000, name


def test_the_spec_for_each_new_frame_is_in_the_renderer() -> None:
    """Source text: "Draw the remaining desk frames: lean, back_float, chair prop; each needs a spec in render_desk_frames.js." """
    text = (Path(__file__).resolve().parents[1] / "scripts" / "render_desk_frames.js").read_text(encoding="utf-8")
    assert text and all(f'name: "{n}"' in text for n in NEW)


@pytest.mark.parametrize("look", LOOKS)
@pytest.mark.parametrize("edge", ["left", "right"])
def test_a_peek_out_of_a_side_edge_leans_and_a_look_without_the_picture_stands(look: str, edge: str) -> None:
    """Source text: "Draw the remaining desk frames: lean, back_float, chair prop." The side peek (the app's `peekside`) draws the
    lean; a set without the picture draws the stand; the top and bottom peeks never lean."""
    e, s = make(look, "walk", 3)
    e.extra_frames = s.extras()
    e.update(1.0)
    e.state, e.peek_edge, e.peek_started, e.sink, e.sink_max = "peek", edge, 1.0, 0.3, 0.5
    assert e._frame(2.0) == "lean"
    e.extra_frames = frozenset()
    assert e._frame(2.0) in ("stand", "look")
    e.extra_frames = s.extras()
    e.peek_edge = "bottom"
    assert e._frame(2.0) in ("stand", "look")


@pytest.mark.parametrize("look", LOOKS)
def test_the_back_float_is_a_floaters_act_only(look: str) -> None:
    """Source text: "Draw the remaining desk frames: lean, back_float, chair prop." `back_float` is an act of a floating look
    drawing its own picture: the mind offers it to a floater and never to a walker, and the engine draws the picture in it."""
    extras.register()
    act = bh.ACTIVITIES["back_float"]
    assert act.frame == "back_float" and act.gait == "float" and bh.BASE_WEIGHT["back_float"] > 0
    for gait, offered in (("float", True), ("walk", False)):
        e, s = make(look, gait, 3)
        assert ("back_float" in dict(e.mind.weights(100.0, gait))) is offered, gait
    e, s = make(look, "float", 3)
    e.extra_frames = s.extras()
    e.update(1.0)
    e._start_act("back_float", 2.0)
    assert e.update(3.0).frame == "back_float"
    e.extra_frames = frozenset()
    assert e._extra_name("back_float", 3.1) == "idle0"  # no picture: the idle cycle it floats on


@pytest.mark.parametrize("look", LOOKS)
def test_the_chair_act_draws_its_chair_under_the_sitter(look: str) -> None:
    """Source text: "Draw the remaining desk frames: lean, back_float, chair prop." `sit_chair` is a sitting prop act whose chair is
    drawn under the figure (the legs and the seat show below the sit), fetched in by size and moving a step."""
    extras.register()
    spec, act, weight = props.PROP_ACTS["sit_chair"]
    assert spec.prop == "chair" and spec.under and act.frame == "sit" and weight > 0
    assert props.view("sit_chair", 0.5, 1.0, 30.0) == ("chair", int(1.0 * spec.fps) % spec.steps, 3)
    assert props.view("sit_chair", 0.0, 0.0, 30.0) is None
    s = SpriteSet(look)
    base = s.frame("sit", 96, False)
    whole = props.draw(base, ("chair", 0, 3), False)
    assert whole.bgra != base.bgra and props.draw(base, ("chair", 1, 3), False).bgra != whole.bgra
    assert props.draw(base, ("chair", 0, 1), False).bgra != whole.bgra
    assert props.draw(base, ("chair", 0, 3), True).bgra != whole.bgra  # the back is behind it on the other side when it faces left


@pytest.mark.parametrize("look", LOOKS)
def test_the_card_nap_lies_on_a_note_card_and_the_pot_is_held_by_the_tail(look: str) -> None:
    """Source text: "Draw the pot in the tail curl and a card box for the desk card nap." The nap gets a note card drawn under the
    sleeper; the plant's pot is drawn under the figure so its tail curl lies over the pot's edge."""
    extras.register()
    assert props.spec_of("card_nap").prop == "notecard" and props.spec_of("card_nap").under
    assert props.SPELL_ACTS["water_plant"][0].under
    assert props.view("card_nap", 0.5, 2.0, 10.0)[0] == "notecard"
    s = SpriteSet(look)
    for frame, prop in (("sleep", "notecard"), ("stand", "plant")):
        base = s.frame(frame, 96, False)
        top = props.draw(base, (prop, 0, 3), False)
        assert top.bgra != base.bgra and props.draw(base, (prop, 1, 3), False).bgra != top.bgra
    assert props.DOING["card_nap"] and props.DOING["sit_chair"]
