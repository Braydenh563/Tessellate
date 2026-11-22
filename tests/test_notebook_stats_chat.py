"""Chat's statistics answers (UI_MODERNISATION statistics row 5, Brief 89):
counted, so quick and said as counted, with no grounding heads-up under them."""

from __future__ import annotations

import time


def _streamed(client, question):
    import json as _json

    lines = client.post("/chat/stream", json={"question": question}).text.splitlines()
    return "".join(_json.loads(line).get("delta", "") for line in lines if line.strip() and '"answer"' in line)


def test_a_counted_chat_answer_carries_no_heads_up(client):
    """The grounding check read "You have 3 notes" as a model's claim and said
    it could not find 3 in the notes; a count is not in any note (Brief 89)."""
    for text in ("one", "two", "three"):
        client.post("/entries", json={"content": f"note {text}", "tags": ["work"]})
    for question in ("how many notes do I have", "what are my top tags", "show me my stats"):
        answer = _streamed(client, question)
        assert answer and "Heads up" not in answer, (question, answer)


def test_a_counted_answer_is_counted_quickly_on_a_bigger_notebook(client):
    """Row 5's budget: the stats are counts, so a 400-note notebook still
    answers well under 300 ms server-side (measured about 15 ms on 96 notes
    over HTTP; the 829 to 1,416 ms in the plan was the probe's 150 ms poll
    on a loaded machine plus the first reply it could not see)."""
    from tessellate.ai import notebook_stats
    from tessellate.core import deps
    from tessellate.core.database import Entry

    with deps.get_db().session() as session:
        session.add_all(Entry(content=f"note {i} about the harbor survey and the budget", tags='["work", "t%d"]' % (i % 9)) for i in range(400))
        session.commit()
        for question in ("how many notes do I have", "what are my top tags", "how many words have I written", "which notes are orphans"):
            started = time.process_time()
            assert notebook_stats.answer(question, session) is not None, question
            assert time.process_time() - started < 0.3, question
