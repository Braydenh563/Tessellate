"""With the model down, one "Why?" batch costs one attempt and one log line, not one per pair.

Source text: the owner's Windows log, 2026-11-22 (Ollama not running): the suggestions sheet's
reasons fired six times back to back; the first waited out the 2.0 s connect timeout and the
other five failed in 1 ms each, each logged ("link suggestion reason skipped"). After the first
"not running" the batch is skipped, the next batches inside the back-off are not sent at all,
and it is said once.
"""

from __future__ import annotations

import logging

import pytest

from tessellate.ai import ollama_client
from tessellate.ai.ollama_client import OllamaError
from tessellate.api import routes_entries_relations as rel


@pytest.fixture(autouse=True)
def _fresh_backoff(monkeypatch):
    now = [1000.0]
    monkeypatch.setattr(ollama_client, "_clock", lambda: now[0])
    yield now


def _pairs(client, n):
    ids = [client.post("/entries", json={"content": f"note {i} about tickets"}).json()["id"] for i in range(n + 1)]
    return [{"source_id": ids[i], "target_id": ids[i + 1]} for i in range(n)]


def _counting(monkeypatch, exc):
    calls = []

    def fake(*a, **k):
        calls.append(1)
        raise exc

    monkeypatch.setattr(rel.librarian, "generate_link_reason", fake)
    return calls


def _skips(caplog):
    return [r for r in caplog.records if "link suggestion reason" in r.getMessage()]


def test_the_first_not_running_skips_the_rest_of_the_batch_and_logs_once(client, monkeypatch, caplog):
    caplog.set_level(logging.INFO, logger="tessellate.api.entries")
    calls = _counting(monkeypatch, OllamaError("Ollama is not running at http://localhost:11434"))
    result = client.post("/entries/link-suggestions/reasons", json={"pairs": _pairs(client, 6)}).json()
    assert result == {"reasons": [], "ai_unavailable": True}
    assert len(calls) == 1
    assert len(_skips(caplog)) == 1


def test_batches_inside_the_back_off_are_not_sent_and_not_logged_again(client, monkeypatch, caplog, _fresh_backoff):
    caplog.set_level(logging.INFO, logger="tessellate.api.entries")
    calls = _counting(monkeypatch, OllamaError("Ollama is not running at http://localhost:11434"))
    pairs = _pairs(client, 3)
    for _ in range(5):
        result = client.post("/entries/link-suggestions/reasons", json={"pairs": pairs}).json()
        assert result["ai_unavailable"] is True
        _fresh_backoff[0] += 1.0
    assert len(calls) == 1
    assert len(_skips(caplog)) == 1
    _fresh_backoff[0] += rel.REASONS_BACKOFF_SECONDS
    client.post("/entries/link-suggestions/reasons", json={"pairs": pairs})
    assert len(calls) == 2, "after the back-off the model is asked again"


def test_a_connect_timeout_counts_as_down(client, monkeypatch):
    calls = _counting(monkeypatch, TimeoutError("timed out"))
    client.post("/entries/link-suggestions/reasons", json={"pairs": _pairs(client, 4)})
    assert len(calls) == 1


def test_one_bad_pair_with_the_model_up_does_not_sink_the_rest(client, monkeypatch):
    calls = []

    def fake(a, b, *rest):
        calls.append(1)
        if len(calls) == 1:
            raise ValueError("an odd reply")
        return "both about tickets"

    monkeypatch.setattr(rel.librarian, "generate_link_reason", fake)
    result = client.post("/entries/link-suggestions/reasons", json={"pairs": _pairs(client, 3)}).json()
    assert len(calls) == 3 and len(result["reasons"]) == 2
    assert not ollama_client.held_off("link-suggestion-reasons")
