"""The desk companion's wave moves its arm (INBOX 1696, the owner 2026-11-08: "the desktop
companion's wave animation doesnt have the arm move so it looks liek a nazi salute").

The wave was one frame (`wave`, the arm held straight up at 120 degrees) for the whole
1.4 s of the state. A look that ships the wave cycle (`wave0` to `wave5`, the arm swung
side to side about the raised position) draws it at `WAVE_FPS`; a set without it keeps
the one frame.
"""

from __future__ import annotations

import random
from pathlib import Path

from tessellate.core.overlay import engine as eng
from tessellate.core.overlay import sprites
from tessellate.core.overlay.engine import Engine, Monitor

ROOT = Path(__file__).resolve().parents[1]
ONE = [Monitor((0, 0, 1920, 1040), 96)]


def _waving(wave_frames: int) -> list[str]:
    e = Engine((100, 120), ONE, rng=random.Random(3), idle_frames=0, wave_frames=wave_frames, home=(800, 920))
    t = 0.0
    for _ in range(60):
        t += 0.033
        e.update(t)
    e.command("wave", t)
    names = []
    for _ in range(int(eng.WAVE_FOR / 0.033) - 2):
        t += 0.033
        names.append(e.update(t).frame)
    return names


def test_a_wave_swings_through_its_cycle_when_the_look_has_one():
    names = _waving(sprites.WAVE_COUNT)
    waved = [n for n in names if n.startswith("wave")]
    assert len(waved) >= len(names) - 3, names
    assert "wave" not in waved, "the still frame is not drawn when the cycle is shipped"
    shown = set(waved)
    assert shown >= {f"wave{i}" for i in range(sprites.WAVE_COUNT)}, shown
    # Back and forth, not one sweep and a hold: the picture changes at least eight times in the wave.
    changes = sum(1 for a, b in zip(waved, waved[1:]) if a != b)
    assert changes >= 8, changes


def test_a_set_without_the_cycle_keeps_its_one_wave_frame():
    names = _waving(0)
    assert "wave" in names and not any(n.startswith("wave") and n != "wave" for n in names)


def test_the_cycle_is_optional_in_a_shipped_set_and_counted():
    assert set(sprites.WAVE_FRAMES) <= set(sprites.FRAME_NAMES)
    assert len(sprites.WAVE_FRAMES) == sprites.WAVE_COUNT


def test_both_shipped_atlas_looks_carry_the_wave_cycle():
    for look in ("feminine", "masculine"):
        assert sprites.SpriteSet(look, ROOT / "frontend" / "img" / "desk").wave_count() == sprites.WAVE_COUNT, look


def test_the_runner_tells_the_engine_how_many_wave_frames_the_look_has():
    src = (ROOT / "src" / "tessellate" / "core" / "overlay" / "runner.py").read_text(encoding="utf-8")
    assert "wave_frames=spr.wave_count()" in src


def test_the_render_swings_the_arm_in_every_wave_frame():
    js = (ROOT / "scripts" / "render_desk_frames.js").read_text(encoding="utf-8")
    assert "wave:" in js and "--desk-wave" in js
    css = "\n".join(p.read_text(encoding="utf-8") for p in (ROOT / "frontend" / "css").glob("*.css"))
    assert "var(--desk-wave" in css
