"""Batch BA1 (OPEN.md agent rows): K33 the token sweep is not run per request; K38 a media link is single use."""

from __future__ import annotations

import time

import pytest

from tessellate.api import routes_auth as auth


@pytest.fixture(autouse=True)
def _clean():
    auth._active_tokens.clear()
    auth._media_links.clear()
    auth._sweep_state["last"] = 0.0
    yield
    auth._active_tokens.clear()
    auth._media_links.clear()


def test_k33_a_live_token_is_checked_without_sweeping_every_request(monkeypatch):
    token = auth._issue_token()
    calls = []
    real = auth._sweep_expired
    monkeypatch.setattr(auth, "_sweep_expired", lambda ttl: (calls.append(ttl), real(ttl)))
    for _ in range(50):
        assert auth._token_valid(token, 3600)
    assert len(calls) <= 1


def test_k33_an_idle_token_is_still_refused_at_once(monkeypatch):
    token = auth._issue_token()
    auth._token_valid(token, 3600)  # the throttled sweep has run
    auth._active_tokens[token][1] = time.time() - 7200
    assert not auth._token_valid(token, 3600)
    assert token not in auth._active_tokens


def test_k38_access_log_never_prints_a_media_link_ticket():
    import logging

    record = logging.LogRecord(
        "uvicorn.access", logging.INFO, __file__, 1, '%s - "%s %s HTTP/%s" %d',
        ("127.0.0.1:1", "GET", "/media/a.pdf?once=abcDEF_123-xyz&x=1", "1.1", 200), None,
    )
    assert auth._HideTickets().filter(record)
    assert "abcDEF" not in record.getMessage()
    assert "/media/a.pdf?once=...&x=1" in record.getMessage()
    plain = logging.LogRecord("uvicorn.access", logging.INFO, __file__, 1, "%s", ("/notes?limit=5",), None)
    auth._HideTickets().filter(plain)
    assert plain.getMessage() == "/notes?limit=5"
    assert any(isinstance(f, auth._HideTickets) for f in logging.getLogger("uvicorn.access").filters)
