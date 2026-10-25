"""needle as a tool-calling fallback (INBOX 302).

The owner, 2026-09-24: "Yes, as an extra" (opt-in, telemetry forced off).
needle is a 121M-parameter tool-calling model driven through `ctypes`; the
agent uses it to pick and fill tools when no Ollama or OpenAI-compatible
backend is running. These tests hold the seam with a fake engine: which
provider is chosen with and without it, that telemetry is off before the
library loads, and that nothing imports it unless it is installed. The one
test that needs the real engine is `evals`, skipped unless
`TESSELLATE_NEEDLE_DIR` names an installed copy.
"""

from __future__ import annotations

import ctypes
import json
import os
import subprocess
import sys
from pathlib import Path

import pytest

from tessellate.ai.provider import Provider, ProviderError
from tessellate.core import extra_downloads, extras

ROOT = Path(__file__).resolve().parent.parent


def _install_fake_needle():
    """The needle folder as a finished install leaves it, with stand-ins."""
    extra = extras.EXTRAS_BY_ID["needle"]
    target = extra_downloads.folder(extra)
    target.mkdir(parents=True, exist_ok=True)
    from tessellate.ai import needle_provider

    names = [needle_provider.library_name(), "needle3.cact", "LICENSE"]
    for name in names:
        (target / name).write_bytes(b"x")
    (target / extra_downloads.MARKER).write_text(
        json.dumps({"version": extra.version, "files": names}), encoding="utf-8"
    )
    return target


class _FakeFn:
    def __init__(self, impl):
        self.impl = impl
        self.argtypes = None
        self.restype = None

    def __call__(self, *args):
        return self.impl(*args)


class FakeLib:
    """The engine's C API, answering from a script."""

    def __init__(self, path, answers=None, env_at_load=None):
        self.path = path
        self.env_at_load = env_at_load
        self.answers = list(answers or [])
        self.inits = []
        self.completes = []
        self.loads = 0
        self.needle_load = _FakeFn(self._load)
        self.needle_init = _FakeFn(self._init)
        self.needle_complete = _FakeFn(self._complete)
        self.needle_reset = _FakeFn(lambda: None)
        self.needle_last_error = _FakeFn(lambda: b"too many tools")

    def _load(self, data, n):
        self.loads += 1
        return 0

    def _init(self, system, tools, index):
        self.inits.append((system, tools))
        return -1 if b"FAIL" in tools else 10

    def _complete(self, text, max_new, buf, cap):
        self.completes.append(text)
        answer = self.answers.pop(0) if self.answers else {"function_calls": []}
        raw = json.dumps(answer).encode()
        ctypes.memmove(buf, raw, len(raw))
        return len(raw)


@pytest.fixture()
def fake_engine(app_state, monkeypatch):
    """Installs a fake needle and a loader that records the environment it
    was called in."""
    from tessellate.ai import needle_provider

    needle_provider.reset_for_tests()
    _install_fake_needle()
    made = []

    def loader(path):
        lib = FakeLib(
            path,
            env_at_load={k: os.environ.get(k) for k in needle_provider.TELEMETRY_OFF},
        )
        made.append(lib)
        return lib

    monkeypatch.setattr(needle_provider, "_load_library", loader)
    for key in needle_provider.TELEMETRY_OFF:
        monkeypatch.delenv(key, raising=False)
    yield made
    needle_provider.reset_for_tests()


class _Down(Provider):
    name = "ollama"

    def is_running(self):
        return False


class _Up(Provider):
    name = "ollama"

    def is_running(self):
        return True


TOOLS = [
    {
        "type": "function",
        "function": {
            "name": "create_reminder",
            "description": "Create a reminder",
            "parameters": {"type": "object", "properties": {"text": {"type": "string"}}},
        },
    }
]


# --- selection -----------------------------------------------------------------------


def test_a_running_backend_is_always_chosen(fake_engine):
    from tessellate.ai import tool_fallback

    primary = _Up()
    assert tool_fallback.for_tools(primary) is primary


def test_needle_answers_tools_when_nothing_else_is_running(fake_engine):
    from tessellate.ai import tool_fallback

    chosen = tool_fallback.for_tools(_Down())
    assert chosen is not None and chosen.name == "needle"
    assert chosen.is_running()


def test_without_the_extra_there_is_no_fallback_and_nothing_is_imported(app_state, monkeypatch):
    from tessellate.ai import tool_fallback

    #: Restored afterwards, so later tests see the one module object.
    monkeypatch.delitem(sys.modules, "tessellate.ai.needle_provider", raising=False)
    assert tool_fallback.for_tools(_Down()) is None
    assert "tessellate.ai.needle_provider" not in sys.modules


