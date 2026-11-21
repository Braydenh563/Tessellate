"""A word the English list holds is never read as two run together (LEDGER L-world-class-135, VC8).

`repair("How a map's topics look")` read "topics" as "to pictures", so the Guide's own topic
title reached the wrong topic. Run over the 91,185 words of the list (four letters or more),
`repair` changed 88 before; the 12 below were run-on or asking-word splits of real words, the
rest are slang spelled out ("asap", "info") or US spellings read as UK, which are meant.
"""

from __future__ import annotations

import pytest

from tessellate.ai import question_noise

REAL = ["topics", "anther", "aspics", "cancan", "candid", "canon", "canto", "liston", "longtime", "wherein", "whereof", "whereon", "whereto", "wherewith", "willis"]


@pytest.mark.parametrize("word", REAL)
def test_a_real_word_is_not_split_in_two(word):
    assert question_noise.repair(word) == word


def test_a_run_together_pair_is_still_split():
    assert question_noise.repair("whenis the meeting") == "when is the meeting"
    assert question_noise.repair("howmany notes") == "how many notes"
