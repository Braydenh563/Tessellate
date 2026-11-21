"""L51: a tab-level Guide topic rings its own control, not the tab's main control."""

from __future__ import annotations

import re
from pathlib import Path

from tessellate.ai import help_chat, help_targets
from tessellate.ai.help_topics_core import HELP_TOPICS

INDEX = (Path(__file__).resolve().parents[1] / "frontend" / "index.html").read_text(encoding="utf-8")
IDS = set(re.findall(r'id="([A-Za-z0-9_-]+)"', INDEX))


def _topic(topic_id: str) -> dict:
    return next(t for t in HELP_TOPICS if t["id"] == topic_id)


def test_every_named_control_is_in_the_page():
    for topic_id, target in help_targets.TARGETS.items():
        assert any(t["id"] == topic_id for t in HELP_TOPICS), topic_id
        for element in target.split():
            assert element in IDS, (topic_id, element)


def test_a_mapped_topic_badge_carries_its_own_target():
    assert _topic("tidy")["badge"] == {"label": "Notes", "tab": "notes", "target": "notes-tidy"}
    assert _topic("voice")["badge"]["target"] == "mic-note"
    #: The drive (L54) measured these off screen in the tab's normal state (in a
    #: menu, or shown only on a failure), so they keep the tab landing.
    for hidden in ("chat-private", "tag-manager", "archive", "note-outbox"):
        assert "target" not in _topic(hidden)["badge"], hidden


def test_a_topic_with_no_control_of_its_own_keeps_the_tab_landing():
    assert "target" not in _topic("board-laser")["badge"]


def test_the_open_button_an_answer_carries_is_the_topics_own_control():
    topics = help_chat.topics_for("where is the tidy button for my notes")
    assert any(b.get("target") == "notes-tidy" for b in help_chat.badges_for(topics)), help_chat.badges_for(topics)


def test_tidy_my_notes_is_the_notes_tidy_topic_not_the_map_layout_l54():
    """The 2026-11-12 drive: the bare keyword "tidy" put the mind-map layout first."""
    from tessellate.ai import help_chat

    for question in ("how do I tidy my notes", "tidy my notes"):
        assert help_chat.topics_for(question)[0]["id"] == "tidy", question
    assert help_chat.topics_for("tidy the map")[0]["id"] == "mind-map-features"
