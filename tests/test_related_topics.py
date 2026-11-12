"""The related-topic table (`memorymap_related.json`, Q29, owner 2026-11-11):
a hit on Gardening counts half toward Home, Mental Health toward Health,
Physics toward Education. Every name in it must be a real topic."""

from __future__ import annotations

import json

from tessellate.ai import taxonomy


def _table() -> dict:
    return json.loads((taxonomy.DATA_DIR / "memorymap_related.json").read_text(encoding="utf-8"))


def test_every_source_and_target_is_a_real_topic() -> None:
    topics = set(taxonomy.taxonomy_map())
    table = _table()["related"]
    assert table
    assert {src for src in table} <= topics
    assert {tgt for targets in table.values() for tgt in targets} <= topics


def test_no_topic_is_related_to_itself_or_listed_twice() -> None:
    for src, targets in _table()["related"].items():
        assert src not in targets, src
        assert len(targets) == len(set(targets)), src


def test_a_hit_counts_half_toward_the_related_topic() -> None:
    assert _table()["factor"] == 0.5
    weights = taxonomy.topic_weights("Mow the lawn and prune the roses")
    assert weights["Gardening"] > 0
    assert weights["Home"] >= weights["Gardening"] * 0.5
    assert taxonomy.topic_weights("Therapy session: anxiety and counselling")["Health"] > 0


def test_a_topic_the_text_named_itself_is_never_lowered() -> None:
    text = "Fix the leaking tap and plant the roses"
    plain = taxonomy.topic_hits(text)
    own = taxonomy.topic_weights(text, plain)
    assert own.get("Home", 0.0) >= max(own.get("Gardening", 0.0), own.get("DIY & Home Repair", 0.0)) * 0.5
