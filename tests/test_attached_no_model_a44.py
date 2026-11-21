"""L64 (A44): with no model, a Chat question that points at the attached note ("what happened here?")
is answered from that note alone, in Chat and in Ask, never from the newest notes."""

from __future__ import annotations

import pytest

from tests.test_composer_attached_1461 import _seed
from tests.test_composer_route_688 import _ask


@pytest.mark.parametrize("use_tools", [True, False])
@pytest.mark.parametrize(
    "question",
    ["what happened here?", "what happened in this note", "what's going on here", "what is happening in this note?"],
)
def test_a_pointing_question_reads_the_attached_note_alone(client, session, question, use_tools):
    bus = _seed(session)
    text = _ask(client, question, use_tools=use_tools, note_ids=[bus])["text"]
    assert "bus" in text.lower(), text
    assert "Current Commitments" not in text and "Girl with bell" not in text, text
    assert "newest notes" not in text, text


def test_a_one_line_cjk_note_is_read_as_content_and_counted_in_characters_l25(client, session):
    """L25 (C10): a Japanese or Chinese one-liner answers from its words; its length is characters, not three 'words'."""
    from tessellate.entry import manager

    ja = manager.create_entry(session, "今日はバスに乗り遅れたけど、友達に会ってコーヒーを飲んだ。いい朝になった。")
    zh = manager.create_entry(session, "会议在下午三点，带上预算表。")
    session.commit()
    said = _ask(client, "what is this note about?", use_tools=False, note_ids=[ja.id])["text"]
    assert "コーヒー" in said and "Current" not in said
    assert "友" in _ask(client, "summarise this", use_tools=False, note_ids=[ja.id])["text"]
    long_ja = _ask(client, "how long is this", use_tools=False, note_ids=[ja.id])["text"]
    assert "characters" in long_ja and "three words" not in long_ja, long_ja
    assert "twelve characters" in _ask(client, "how long is this", use_tools=False, note_ids=[zh.id])["text"]
    assert "会议在下午三点" in _ask(client, "what does it say?", use_tools=False, note_ids=[zh.id])["text"]
