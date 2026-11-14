"""L218: a run of small-talk turns is not one reply said again. Measured over ten hellos and ten
thanks in one chat (each reply sees the last three as `recent`): the replies are distinct, and
no reply opens as the one before it did."""

import pytest

from tessellate.ai import composer_smalltalk


def _run(message, n=10):
    out: list[str] = []
    for _ in range(n):
        out.append(composer_smalltalk.social(message, "smalltalk", recent=out[-3:], seed="chat-a"))
    return out


@pytest.mark.parametrize("message", ["hello", "thanks"])
def test_a_run_of_small_talk_is_varied(message):
    replies = _run(message)
    assert len(set(replies)) >= 8, replies
    assert all(a.split()[:2] != b.split()[:2] for a, b in zip(replies, replies[1:])), replies
