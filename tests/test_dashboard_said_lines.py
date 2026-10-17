"""The dashboard's composed lines read as sentences, and what they name opens
(INBOX 904 B83, B84; O9). Measured in Chromium on 2026-10-17
(scratchpad sweeps digest_lines.js, pattern_link.js): the day digest's count
line had cursor pointer and the row's hover wash, now cursor default and no
wash, a click goes nowhere; the pattern reads "Pattern: golf came up 4 times
since 5 September" and its words open the Notes tab filtered to "golf"."""

from __future__ import annotations

from pathlib import Path

from tessellate.ai import help_chat, insights, reading

ROOT = Path(__file__).resolve().parents[1]
READER = reading.__name__


def test_a_digest_sentence_is_not_a_control_and_its_quotes_still_open():
    source = (ROOT / "frontend" / "js" / "dash-day.js").read_text(encoding="utf-8")
    said = source[source.index("function digestSaidLine"):]
    assert 'role", "link"' not in said and "addEventListener(\"click\", open)" not in said
    assert 'if (line.kind !== "quote")' in source
    css = (ROOT / "frontend" / "css" / "dash-orphans-lazy.css").read_text(encoding="utf-8")
    assert ".dash-list li.digest-day-said {\n  cursor: default;" in css


def test_a_pattern_is_said_as_a_sentence_and_links_its_notes():
    found = insights.Insight(rule="recurrence", text="", note_ids=[1], slots={"subject": "university", "count": 4, "since": "16 July"})
    assert insights.short(found) == "university came up 4 times since 16 July"
    weekly = insights.Insight(rule="streak", text="", note_ids=[1], slots={"subject": "golf", "weeks": 3})
    assert insights.short(weekly) == "golf every week for 3 weeks"
    source = (ROOT / "frontend" / "js" / "dashboard.js").read_text(encoding="utf-8")
    assert 'bits.push(["patterns", "Pattern: ", pattern.text])' in source
    assert 'if (kind === "patterns") dashPatternBit(bit, pattern);' in source
    lazy = (ROOT / "frontend" / "js" / "dash-day.js").read_text(encoding="utf-8")
    assert "showNotesFilter(subject)" in lazy[lazy.index("function dashPatternBit"):]
    assert '"dashPatternBit"]' in (ROOT / "frontend" / "js" / "lazy-entries.js").read_text(encoding="utf-8")


def test_the_guide_says_what_patterns_are_whether_they_change_and_how_to_see_them():
    from tessellate.ai import composer

    for question, said in (
        ("what are patterns", "counted from the notes themselves with no AI"),
        ("do the patterns ever change", "They change as you write"),
        ("can I view the patterns", "to see the notes behind it"),
    ):
        topics = help_chat.topics_for(question)
        assert topics[0]["id"] == "patterns", (question, [t["id"] for t in topics])
        assert said in composer.help_line(question, topics)[0], question
