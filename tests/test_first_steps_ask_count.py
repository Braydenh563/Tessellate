"""Get started's third step reads the Ask history's count again when the badge's
cached count is 0: that 0 may predate the answer's record (E2E first-run failed
on CI 2026-11-03 with the step unticked after an answer)."""

from pathlib import Path

FIRST_RUN = Path(__file__).resolve().parents[1] / "frontend" / "js" / "first-run.js"


def test_a_cached_zero_is_read_again() -> None:
    body = FIRST_RUN.read_text(encoding="utf-8").split("async function firstStepsRead()", 1)[1].split("\n}\n", 1)[0]
    assert 'askBadgeTotal ? { total: askBadgeTotal } : apiJson("/ask-history/stats")' in body
    assert "askBadgeTotal === null ?" not in body, "a 0 the badge read before the answer was kept is trusted"
