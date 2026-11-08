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
