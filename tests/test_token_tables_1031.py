"""The session token tables take one lock (audit 1031 BK7).

Session tokens, media tickets, device and network tokens were plain dicts. Each
single dict operation is atomic under the GIL, but a sweep, a grant and a sign
out are several steps, and requests run in the threadpool: two grants for one
session each saw "no ticket yet" and left two, and a sweep that raced a
sign-out raised "changed size during iteration" (1028 K2, K23). The tables are
now one guarded type and the multi-step moves hold the lock."""

from __future__ import annotations

import sys
import threading
import time

import pytest

from tessellate.api import routes_auth as auth


@pytest.fixture(autouse=True)
def _clean_tables():
    for table in (auth._active_tokens, auth._media_tickets, auth._device_tokens):
        table.clear()
    auth._network_tokens.clear()
    old = sys.getswitchinterval()
    sys.setswitchinterval(1e-6)  # switch threads between steps, not just between calls
    yield
    sys.setswitchinterval(old)
    for table in (auth._active_tokens, auth._media_tickets, auth._device_tokens):
        table.clear()
    auth._network_tokens.clear()


class _Request:
    url = type("U", (), {"scheme": "http", "hostname": "127.0.0.1"})()
    headers: dict = {}


class _Response:
    def set_cookie(self, *a, **k):
        pass


def _run(workers: int, job) -> list[Exception]:
    errors: list[Exception] = []

    def body(n: int) -> None:
        try:
            job(n)
        except Exception as exc:  # noqa: BLE001  # the test reports whatever a thread raised
            errors.append(exc)

    threads = [threading.Thread(target=body, args=(n,)) for n in range(workers)]
    for t in threads:
        t.start()
    for t in threads:
        t.join(30)
    return errors


def test_the_tables_are_guarded_types_sharing_one_lock():
    tables = (auth._active_tokens, auth._media_tickets, auth._device_tokens, auth._network_tokens)
    assert all(isinstance(t, auth.GuardedTable) for t in tables)
    assert len({id(t.lock) for t in tables}) == 1
    assert auth._token_lock is tables[0].lock


def test_concurrent_grants_for_one_session_leave_one_ticket(monkeypatch):
    token = auth._issue_token()
    real = auth.secrets.token_urlsafe

    def slow(n):
        time.sleep(0.0005)  # the gap between "drop the old ticket" and "store the new one"
        return real(n)

    monkeypatch.setattr(auth.secrets, "token_urlsafe", slow)

    def grant(_):
        for _ in range(10):
            auth._grant_media(_Request(), _Response(), token)

    assert _run(12, grant) == []
    assert [owner for owner in auth._media_tickets.values()].count(token) == 1


def test_sweeping_while_others_unlock_and_sign_out_raises_nothing_and_orphans_nothing():
    def churn(n):
        for _ in range(80):
            token = auth._issue_token()
            auth._grant_media(_Request(), _Response(), token)
            if n % 3 == 0:
                auth._active_tokens.pop(token, None)
            auth._sweep_expired(0)  # every token is idle for longer than zero seconds

    assert _run(12, churn) == []
    time.sleep(0.01)
    auth._sweep_expired(0)
    assert not auth._active_tokens
    assert not auth._media_tickets


def test_ending_network_sessions_does_not_trip_over_a_late_unlock():
    def unlock(_):
        for _ in range(100):
            token = auth._issue_token()
            auth._network_tokens.add(token)
            auth._device_tokens[token] = "dev"

    def end(_):
        for _ in range(100):
            auth._end_network_sessions()

    errors = _run(8, lambda n: (unlock if n % 2 else end)(n))
    assert errors == []
