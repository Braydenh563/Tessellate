"""L193: "tonight around 7pm" reads as 19:00 by rule, and the reminder edit
row's fields share the buttons' height, the touch floor included (measured
2026-11-13 at 390px: due field 32px beside 44px buttons before, 44 after)."""

from __future__ import annotations

from datetime import datetime
from pathlib import Path

import pytest

from tessellate.ai import reminder_parser

JS = (Path(__file__).resolve().parents[1] / "frontend" / "js" / "reminder-edit.js").read_text(encoding="utf-8")


@pytest.mark.parametrize("said", ["call mum tonight around 7pm", "call mum tonight at about 7", "buy milk around 7pm tonight"])
def test_tonight_around_seven_is_seven_tonight(said):
    found = reminder_parser.read_by_rule(said, datetime(2026, 11, 13, 10, 0))
    assert found and found["due_at"] == datetime(2026, 11, 13, 19, 0), found


def test_the_fields_take_the_touch_floor_the_buttons_take():
    assert 'field.style.height = "max(var(--control-h), var(--target-min))";' in JS
