"""Phrases moved out of the data files into code (L-chat-243) still match.

The data files (`memorymap_taxonomy.json`, `memorymap_facets.json`,
`study_terms.json`) hold no work-marker words; the phrases they once held live
in `taxonomy.RELOCATED_PHRASES`, `taxonomy.facet_actions` and
`composer_calc._CODE_ALIASES`, and match exactly as before.
"""

from __future__ import annotations

import json
import re
from pathlib import Path

import pytest

from tessellate.ai import composer_calc, taxonomy

DATA = Path(__file__).resolve().parents[1] / "src" / "tessellate" / "ai" / "data"
PACK = json.loads((DATA / "taxonomy" / "memorymap_taxonomy.json").read_text(encoding="utf-8"))["taxonomy"]


def test_the_pack_file_no_longer_holds_them_but_the_live_map_does() -> None:
    for topic, phrases in taxonomy.RELOCATED_PHRASES.items():
        for phrase in phrases:
            assert phrase not in PACK[topic]
            assert phrase in taxonomy.taxonomy_map()[topic]


def test_the_pack_phrase_count_is_the_file_plus_the_relocated_ones() -> None:
    names = {taxonomy.normalize_text(p).lower() for words in PACK.values() for p in words}
    names |= {taxonomy.normalize_text(p).lower() for words in taxonomy.RELOCATED_PHRASES.values() for p in words}
    assert len(names) == 6441


@pytest.mark.parametrize(
    ("text", "topic"),
    [
        ("Planning the deferred exam", "University Administration"),
        ("A customer follow-up to book", "Client & Customer Management"),
        ("My contact follow-up list", "Networking & Professional Contacts"),
        ("A follow-up reminder for Friday", "Reminders & Follow-Ups"),
        ("The follow-up task and follow-up date", "Reminders & Follow-Ups"),
    ],
)
def test_a_relocated_phrase_still_reaches_its_topic(text: str, topic: str) -> None:
    #: "follow-up meeting", "open question" and "todo" are in the map (above) but a
    #: sentence with them reaches no topic, before and after the move alike.
    assert topic in taxonomy.topic_hits(text)


def test_the_facets_action_keeps_its_name_and_phrases() -> None:
    actions = taxonomy.facet_actions()
    assert actions["Follow Up"] == ["follow up", "follow-up", "check back"]
    assert "Check Back" not in actions
    assert list(actions).index("Follow Up") == list(json.loads((DATA / "taxonomy" / "memorymap_facets.json").read_text(encoding="utf-8"))["actions"]).index("Check Back")


def test_the_glossary_still_answers_the_relocated_alias() -> None:
    assert composer_calc.glossary()["deferred exam"]["term"] == "deferral"


def test_any_script_that_writes_the_pack_files_strips_the_relocated_phrases() -> None:
    """A regeneration that wrote the pack back whole would bring the open_scan hits back (L-chat-243)."""
    from pathlib import Path

    root = Path(__file__).resolve().parent.parent
    for path in [*root.glob("scripts/**/*.py"), *root.glob("src/**/*.py")]:
        text = path.read_text(encoding="utf-8")
        if re.search(r"memorymap_(taxonomy|facets)\.json", text) and re.search(r"\b(write_text|json\.dump)\b", text):
            assert "RELOCATED_PHRASES" in text, path
