"""The Settings head's 56px face is cut up while the page is idle, so the
first Settings open does not force its window's layout to measure it (25-33ms
in the perf probe, L-world-class-37; 0 forced reads over 5ms after)."""

import re
from pathlib import Path

AVATARS = (Path(__file__).resolve().parents[1] / "frontend/js/avatars.js").read_text(encoding="utf-8")


def test_the_own_face_is_warmed_at_the_settings_head_size_on_idle():
    body = AVATARS.split("function nameMarkWarmOwn()", 1)[1].split("\n  }\n", 1)[0]
    assert "nameMarkGenerated(seed, 56)" in body
    assert re.search(r"requestIdleCallback\(nameMarkWarmOwn, \{ timeout: \d+ \}\)", AVATARS)


def test_the_warm_fills_the_same_cache_key_nameMark_reads():
    # One builder for both, so a warmed face is the one Settings asks for.
    nm = AVATARS.split("function nameMark(seed, size = 20) {", 1)[1].split("\n  }\n", 1)[0]
    assert "nameMarkGenerated(seed, size)" in nm
    assert 'data-user-mark="56"' in (Path(__file__).resolve().parents[1] / "frontend/index.html").read_text(encoding="utf-8")
