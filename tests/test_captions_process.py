"""The supervisor that runs the captions helper (`ai/captions_process.py`).

The child is `scratchpad/fake_captions_server.py --print-port` (a real process
on a real loopback port, no model, no engine), and the clock is a fixed one
the tests advance, so no test sleeps for a timeout. A real whisper.cpp child
is unverified here; `tests/test_captions_live.py` is the real-model check.
"""

from __future__ import annotations

import sys
from pathlib import Path

import pytest
import requests

from tessellate.ai import captions, captions_process
from tessellate.core import extras

ROOT = Path(__file__).resolve().parents[1]
FAKE = str(ROOT / "scratchpad" / "fake_captions_server.py")


class Clock:
    """A fixed clock; `sleep` advances it, so a start that never succeeds
    reaches its deadline without waiting."""

    def __init__(self) -> None:
        self.now = 1000.0

    def __call__(self) -> float:
        return self.now

    def sleep(self, seconds: float) -> None:
        self.now += seconds


@pytest.fixture()
def clock(monkeypatch):
    fixed = Clock()
    monkeypatch.setattr(captions_process, "clock", fixed)
    monkeypatch.setattr(captions_process, "sleep", fixed.sleep)
    return fixed


@pytest.fixture()
def installed(monkeypatch, tmp_path):
    """Both rows 'installed', the log in a scratch folder."""
    model = tmp_path / "ggml-tiny.en-q5_1.bin"
    model.write_bytes(b"x")
    monkeypatch.setattr(captions_process, "installed", lambda: True)
    monkeypatch.setattr(captions_process, "model_path", lambda: model)
    monkeypatch.setattr(captions_process, "_log_path", lambda: tmp_path / "logs" / "captions-helper.log")
    monkeypatch.delenv("TESSELLATE_CAPTIONS_URL", raising=False)
    captions._probe.update(at=0.0, url="", ok=False)
    return model


@pytest.fixture()
def child(monkeypatch):
    """Run the fake instead of the real helper; `extra` flags go to the fake."""
    flags: list[str] = []
    monkeypatch.setattr(
        captions_process,
        "_command",
        lambda model: [sys.executable, FAKE, "--print-port", "--model", str(model), *flags],
    )
    yield flags
    captions_process.reset_for_tests()


@pytest.fixture(autouse=True)
def _fresh():
    captions_process.reset_for_tests()
    yield
    captions_process.reset_for_tests()


def test_nothing_runs_until_the_first_start(installed, child, clock):
    assert captions_process.url() == ""
    assert captions.status()["available"] is True  # installed, starts on first use
    assert captions_process.url() == "", "a status poll must never start the helper"
    assert captions._env_url() == ""


def test_the_first_start_spawns_it_and_it_answers(installed, child, clock):
    url = captions_process.ensure_started()
    assert url.startswith("http://127.0.0.1:") and captions_process.url() == url
    http = requests.Session()
    http.trust_env = False
    assert http.get(url + "/", timeout=5).status_code == 200
    # A second call reuses the running child.
    assert captions_process.ensure_started() == url


def test_the_child_is_launched_with_the_model_and_cleanly(installed, monkeypatch):
    command = captions_process._command(installed)
    assert command[1:3] == ["-m", "tessellate.ai.captions_helper"]
    assert command[command.index("--model") + 1] == str(installed)
    assert "--exit-on-stdin-close" in command
    assert int(command[command.index("--threads") + 1]) >= 1


def test_the_log_is_truncated_per_start_and_named(installed, child, clock, tmp_path):
    captions_process.ensure_started()
    assert (tmp_path / "logs" / "captions-helper.log").is_file()


def test_status_says_starting_while_a_start_is_in_progress(installed, child, clock):
    captions_process.starting = True
    try:
        assert captions.status()["starting"] is True
    finally:
        captions_process.starting = False


def test_a_dead_child_is_restarted_on_the_next_use(installed, child, clock):
    first = captions_process.ensure_started()
    captions_process._proc.kill()
    captions_process._proc.wait()
    assert captions_process.url() == "", "a dead child has no address"
    second = captions_process.ensure_started()
    assert second.startswith("http://127.0.0.1:") and second != first  # a new child, a new port
    assert len(captions_process._crashes) == 1


def test_it_gives_up_after_too_many_crashes_in_the_window(installed, child, clock):
    for _ in range(captions_process.MAX_RESTARTS + 1):
        captions_process.ensure_started()
        captions_process._proc.kill()
        captions_process._proc.wait()
    with pytest.raises(captions_process.HelperError) as err:
        captions_process.ensure_started()
    assert err.value.args[0] == captions_process.STOPPED_HINT
    assert captions_process.gave_up() is True
    body = captions.status()
    assert body["available"] is False and body["hint"] == captions_process.STOPPED_HINT


def test_old_crashes_age_out_of_the_window(installed, child, clock):
    for _ in range(captions_process.MAX_RESTARTS + 1):
        captions_process.ensure_started()
        captions_process._proc.kill()
        captions_process._proc.wait()
    captions_process._crashes[:] = [clock.now] * (captions_process.MAX_RESTARTS + 1)
    assert captions_process.gave_up() is True
    clock.now += captions_process.RESTART_WINDOW + 1
    assert captions_process.gave_up() is False
    assert captions_process.ensure_started()


