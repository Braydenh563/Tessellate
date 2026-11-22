"""The model hands off to the composed answer on every failure (CHAT_PLAN Phase 10, `handoff_1010.json`, L-chat-22).

25 questions, each asked with its one note under the six failures of
`tests/test_chat_degrades.py` (150 turns, on the fake transport: CLAUDE.md
section 4). Each leaves the composed text, the line that says why (the model
stopped, or the notes back none of its answer), never an error-only bubble,
and `composition.fallback` true on the stats.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from tessellate.api.chat_said import MODEL_STOPPED_NOTE, MODEL_UNBACKED_NOTE
from tessellate.entry import manager
from tests.test_chat_degrades import FAILURES, _Failing, _final
from tests.test_composer_route_688 import _ask

ROWS = json.loads((Path(__file__).parent / "fixtures/composer/handoff_1010.json").read_text(encoding="utf-8"))["rows"]


def test_the_set_is_twenty_five_questions_under_six_failures():
    assert len(ROWS) == 25 and len(FAILURES) == 6
    assert len({r["question"] for r in ROWS}) == 25


@pytest.mark.parametrize("row", ROWS, ids=[r["title"] for r in ROWS])
def test_every_failure_leaves_the_composed_answer(ai_client, fake_ollama, session, monkeypatch, row):
    from tessellate.core import deps

    manager.create_entry(session, f"# {row['title']}\n\n{row['note']}")
    session.commit()
    for failure, stream in FAILURES.items():
        monkeypatch.setattr(deps, "get_ollama", lambda stream=stream: _Failing(fake_ollama, stream))
        out = _ask(ai_client, row["question"], notes_only=True, use_tools=False, answer_from="ai")
        final = _final(out)
        assert row["composed"] in final, (failure, final)
        assert (MODEL_UNBACKED_NOTE if failure == "unsupported" else MODEL_STOPPED_NOTE) in final, (failure, final)
        assert "Lisbon" not in final and "2019" not in final, (failure, final)
        assert final.strip() not in (MODEL_STOPPED_NOTE, MODEL_UNBACKED_NOTE), (failure, final)
        stats = out.get("stats") or [{}]
        assert stats[-1].get("composition", {}).get("fallback") is True, (failure, stats)