def test_the_app_starts_without_importing_it():
    """The app starts identically without the extra: a fresh interpreter
    builds the app and answers a request, and the module was never loaded."""
    code = (
        "import sys, tempfile, os\n"
        "os.environ['TESSELLATE_DATA_DIR'] = tempfile.mkdtemp()\n"
        "from fastapi.testclient import TestClient\n"
        "from tessellate.api.app import create_app\n"
        "c = TestClient(create_app())\n"
        "assert c.get('/health').status_code == 200\n"
        "assert 'tessellate.ai.needle_provider' not in sys.modules, 'imported'\n"
        "assert not any(m.startswith('needle') for m in sys.modules), 'needle imported'\n"
        "print('ok')\n"
    )
    env = {**os.environ, "PYTHONPATH": str(ROOT / "src")}
    done = subprocess.run(
        [sys.executable, "-c", code], env=env, capture_output=True, text=True, timeout=120
    )
    assert done.returncode == 0 and "ok" in done.stdout, done.stderr[-2000:]


# --- telemetry, loading ------------------------------------------------------------------


def test_telemetry_is_off_before_the_library_loads(fake_engine):
    from tessellate.ai import needle_provider

    provider = needle_provider.NeedleProvider()
    provider.chat_tools("any", [{"role": "user", "content": "remind me"}], TOOLS)
    assert fake_engine, "the engine was never loaded"
    assert fake_engine[0].env_at_load == {"NEEDLE_TELEMETRY": "0", "DO_NOT_TRACK": "1"}
    assert fake_engine[0].path.endswith(needle_provider.library_name())
    assert fake_engine[0].loads == 1


def test_the_engine_is_loaded_once_per_process(fake_engine):
    from tessellate.ai import needle_provider

    provider = needle_provider.NeedleProvider()
    for _ in range(3):
        provider.chat_tools("any", [{"role": "user", "content": "x"}], TOOLS)
    assert len(fake_engine) == 1
    #: The same tools are not re-initialised for every turn.
    assert len(fake_engine[0].inits) == 1


# --- the provider's answers ------------------------------------------------------------


def test_tool_calls_come_back_in_the_agents_shape(fake_engine):
    from tessellate.ai import needle_provider

    provider = needle_provider.NeedleProvider()
    lib_answers = [
        {
            "function_calls": [{"name": "create_reminder", "arguments": {"text": "call mum"}}],
            "confidence": 0.95,
        }
    ]
    provider._engine()  # noqa: SLF001  # load, so the script can be set
    fake_engine[0].answers = lib_answers
    reply = provider.chat_tools(
        "any", [{"role": "system", "content": "long"}, {"role": "user", "content": "remind me to call mum"}], TOOLS
    )
    assert reply["tool_calls"] == [{"name": "create_reminder", "arguments": {"text": "call mum"}}]
    assert reply["raw_tool_calls"][0]["function"]["name"] == "create_reminder"
    #: needle is handed the user's words and the tools, never the app's
    #: long system prompt.
    assert fake_engine[0].completes == [b"remind me to call mum"]
    system, tools = fake_engine[0].inits[0]
    assert b"long" not in system
    assert json.loads(tools) == [TOOLS[0]["function"]]


def test_the_stream_is_one_final(fake_engine):
    from tessellate.ai import needle_provider

    pieces = list(
        needle_provider.NeedleProvider().chat_tools_stream(
            "any", [{"role": "user", "content": "hello"}], TOOLS
        )
    )
    assert len(pieces) == 1 and "final" in pieces[0]
    assert pieces[0]["final"]["streamed"] is False


def test_no_fitting_tool_says_so_in_one_line(fake_engine):
    from tessellate.ai import needle_provider

    reply = needle_provider.NeedleProvider().chat_tools(
        "any", [{"role": "user", "content": "tell me a joke"}], TOOLS
    )
    assert reply["tool_calls"] == []
    assert "model" in reply["content"] and "reminders" in reply["content"]  # the composer words it (CHAT_PLAN 1353)


def test_after_the_tools_ran_their_results_are_the_answer(fake_engine):
    """needle writes no prose: once the tools have run, the turn ends with
    what they said rather than a second call that would pick them again."""
    from tessellate.ai import needle_provider

    messages = [
        {"role": "user", "content": "remind me"},
        {"role": "assistant", "content": "", "tool_calls": [{"function": {"name": "create_reminder"}}]},
        {"role": "tool", "tool_name": "create_reminder", "content": "Reminder set for 5 pm."},
    ]
    reply = needle_provider.NeedleProvider().chat_tools("any", messages, TOOLS)
    assert reply["tool_calls"] == []
    assert reply["content"] == "Reminder set for 5 pm."
    assert fake_engine == [] or fake_engine[0].completes == []


