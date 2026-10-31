"""`POST /logs/client` is open to anyone who can reach the server, so in LAN
mode one device could flood the 500-line log and push real warnings (failed
unlocks, blocked devices) out of Settings, Logs (audit 1028 K10). Each client
gets a budget per minute; past it the line is dropped, still answered 204 so
a crashing page does not retry."""

from __future__ import annotations

import logging

from tessellate.api import routes_settings


def _post(client, n):
    for i in range(n):
        response = client.post("/logs/client", json={"kind": "error", "message": f"boom {i}"})
        assert response.status_code == 204


def test_a_flood_is_cut_at_the_budget(client, caplog, monkeypatch):
    monkeypatch.setattr(routes_settings, "_client_log_clock", lambda: 1000.0)
    routes_settings._client_log_times.clear()
    with caplog.at_level(logging.ERROR, logger="tessellate.browser"):
        _post(client, routes_settings.CLIENT_LOG_PER_MINUTE + 25)
    lines = [r for r in caplog.records if r.name == "tessellate.browser"]
    assert len(lines) == routes_settings.CLIENT_LOG_PER_MINUTE


def test_the_budget_comes_back_after_a_minute(client, caplog, monkeypatch):
    now = [1000.0]
    monkeypatch.setattr(routes_settings, "_client_log_clock", lambda: now[0])
    routes_settings._client_log_times.clear()
    _post(client, routes_settings.CLIENT_LOG_PER_MINUTE + 1)
    now[0] += 61
    with caplog.at_level(logging.ERROR, logger="tessellate.browser"):
        _post(client, 1)
    assert [r for r in caplog.records if r.name == "tessellate.browser"]
