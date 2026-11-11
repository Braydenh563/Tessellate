"""The grouped, shape-aware overview (the framed path) as a test fixture.

INBOX 1743 wove an overview of 5 to 40 dated notes into paragraphs
(`composer_story`). The grouped lines, the shape sentence, link lines and
group order remain the answer for a notebook over `WOVEN_LIMIT` notes or one
with an undated note, and these tests assert them: a limit of zero puts the
question on that path, so they keep checking what they were written to check.
"""

from __future__ import annotations

import pytest

from tessellate.ai import composer_story


@pytest.fixture
def framed_path(monkeypatch):  # noqa: ANN001, ANN201
    monkeypatch.setattr(composer_story, "WOVEN_LIMIT", 0)
