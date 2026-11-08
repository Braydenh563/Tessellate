"""INBOX 1690 b: a captured look (the owner's own figure, key `c-...`) has no charted
eye box; the face layer drew from `LID_EYES[look]` and raised KeyError, which killed
the overlay and left the card-window fallback flickering."""

from __future__ import annotations

from types import SimpleNamespace

import pytest

from tessellate.core.overlay import faces
from tessellate.core.overlay import sprites as sp
from tessellate.core.overlay.sprites import SpriteSet


def test_a_captured_look_has_no_eye_anchor_and_draws_the_bare_frame() -> None:
    spr = SimpleNamespace(look="c-548bdf873742")
    assert spr.look not in sp.LID_EYES
    for name in faces.FACE_FRAMES:
        assert faces.eye_anchor(spr, name) is None
    base = object()
    kind = next(iter(faces.EXPRESSIONS))
    assert faces.draw(spr, "stand", base, False, None, (kind, 1)) is base


# --- companion catalogue B4: confused, sad, shy, love, laughing -------------------------------------------------

FIVE = ("confused", "sad", "shy", "love", "laughing")


@pytest.mark.parametrize("look", ["masculine", "feminine"])
def test_the_five_new_faces_are_drawn_each_unlike_the_others_and_the_old_ones(look: str) -> None:
    s = SpriteSet(look)
    base = s.frame("stand", 96, False)
    assert set(FIVE) <= set(faces.EXPRESSIONS)
    drawn = {k: faces.draw(s, "stand", base, False, None, (k, 3), base).bgra for k in faces.EXPRESSIONS}
    assert all(b != base.bgra for b in drawn.values())
    assert len(set(drawn.values())) == len(drawn), "two expressions draw the same face"


@pytest.mark.parametrize("kind", FIVE)
def test_a_new_face_eases_in_and_out_like_the_others(kind: str) -> None:
    s = SpriteSet("masculine")
    base = s.frame("stand", 96, False)
    by_level = [faces.draw(s, "stand", base, False, None, (kind, lv), base).bgra for lv in (1, 2, 3)]
    assert len(set(by_level)) == 3 and base.bgra not in by_level
    assert faces.draw(s, "stand", base, False, None, (kind, 0), base) is base


# --- the faces are worn by a reaction (deskfix 4) ---------------------------------------------------------------


def _face_of(e, t: float) -> str | None:
    out = e.update(t)
    return out.face[0] if out.face else None


def _pet(e, kind: str, t: float) -> float:
    """One pat or rub on the figure, then the pointer far away so the next one starts fresh."""
    from tests.test_overlay_parity_1683 import box, feed

    lx, top, r, b = box(e)
    cx, cy = (lx + r) // 2, (top + b) // 2
    if kind == "pat":
        path = [(cx, top + 8), (cx, top + 26), (cx, top + 8), (cx, top + 26), (cx, top + 8), (cx, top + 26)]
    else:
        path = [(cx - 25, cy), (cx + 25, cy), (cx - 25, cy), (cx + 25, cy), (cx - 25, cy), (cx + 25, cy), (cx - 25, cy)]
    t = feed(e, t, path, 0.05)
    return feed(e, t, [(cx + 3000, cy)], 0.05)


def test_confused_is_worn_when_poked_while_the_person_is_working() -> None:
    from tests.test_overlay_parity_1683 import box, feed, still

    e, _s, t = still()
    e.quiet = True  # typing
    lx, top, r, b = box(e)
    cx, cy = (lx + r) // 2, top + int(0.72 * (b - top))
    feed(e, t, [(cx + 400, cy), (cx + 330, cy), (cx + 200, cy), (cx + 60, cy), (cx + 2, cy), (cx + 120, cy), (cx + 300, cy)], 0.04)
    assert e.ex.over and e.ex.over[0] == "confused"


def test_sad_is_worn_when_a_request_is_refused() -> None:
    from tests.test_overlay_parity_1683 import still

    e, _s, t = still()
    assert e.command("perch", t + 0.1) is False  # no window to sit on
    assert e.ex.over and e.ex.over[0] == "sad"
    assert _face_of(e, t + 0.2) == "sad"


def test_shy_is_worn_when_petted_right_after_waking() -> None:
    from tests.test_overlay_parity_1683 import still

    e, _s, t = still()
    e.command("nap", t)
    t += 0.5
    e.update(t)
    assert e.state == "sleep"
    e.command("wake", t)
    t += 0.3
    e.update(t)
    _pet(e, "pat", t)
    assert e.ex.over and e.ex.over[0] == "shy"


def test_a_pet_long_after_waking_is_not_shy() -> None:
    from tests.test_overlay_parity_1683 import still

    e, _s, t = still()
    _pet(e, "pat", t)
    assert e.ex.over and e.ex.over[0] == "joy"


def test_love_is_worn_on_the_third_pet_in_a_short_while() -> None:
    from tests.test_overlay_parity_1683 import still

    e, _s, t = still()
    faces_worn = []
    for kind in ("pat", "rub", "pat"):
        t = _pet(e, kind, t)
        faces_worn.append(e.ex.over[0] if e.ex.over else None)
        t += 7.0  # past the cooldowns, inside the pet streak
        e.update(t)
    assert faces_worn[:2] == ["joy", "content"] and faces_worn[2] == "love", faces_worn