def test_a_json_result_is_not_pasted_into_the_reply(fake_engine):
    from tessellate.ai import needle_provider

    messages = [
        {"role": "user", "content": "what is in my notebook"},
        {"role": "tool", "tool_name": "notebook_overview", "content": '{"total_notes": 0}'},
    ]
    reply = needle_provider.NeedleProvider().chat_tools("any", messages, TOOLS)
    #: Said as an answer (INBOX 801), never the step's name or the raw JSON.
    assert "{" not in reply["content"] and "notebook_overview" not in reply["content"]
    assert reply["content"] and "step above" not in reply["content"]


def test_prose_is_refused_plainly(fake_engine):
    from tessellate.ai import needle_provider

    with pytest.raises(ProviderError):
        needle_provider.NeedleProvider().chat("any", [{"role": "user", "content": "hi"}])


def test_an_engine_that_cannot_take_the_tools_says_why(fake_engine):
    from tessellate.ai import needle_provider

    bad = [{"type": "function", "function": {"name": "FAIL"}}]
    with pytest.raises(ProviderError, match="too many tools"):
        needle_provider.NeedleProvider().chat_tools("any", [{"role": "user", "content": "x"}], bad)


def test_removing_it_while_the_engine_is_loaded_asks_for_a_restart(fake_engine):
    """Windows cannot delete a DLL a process has mapped."""
    from tessellate.ai import needle_provider

    needle_provider.NeedleProvider().chat_tools("any", [{"role": "user", "content": "x"}], TOOLS)
    started, message = extras.remove("needle")
    assert started is False and "Restart" in message
    needle_provider.reset_for_tests()
    extras.reset_for_tests()
    removed, _message = extras.remove("needle")
    assert removed is True


# --- the route seam -----------------------------------------------------------------------


def test_the_agent_route_uses_it_only_when_the_backend_is_down():
    """Source check: the fallback is asked only after `is_running()` said no,
    and only for a turn that may use tools."""
    source = (ROOT / "src" / "tessellate" / "api" / "routes_chat.py").read_text(encoding="utf-8")
    at = source.index("tool_fallback.for_tools(req.ollama)")
    before = source[at - 400 : at]
    assert "not ollama_running and req.use_tools" in before


# --- the real engine ------------------------------------------------------------------------


@pytest.mark.evals
@pytest.mark.skipif(
    not os.environ.get("TESSELLATE_NEEDLE_DIR"),
    reason="needs the real needle engine: TESSELLATE_NEEDLE_DIR=<an installed needle folder>",
)
def test_the_real_engine_picks_a_tool(monkeypatch):
    from tessellate.ai import needle_provider

    needle_provider.reset_for_tests()
    monkeypatch.setattr(
        needle_provider, "_folder", lambda: Path(os.environ["TESSELLATE_NEEDLE_DIR"])
    )
    reply = needle_provider.NeedleProvider().chat_tools(
        "any", [{"role": "user", "content": "remind me to call mum tomorrow"}], TOOLS
    )
    assert [c["name"] for c in reply["tool_calls"]] == ["create_reminder"]
    assert os.environ["NEEDLE_TELEMETRY"] == "0" and os.environ["DO_NOT_TRACK"] == "1"


@pytest.mark.evals
@pytest.mark.skipif(
    not os.environ.get("TESSELLATE_NEEDLE_DIR"),
    reason="needs the real needle engine: TESSELLATE_NEEDLE_DIR=<an installed needle folder>",
)
def test_the_real_engine_takes_the_apps_own_core_tools(monkeypatch):
    """The app's own schemas, the set a small model is offered, not a toy."""
    from tessellate.ai import needle_provider, tools

    needle_provider.reset_for_tests()
    monkeypatch.setattr(
        needle_provider, "_folder", lambda: Path(os.environ["TESSELLATE_NEEDLE_DIR"])
    )
    offered = tools.ollama_tools(
        [n for n in tools.CORE_TOOLS if n not in tools.ORCHESTRATION_TOOLS]
    )
    reply = needle_provider.NeedleProvider().chat_tools(
        "any", [{"role": "user", "content": "save a note titled Garden saying plant the tulips"}], offered
    )
    names = [c["name"] for c in reply["tool_calls"]]
    assert names and set(names) <= {t["function"]["name"] for t in offered}, reply
