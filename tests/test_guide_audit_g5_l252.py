"""L252 (audit G5): a Guide lead stands alone, so it never leans on "there" or "it" for a place the line does not name."""

from __future__ import annotations

import re

import pytest

from tessellate.ai import composer, help_chat

_DANGLING = re.compile(r"^(?:Press|Open|Click|Use)\b[^.]*\b(?:there|it)\b", re.I)


@pytest.mark.parametrize("question", ["how do I record a meeting"])
def test_the_record_a_meeting_lead_names_the_recorder(question):
    line, topic = composer.help_line(question, help_chat.topics_for(question, "dashboard"))
    assert topic == "meetings"
    assert "recorder" in line.lower()
    assert not re.search(r"\bthere\b", line), line


def test_the_miss_line_never_blames_a_missing_model():
    from tessellate.ai import guide_lead

    assert "model" not in guide_lead.MISS.lower()
