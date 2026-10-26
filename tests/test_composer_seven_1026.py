"""composer7: leftovers from composer5/6 and dog2, asked with no model."""

from __future__ import annotations

import pytest

from tests.test_composer_five_1025 import ask  # noqa: F401


def test_definition_does_not_volunteer_tasks(ask):  # noqa: F811
    said = ask("what is the Krebs cycle")
    assert "revise the krebs cycle diagram" not in said.lower(), said
    assert "read chapter 4" not in said.lower(), said


@pytest.mark.parametrize("q", ["what's my next exam", "exam date", "when is my next exam"])
def test_next_exam_uses_reminder(ask, q):  # noqa: F811
    said = ask(q)
    assert "12 Nov" in said or "November" in said or "Nov 12" in said, said
    assert "09:00" in said, said
