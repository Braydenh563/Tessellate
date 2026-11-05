"""INBOX 1690 b: a captured look (the owner's own figure, key `c-...`) has no charted
eye box; the face layer drew from `LID_EYES[look]` and raised KeyError, which killed
the overlay and left the card-window fallback flickering."""

from __future__ import annotations

from types import SimpleNamespace

from tessellate.core.overlay import faces
from tessellate.core.overlay import sprites as sp


def test_a_captured_look_has_no_eye_anchor_and_draws_the_bare_frame() -> None:
    spr = SimpleNamespace(look="c-548bdf873742")
    assert spr.look not in sp.LID_EYES
    for name in faces.FACE_FRAMES:
        assert faces.eye_anchor(spr, name) is None
    base = object()
    kind = next(iter(faces.EXPRESSIONS))
    assert faces.draw(spr, "stand", base, False, None, (kind, 1)) is base
