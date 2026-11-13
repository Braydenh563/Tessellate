"""The desk's reactions to a note and a remark wear what the app's do (L-ui-modernisation-11): reading glasses for a long
note, both hands over the eyes for a private one, a speech bubble for a remark. A fixed clock; real Windows is unverified."""
from __future__ import annotations

import pytest

pytest.importorskip("PIL")

from tessellate.core.overlay import extras, props  # noqa: E402
from tessellate.core.overlay.sprites import SpriteSet  # noqa: E402
from tests.test_overlay_ride_1670 import LOOKS, make  # noqa: E402

#: reaction -> (the act it plays, the prop that act wears)
WORN = {"long_note": ("read_glasses", "glasses"), "private_note": ("cover_eyes", "hands"), "remark": ("remark_say", "bubble")}


def test_each_reaction_plays_an_act_that_wears_its_prop() -> None:
    """Source text: "Bring desk note and search reactions to app parity: glasses, shy hands, bubble." The long note, the private
    note and the remark each play a reaction act with its own prop (the glasses, the hands, the bubble)."""
    for kind, (act, prop) in WORN.items():
        assert extras.REACTIONS[kind].act == act
        assert extras.REACT_ACTS[act].where == "react"
        spec = props.REACT_PROPS[act]
        assert spec.prop == prop
        assert props.view(act, 0.5, 1.2, 3.0) == (prop, int(1.2 * spec.fps) % spec.steps, 3)
        assert props.view(act, 0.0, 0.0, 3.0) is None  # fetched in, not worn at the first instant
        assert props.view(act, 1.0, 3.0, 3.0) is None  # and put away at the end
    assert not set(props.REACT_PROPS) & (set(props.PROP_ACTS) | set(props.SPELL_ACTS))  # never a pick of the mind's own


@pytest.mark.parametrize("look", LOOKS)
def test_each_prop_is_drawn_moves_and_the_bubble_grows_the_canvas(look: str) -> None:
    """Source text: "Bring desk note and search reactions to app parity: glasses, shy hands, bubble." Drawn on the frame the act
    uses: it changes the picture, differs from step to step, grows in by size, and sits on the other side when it faces left."""
    s = SpriteSet(look)
    for act, spec in props.REACT_PROPS.items():
        base = s.frame("sit" if act == "read_glasses" else "stand", 96, False)
        whole = props.draw(base, (spec.prop, 0, 3), False)
        assert whole.bgra != base.bgra, act
        assert props.draw(base, (spec.prop, 1, 3), False).bgra != whole.bgra, act
        assert props.draw(base, (spec.prop, 0, 1), False).bgra != whole.bgra, act
        if spec.prop == "bubble":
            assert props.draw(base, (spec.prop, 0, 3), True).bgra != whole.bgra  # on the other side when it faces left
            assert whole.width > base.width and whole.height > base.height  # room round the figure, the window keeps its place


@pytest.mark.parametrize("look", LOOKS)
def test_the_engine_draws_the_prop_while_the_reaction_plays(look: str) -> None:
    """Source text: "Bring desk note and search reactions to app parity: glasses, shy hands, bubble." Through the engine: firing the
    reaction puts the prop on `Output.prop` partway through its act and takes it off after."""
    for kind, (act, prop) in WORN.items():
        e, s = make(look, "float", 3)
        e.extra_frames = s.extras()
        e.update(1.0)
        e.ex.cool.clear()
        assert e.ex.fire(kind, 2.0), kind
        seen: set[str] = set()
        t = 2.0
        for _ in range(int(extras.REACT_ACTS[act].seconds[0] * 10) - 2):  # only while the reaction plays, not the mind's next act
            t += 0.1
            out = e.update(t)
            if out.prop is not None:
                seen.add(out.prop[0])
        assert seen == {prop}, (kind, seen)
        assert e.update(t + 30.0).prop is None