def test_a_child_that_never_answers_is_a_sentence_and_is_killed(installed, child, clock):
    child.append("--never-answer")
    with pytest.raises(captions_process.HelperError) as err:
        captions_process.ensure_started()
    assert err.value.args[0] == captions_process.NOT_STARTED_HINT
    assert captions_process._proc is None and captions_process.url() == ""
    assert clock.now - 1000.0 >= captions_process.START_TIMEOUT - captions_process.POLL_SECONDS
    assert captions_process.starting is False


def test_a_child_that_exits_before_a_port_is_a_sentence(installed, monkeypatch, clock):
    monkeypatch.setattr(captions_process, "_command", lambda model: [sys.executable, "-c", "raise SystemExit(3)"])
    with pytest.raises(captions_process.HelperError) as err:
        captions_process.ensure_started()
    assert err.value.args[0] == captions_process.NOT_STARTED_HINT
    assert captions_process._proc is None


def test_a_child_that_dies_later_has_no_address(installed, child, clock):
    child.extend(["--exit-after", "0.3"])
    captions_process.ensure_started()
    captions_process._proc.wait(timeout=10)
    assert captions_process.url() == ""


def test_a_child_that_prints_no_port_is_a_sentence(installed, monkeypatch, clock):
    monkeypatch.setattr(captions_process, "START_TIMEOUT", 0.3)
    monkeypatch.setattr(captions_process, "_command", lambda model: [sys.executable, "-c", "import time; time.sleep(30)"])
    with pytest.raises(captions_process.HelperError):
        captions_process.ensure_started()
    assert captions_process._proc is None


def test_a_missing_interpreter_is_a_sentence(installed, monkeypatch, clock):
    monkeypatch.setattr(captions_process, "_command", lambda model: ["/nonexistent/python-for-captions"])
    with pytest.raises(captions_process.HelperError) as err:
        captions_process.ensure_started()
    assert err.value.args[0] == captions_process.NOT_STARTED_HINT


def test_not_installed_is_a_sentence_and_spawns_nothing(monkeypatch, clock):
    monkeypatch.setattr(captions_process, "installed", lambda: False)
    monkeypatch.setattr(captions_process, "model_path", lambda: None)
    with pytest.raises(captions_process.HelperError, match="Install Live captions"):
        captions_process.ensure_started()
    assert captions_process._proc is None


def test_it_stops_five_minutes_after_the_last_session(installed, child, clock):
    captions_process.ensure_started()
    captions_process.session_ended(0)
    try:
        assert captions_process.idle_check() is False, "not yet"
        clock.now += captions_process.IDLE_STOP_SECONDS - 1
        assert captions_process.idle_check() is False
        clock.now += 2
        assert captions_process.idle_check() is True
        assert captions_process.url() == ""
    finally:
        captions_process.cancel_idle()


def test_a_session_still_running_keeps_it_alive(installed, child, clock):
    captions_process.ensure_started()
    captions_process.session_ended(1)
    assert captions_process._timer is None
    clock.now += captions_process.IDLE_STOP_SECONDS * 3
    assert captions_process.idle_check() is False and captions_process.url()


def test_a_new_session_cancels_the_idle_stop(installed, child, clock):
    captions_process.ensure_started()
    captions_process.session_ended(0)
    captions_process.ensure_started()  # the next begin()
    clock.now += captions_process.IDLE_STOP_SECONDS * 2
    assert captions_process.idle_check() is False and captions_process.url()


def test_stop_kills_the_child_and_forgets_crashes(installed, child, clock):
    captions_process.ensure_started()
    proc = captions_process._proc
    captions_process._crashes.append(clock.now)
    captions_process.stop()
    assert proc.poll() is not None
    assert captions_process.url() == "" and captions_process._crashes == []
    captions_process.stop()  # safe to repeat


def test_the_variable_wins_and_nothing_is_spawned(installed, child, clock, monkeypatch):
    monkeypatch.setenv("TESSELLATE_CAPTIONS_URL", "http://127.0.0.1:9")
    assert captions.helper_url() == "http://127.0.0.1:9"
    assert captions_process._proc is None


def test_the_engine_row_and_model_row_are_what_installed_means(monkeypatch):
    engine = extras.EXTRAS_BY_ID["captions"]
    monkeypatch.setattr(extras, "is_installed", lambda extra: extra.id == "captions")
    monkeypatch.setattr(extras, "download_ready", lambda extra_id: None)
    assert captions_process.installed() is False and engine.module == "pywhispercpp"
    monkeypatch.setattr(extras, "download_ready", lambda extra_id: Path("/models"))
    assert captions_process.installed() is True
    assert captions_process.model_path() == Path("/models") / extras.CAPTIONS_MODEL_FILE
    monkeypatch.setattr(extras, "is_installed", lambda extra: False)
    assert captions_process.installed() is False
