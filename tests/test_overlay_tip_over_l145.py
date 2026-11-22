"""L145: a prop a grab knocks out of the companion's hands lies tipped over beside it once it stands again, then is put away."""

from __future__ import annotations

import pytest

from tessellate.core.overlay import extras, props
from tessellate.core.overlay import sprites as sp
from tests.test_overlay_moves import make, step, throw


def empty(w: int = 132, h: int = 151) -> sp.Frame:
    from PIL import Image

    return sp.Frame(w, h, sp.premultiplied_bgra(Image.new("RGBA", (w, h), (0, 0, 0, 0))), 0, 0, (20, 0, w - 19, h))


def rows(frame: sp.Frame) -> tuple[int, int]:
    """The first and last row that has any prop in it."""
    from PIL import Image

    img = Image.frombytes("RGBA", (frame.width, frame.height), frame.bgra, "raw", "BGRa")
    box = img.getchannel("A").point(lambda a: 255 if a > 40 else 0).getbbox()
    assert box is not None
    return box[1], box[3]


@pytest.mark.parametrize("name", sorted(props.TIP_PROPS))
def test_a_tipped_prop_lies_lower_than_it_stands_and_stays_on_the_canvas(name: str) -> None:
    f = empty()
    up = rows(props.draw(f, (name, 0, 3), False))
    lying = props.draw(f, (name, 0, props.TIPPED), False)
    top, bottom = rows(lying)
    assert top > up[0], (name, up, top)  # it no longer reaches as high
    assert bottom <= lying.height - 1, name  # inside the canvas the draw grew
    assert (lying.box[3]) - 12 <= bottom <= lying.box[3] + 6, (name, bottom, lying.box)  # down on the floor line, at the feet


def test_a_prop_that_is_not_held_is_not_tipped() -> None:
    f = empty()
    for name in ("blanket", "beanbag", "mat", "stars"):
        assert name not in props.TIP_PROPS
        a, b = props.draw(f, (name, 0, 3), False), props.draw(f, (name, 0, props.TIPPED), False)
        assert a.bgra == b.bgra, name


def thrown_with(act: str, seed: int = 4, ended: bool = False):
    e = make(seed=seed)
    t = 1.0
    e.update(t)
    e.act_len = 90.0
    e._start_act(act, t)
    t, _ = step(e, t, 6.0)
    assert e.state == "act" and e.act == act
    assert e.update(t).prop is not None and e.update(t).prop[2] == 3
    if ended:  # the act runs its length out first, so there is nothing in its hands when it is picked up
        e.act_len, e.state_until = 1.0, t
        t, _ = step(e, t, 4.0)
        assert e.state != "act" and e.ex.holding is None
    e.update(t, event=("down", int(e.x + 40), int(e.y + 60)))
    out, t = throw(e, to=(int(e.x + 700), int(e.y - 300)), start=(int(e.x + 40), int(e.y + 60)), t0=t + 0.1)
    return e, t


def test_the_cup_it_was_sipping_from_lies_tipped_beside_it_after_the_throw_then_is_put_away() -> None:
    e, t = thrown_with("sip_tea")
    seen: list[tuple[float, tuple | None]] = []
    stood = None
    for _ in range(1500):
        t += 0.016
        out = e.update(t)
        if e.state in ("stand", "sit") and stood is None:
            stood = t
        if out.prop is not None and out.prop[2] >= props.TIPPED:
            seen.append((t, out.prop))
        if stood is not None and t - stood > extras.TIP_S + extras.TIP_OUT_S + 1.0:
            break
    assert stood is not None and seen, "it never stood again, or the cup never lay beside it"
    assert {p[1][0] for p in seen} == {"cup"}
    first, last = seen[0][0], seen[-1][0]
    assert first - stood < 0.1 and abs((last - first) - (extras.TIP_S + extras.TIP_OUT_S)) < 0.1, (first - stood, last - first)
    assert e.ex.view(t)[0] is None or e.ex.view(t)[0][2] < props.TIPPED  # and it is put away at the end


def test_a_blanket_is_not_in_its_hands_so_nothing_is_dropped() -> None:
    e, t = thrown_with("blanket_nap")
    for _ in range(1500):
        t += 0.016
        out = e.update(t)
        assert out.prop is None or out.prop[2] < props.TIPPED


def test_a_prop_it_already_put_away_is_not_dropped() -> None:
    e, t = thrown_with("sip_tea", ended=True)
    for _ in range(1500):
        t += 0.016
        out = e.update(t)
        assert out.prop is None or out.prop[2] < props.TIPPED
