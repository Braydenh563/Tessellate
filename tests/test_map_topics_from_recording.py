"""Source text: the paste runs in the browser's map code with no Python seam, so its single transaction is read as text. Voice to map (MINDMAP_PLAN 12.4, reopened 2026-11-14: only a session line
kept it out of scope). A recording's local transcript becomes a branch, one
topic per transcript line, under the selected topic, through the same outline
paste a pasted list takes (one transaction, one Undo step)."""

from __future__ import annotations

import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
MORE = (ROOT / "frontend" / "js" / "whiteboard-map-more.js").read_text(encoding="utf-8")
MAP = (ROOT / "frontend" / "js" / "whiteboard-map.js").read_text(encoding="utf-8")


def _body(text: str, name: str) -> str:
    match = re.search(rf"^  async function {name}\(.*?^  }}$", text, re.S | re.M)
    assert match, name
    return match.group(0)


def test_the_transcript_is_read_and_pasted_as_one_topic_per_line():
    body = _body(MORE, "wbMapTopicsFromRecording")
    assert "/recordings/${id}/transcript" in body
    assert "wbRecordGesture(wbMapPasteText" in body
    # One picker for both the audio note and this, not a second copy.
    assert "wbAudioChoose(" in body and "wbAudioChoose(" in _body(MORE, "wbAudioPick")
    # A recording with no transcript says what to do, rather than nothing.
    assert "no transcript yet" in body


def test_the_map_offers_it_by_name_on_a_topic_and_through_the_lazy_surface():
    assert "topicsFromRecording: wbMapTopicsFromRecording" in MORE
    assert "wbMapLazy.topicsFromRecording(node)" in MAP


def test_the_guide_says_where_it_is():
    # In the import topic: the features topic sits near the reply budget.
    help_text = (ROOT / "src" / "tessellate" / "ai" / "help_topics_core_tail.py").read_text(encoding="utf-8")
    assert "Topics from a recording for one topic per transcript line" in help_text


def test_the_plan_no_longer_calls_voice_to_map_out_of_scope():
    plan = (ROOT / "docs" / "roadmap" / "MINDMAP_PLAN.md").read_text(encoding="utf-8")
    scope = plan.split("### 12.4", 1)[1].split("\n### ", 1)[0]
    assert "voice-to-map and" not in scope and "topics from a recording" in scope.lower()
