"""L68: the app starts no managed runner, so no message may say one was killed."""

from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def test_no_user_facing_text_mentions_a_managed_runner():
    hits = []
    for base, pattern in ((ROOT / "src", "*.py"), (ROOT / "frontend", "*.js"), (ROOT / "frontend", "*.html")):
        for path in base.rglob(pattern):
            text = path.read_text(encoding="utf-8", errors="ignore").lower()
            if "managed runner" in text or "runner killed" in text or "runner was killed" in text:
                hits.append(str(path.relative_to(ROOT)))
    assert hits == []
