"""Lying asleep, the companion's Zs rise from its head, not from where a standing
head would be (the owner, 2026-10-19). Measured once in Chromium, each pose and variant, first z against the eyes
(before: 85px above the eyes lying, 64px half down; after: about 40px in every pose)."""

from pathlib import Path

CSS = (Path(__file__).resolve().parents[1] / "frontend" / "css" / "08-consistency.css").read_text(encoding="utf-8")


def test_each_lying_pose_moves_the_zs_down_to_the_head() -> None:
    for pose in ("lie", "lie-2", "lie-1"):
        assert f'#nm-buddy[data-pose="{pose}"] .nm-buddy-z {{ translate:' in CSS, pose


def test_the_mirrored_variant_moves_them_the_other_way() -> None:
    for pose in ("lie-2", "lie-1"):
        assert f'#nm-buddy[data-pose="{pose}"][data-atlas-variant="1"] .nm-buddy-z {{ translate: 22px' in CSS
