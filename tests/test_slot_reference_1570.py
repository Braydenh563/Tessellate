"""INBOX 1570 (b): the act grammar reads "the X one" and "the one about X" as a note's title,
and leaves "the other one" and "the last one" to the answer they point back at."""

from __future__ import annotations

from datetime import datetime

import pytest

from tessellate.ai import acts

NOW = datetime(2026, 11, 3, 12)


@pytest.mark.parametrize("verb", ["pin", "unpin", "delete"])
@pytest.mark.parametrize("ref", ["the interesting bean one", "that interesting bean one", "the one about the interesting bean", "the one called interesting bean"])
def test_the_act_grammar_reads_the_x_one(verb, ref):
    parsed = acts.parse(f"{verb} {ref}", NOW)
    assert parsed and parsed["intent"] == verb and parsed["about"] == "interesting bean", parsed


@pytest.mark.parametrize("ref", ["the other one", "the second one", "the last one", "the new one", "that one"])
def test_a_pointer_back_at_an_answer_is_not_a_title(ref):
    assert acts.parse(f"delete {ref}", NOW) is None
