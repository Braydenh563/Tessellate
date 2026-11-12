"""The retry of a download extra's opening request (owner review, 2026-11-08):
Retry-After is honoured up to a cap, Stop during the wait starts no further
request, and only opening the connection is retried. A fake opener and a fake
sleep stand in for the network and the clock; no real time passes."""

from __future__ import annotations

import urllib.error
from types import SimpleNamespace

import pytest

from tessellate.core import extra_downloads

URL = "https://example.invalid/core.tar.bz2"


def _state():
    return SimpleNamespace(log=[], cancelled=False)


def _http(code, retry_after=None):
    headers = {} if retry_after is None else {"Retry-After": retry_after}
    return urllib.error.HTTPError(URL, code, "x", headers, None)


class _Opener:
    """Raises each of `errors` in turn, then returns a response."""

    def __init__(self, *errors):
        self.errors = list(errors)
        self.calls = 0

    def __call__(self, url):
        self.calls += 1
        if self.errors:
            raise self.errors.pop(0)
        return "response"


@pytest.fixture
def slept(monkeypatch):
    """The seconds asked of the fake sleep; the cancel hook is set per test."""
    log: list[float] = []
    monkeypatch.setattr(extra_downloads.time, "sleep", log.append)
    return log


def _open(monkeypatch, opener, state):
    monkeypatch.setattr(extra_downloads, "_open_url", opener)
    return extra_downloads._open_retrying(URL, state)


def test_retry_after_on_a_429_is_the_wait(monkeypatch, slept):
    opener = _Opener(_http(429, "7"))
    assert _open(monkeypatch, opener, _state()) == "response"
    assert sum(slept) == pytest.approx(7)


def test_retry_after_on_a_503_is_the_wait(monkeypatch, slept):
    assert _open(monkeypatch, _Opener(_http(503, "12")), _state()) == "response"
    assert sum(slept) == pytest.approx(12)


def test_retry_after_is_capped(monkeypatch, slept):
    assert _open(monkeypatch, _Opener(_http(429, "86400")), _state()) == "response"
    assert sum(slept) == pytest.approx(extra_downloads._RETRY_AFTER_CAP)
    assert extra_downloads._RETRY_AFTER_CAP == 30.0


def test_a_retry_after_date_is_read_against_the_clock(monkeypatch, slept):
    monkeypatch.setattr(extra_downloads.time, "time", lambda: 1_700_000_000.0)
    # 1,700,000_010 s after the epoch is 2023-11-14 22:13:30 GMT: ten seconds on.
    assert _open(monkeypatch, _Opener(_http(503, "Tue, 14 Nov 2023 22:13:30 GMT")), _state()) == "response"
    assert sum(slept) == pytest.approx(10)


@pytest.mark.parametrize("header", ["soon", "-5", ""])
def test_an_unusable_retry_after_falls_back_to_the_fixed_wait(monkeypatch, slept, header):
    assert _open(monkeypatch, _Opener(_http(503, header)), _state()) == "response"
    assert sum(slept) == pytest.approx(extra_downloads._RETRY_WAITS[0])


def test_without_retry_after_the_fixed_waits_stand(monkeypatch, slept):
    assert _open(monkeypatch, _Opener(_http(502), _http(504)), _state()) == "response"
    assert sum(slept) == pytest.approx(sum(extra_downloads._RETRY_WAITS))


def test_retry_after_on_a_502_is_not_read(monkeypatch, slept):
    """Only 429 and 503 name a wait; a gateway error keeps the fixed one."""
    assert _open(monkeypatch, _Opener(_http(502, "20")), _state()) == "response"
    assert sum(slept) == pytest.approx(extra_downloads._RETRY_WAITS[0])


def test_stop_during_the_wait_starts_no_further_request(monkeypatch):
    state = _state()
    slices: list[float] = []

    def sleep(seconds):
        slices.append(seconds)
        state.cancelled = True  # Stop pressed while the wait runs

    monkeypatch.setattr(extra_downloads.time, "sleep", sleep)
    opener = _Opener(_http(503), _http(503), _http(503))
    with pytest.raises(extra_downloads.DownloadFailed) as caught:
        _open(monkeypatch, opener, state)
    assert caught.value.args[0] == "stopped"
    assert opener.calls == 1
    assert len(slices) == 1 and slices[0] < extra_downloads._RETRY_WAITS[0]


def test_stop_before_the_wait_still_starts_nothing(monkeypatch, slept):
    state = _state()

    class Stopping(_Opener):
        def __call__(self, url):
            state.cancelled = True
            return super().__call__(url)

    opener = Stopping(_http(503))
    with pytest.raises(extra_downloads.DownloadFailed):
        _open(monkeypatch, opener, state)
    assert opener.calls == 1 and slept == []


def test_a_connection_that_cannot_be_opened_is_retried(monkeypatch, slept):
    opener = _Opener(urllib.error.URLError("refused"), ConnectionResetError("reset"))
    assert _open(monkeypatch, opener, _state()) == "response"
    assert opener.calls == 3


def test_a_missing_file_is_not_retried(monkeypatch, slept):
    opener = _Opener(_http(404))
    with pytest.raises(urllib.error.HTTPError):
        _open(monkeypatch, opener, _state())
    assert opener.calls == 1 and slept == []


def test_a_body_that_breaks_off_is_not_resumed(monkeypatch, tmp_path):
    """Only opening the connection is retried: a read that fails mid-stream
    fails the download, and nothing asks the server again."""

    class Broken:
        def __enter__(self):
            return self

        def __exit__(self, *exc):
            return False

        def read(self, _n):
            raise ConnectionResetError("reset")

    opener = _Opener()
    opener.errors = []
    monkeypatch.setattr(extra_downloads, "_open_url", lambda url: (setattr(opener, "calls", opener.calls + 1), Broken())[1])
    download = extra_downloads.Download(url=URL, sha256="0" * 64, size=10, unpack="file", members=(("", "out"),))
    with pytest.raises(ConnectionResetError):
        extra_downloads._fetch(download, tmp_path / "out", _state(), "x")
    assert opener.calls == 1


def test_the_docstring_says_only_the_opening_is_retried():
    doc = extra_downloads._open_retrying.__doc__
    assert "dropped" not in doc and "opened" in doc
