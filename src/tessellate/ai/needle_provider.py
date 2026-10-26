"""needle, a small tool-calling model run in this process (INBOX 302).

The owner, 2026-09-24: "Yes, as an extra" (opt-in, telemetry forced off).
The repository read (ANALYSIS.md, "Twenty-four repositories read", needle)
named the one thing it would buy: the agent works on a machine with no
Ollama and no model server at all. needle is a 121M-parameter model from
Cactus Compute (Apache-2.0, code and weights) that does three things, tool
calls, extraction and embeddings, with a decode grammar that makes an
unparseable call impossible. It writes no prose, and this provider does not
pretend it does.

**How it runs.** The `needle` extra (`core/extras.py`) downloads the prebuilt
engine for this platform, `libneedle3`, and the `needle3.cact` weights into
the data dir. This module loads the library with `ctypes`, hands it the
weights once, and speaks the five-function C API its header declares
(`needle_load`, `needle_init`, `needle_complete`, `needle_reset`,
`needle_last_error`). The engine is one process-global model and not
thread-safe, so every call holds `_lock`. The `cactus-needle` Python package
is not used: it would fetch from Hugging Face at first use and carries its
own telemetry client.

**Telemetry is off before the library loads.** needle's README: "By default,
telemetry is turned on in the binary. To turn it off, set environment
variables NEEDLE_TELEMETRY=0 and DO_NOT_TRACK=1." Both are written into this
process's environment (which `getenv` in the library reads) before
`ctypes.CDLL` runs, every time, whatever the user's shell had. Measured
2026-09-24 on the pinned linux-x86_64 engine: `nm -D libneedle3.so` imports
no `getenv`, `socket`, `connect` or `send`, and `strings` finds no URL and
no telemetry name, so that library has no way to phone home; the README's
sentence is presumably about needle's command-line binary and its Python
package, neither of which is used here. The variables are set anyway,
because the promise is cheap to keep. INBOX 699, 2026-10-06: the install now
reads the engine's imported symbols itself (`core/native_imports.py`, ELF, PE
and Mach-O) and refuses one that imports a socket, name-lookup or HTTP call;
all six pinned glibc, macOS and Windows engines were read that way and import
none. Not verified: a packet capture of a real run, and the two musl engines'
contents (their hashes are pinned; the install check covers them).

**Only imported when installed.** `ai/tool_fallback.py` asks the extra's
folder first and imports this module only when it is there, so an app
without the extra never loads it (`tests/test_needle_provider.py` starts a
fresh interpreter to hold that).

**What the agent gets.** `chat_tools` takes the newest user message and the
offered tools (the app's own OpenAI-shaped schemas, unwrapped), and returns
needle's calls in the agent's shape. Not the app's system prompt: needle's
context is small and its grammar does the job the prompt's rules do for a
chat model. Once the tools have run, there is no model to write the reply,
so the turn ends with what the tools themselves said. A request no tool
fits says so in one line. Measured on the pinned engine in this sandbox's
CPU: 9 to 11 s per call (4 to 8 tokens a second), 102 MB resident; a real
desktop will differ.
"""

from __future__ import annotations

import ctypes
import json
import os
import sys
import threading
import time
from datetime import datetime
from collections.abc import Iterator
from pathlib import Path

from tessellate.ai import composer_compose as compose
from tessellate.ai import needle_control
from tessellate.ai.provider import Provider, ProviderError, normalise_tool_calls

#: Written into the environment before the engine loads (see the docstring).
TELEMETRY_OFF = {"NEEDLE_TELEMETRY": "0", "DO_NOT_TRACK": "1"}

#: The name the agent's stats and Settings show.
MODEL_NAME = "needle3"

#: needle's calls are short; this bounds a runaway decode.
MAX_NEW_TOKENS = 256

_lock = threading.Lock()
_engine: _Engine | None = None


def library_name() -> str:
    """The engine's file name on this platform, as the extra unpacks it."""
    if sys.platform == "darwin":
        return "libneedle3.dylib"
    if sys.platform == "win32":
        return "libneedle3.dll"
    return "libneedle3.so"


def _folder() -> Path | None:
    from tessellate.core import extras

    return extras.download_ready("needle")


def _load_library(path: str):
    """`ctypes.CDLL`, as a seam the tests replace with a fake engine."""
    return ctypes.CDLL(path)


class _Engine:
    """The loaded library and the weights in it. One per process."""

    def __init__(self, folder: Path) -> None:
        # Before the library is loaded, and before anything in it can read
        # them: the whole point of the owner's "telemetry forced off".
        os.environ.update(TELEMETRY_OFF)
        lib = _load_library(str(folder / library_name()))
        lib.needle_init.argtypes = [ctypes.c_char_p, ctypes.c_char_p, ctypes.c_char_p]
        lib.needle_init.restype = ctypes.c_int
        lib.needle_complete.argtypes = [ctypes.c_char_p, ctypes.c_int, ctypes.c_char_p, ctypes.c_int]
        lib.needle_complete.restype = ctypes.c_int
        lib.needle_load.argtypes = [ctypes.c_char_p, ctypes.c_uint64]
        lib.needle_load.restype = ctypes.c_int
        lib.needle_reset.argtypes = []
        lib.needle_reset.restype = None
        lib.needle_last_error.argtypes = []
        lib.needle_last_error.restype = ctypes.c_char_p
        weights = (folder / "needle3.cact").read_bytes()
        if lib.needle_load(weights, len(weights)) < 0:
            raise ProviderError(f"needle could not load its weights: {self._error(lib)}")
        self.lib = lib
        self._bound: tuple[bytes, bytes] | None = None
        self._buffer = ctypes.create_string_buffer(65536)

    @staticmethod
    def _error(lib) -> str:
        try:
            raw = lib.needle_last_error()
        except Exception:  # noqa: BLE001  # the reason is a courtesy
            return "no reason given"
        if isinstance(raw, bytes):
            return raw.decode("utf-8", "replace") or "no reason given"
        return str(raw or "no reason given")

    def complete(self, system: str, tools_json: str, text: str) -> dict:
        """One tool-calling turn. Holds the process-wide lock throughout."""
        key = (system.encode("utf-8"), tools_json.encode("utf-8"))
        with _lock:
            if key != self._bound:
                if self.lib.needle_init(key[0], key[1], None) < 0:
                    self._bound = None
                    raise ProviderError(f"needle could not take these tools: {self._error(self.lib)}")
                self._bound = key
            # Every turn stands alone: the agent sends the whole request each
            # time, and needle's own history would only repeat it.
            self.lib.needle_reset()
            code = self.lib.needle_complete(
                text.encode("utf-8"), MAX_NEW_TOKENS, self._buffer, len(self._buffer)
            )
            if code < 0:
                raise ProviderError(f"needle failed: {self._error(self.lib)}")
            raw = self._buffer.value.decode("utf-8", "replace")
        try:
            answer = json.loads(raw)
        except ValueError as exc:
            raise ProviderError("needle answered with something that is not JSON.") from exc
        return answer if isinstance(answer, dict) else {}


def _get_engine() -> _Engine:
    global _engine
    with _lock:
        if _engine is None:
            folder = _folder()
            if folder is None:
                raise ProviderError("The needle extra is not installed.")
            _engine = _Engine(folder)
        return _engine


def loaded() -> bool:
    """Is the engine mapped into this process? `core/extras.py` asks before
    removing the extra: Windows cannot delete a loaded DLL."""
    return _engine is not None


def reset_for_tests() -> None:
    global _engine
    _engine = None


def _text(content) -> str:
    """A message's words, whether a string or a list of parts."""
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        return " ".join(
            str(part.get("text") or "") for part in content if isinstance(part, dict)
        ).strip()
    return ""


def _date_fact() -> str:
    """What needle's own package adds so "tomorrow" means something."""
    return time.strftime("Today is %A, %Y-%m-%d.")


#: Tools needle is never offered (INBOX 801: every run ended "Couldn't ask
#: user"): asking the person mid-run, and the tools that hand their work to a
#: chat model (a plan, a skill, a compressed chat, a contradiction or link
#: audit). With no model they can only fail, so they are not planned.
#: Needle reads every schema on every call (72 tools were 30,089 chars and
#: 50 s on the owner's Windows machine, 2026-10-19), so it is offered a
#: shortlist: the tools the question's words suggest (`tools.focus_for`), or
#: the likeliest by `tools.rank_tools` when the question hints at none.
NEEDLE_MAX_TOOLS = 15


def shortlist(schemas: list[dict], text: str) -> list[dict]:
    """`schemas` cut to at most `NEEDLE_MAX_TOOLS`, in their given order."""
    if len(schemas) <= NEEDLE_MAX_TOOLS:
        return schemas
    from tessellate.ai import tools

    have = {s.get("name") for s in schemas}
    focus = tools.focus_for(text)
    keep = [] if focus is None else [n for n in dict.fromkeys([*tools.CORE_TOOLS, *focus]) if n in have]
    if not keep or len(keep) > NEEDLE_MAX_TOOLS:
        keep = [n for n, _ in tools.rank_tools(text) if n in have][:NEEDLE_MAX_TOOLS]
    chosen = set(keep)
    return [s for s in schemas if s.get("name") in chosen]


NOT_WITHOUT_A_MODEL = frozenset({
    "ask_user", "make_plan", "run_skill", "save_skill", "compress_chat", "find_contradictions", "audit_link_reasons",
})

#: Where the agent's user turn puts the person's words, after the app's own
#: lines about the notes it found (`agent._build_messages`). Needle reads the
#: whole turn, and those lines name tools ("count_notes and search_notes do"):
#: it searched for "doesn't have count_notes" (INBOX 1345 b), a refusal's own
#: wording fed back as a query. It is given the request alone.
_REQUEST = "My request:"


def request_of(text: str) -> str:
    """The person's words from an agent user turn, without the app's preamble."""
    _, marker, tail = text.rpartition(_REQUEST)
    return tail.strip() if marker and tail.strip() else text


def _names_a_tool(arguments: object, offered: dict) -> bool:
    """A tool's name inside an argument: the app's own text read back as a
    request, never something the person asked to find."""
    if not isinstance(arguments, dict):
        return False
    words = " ".join(str(v) for v in arguments.values() if isinstance(v, str)).lower()
    return any(name and name in words for name in offered)


def _cleaned_calls(calls: list, schemas: list[dict], text: str, strict: bool = True) -> list[dict]:
    """needle's calls with their arguments cleaned (INBOX 801: "NOTEBOOK
    STATS" called search_notes with an empty query): every string tidied, an
    empty search query given the request's topic, and a call still missing a
    required string, or naming a tool it was not offered, dropped."""
    offered = {s.get("name"): s for s in schemas}
    out = []
    for call in calls:
        if not isinstance(call, dict) or call.get("name") not in offered:
            continue
        if _names_a_tool(call.get("arguments"), offered):
            continue
        args = _cleaned_arguments(call.get("arguments") or {}, offered[call["name"]].get("parameters") or {}, text)
        #: A decided act keeps a call missing a slot: the composer fills or asks.
        if args is not None or not strict:
            args = args if args is not None else dict(call.get("arguments") or {})
            out.append({"function": {"name": call["name"], "arguments": args}})
    return out


def _cleaned_arguments(arguments: dict, parameters: dict, text: str) -> dict | None:
    """One call's arguments tidied, an empty query filled with the topic;
    None when a required string is still empty."""
    from tessellate.ai import question_noise

    args = {k: question_noise.tidy(v) if isinstance(v, str) else v for k, v in arguments.items()}
    if "query" in (parameters.get("properties") or {}) and not args.get("query"):
        args["query"] = question_noise.topic_of(text)
    if any(isinstance(args.get(r, ""), str) and not args.get(r) for r in parameters.get("required") or []):
        return None
    return args


def _said_by_tools(messages: list[dict]) -> str:
    """What the tools since the last request said, each as an answer (INBOX
    801: "it doesnt output tool results with the composer"; the owner,
    2026-10-11: "properly outputted in human readable ways and well
    structured"): `tool_say` gives each a lead, a list or table, links to
    what it names and the next tap; a failure as a sentence and the next
    step. Never the raw JSON, never "see the step"."""
    said = []
    tail = []
    for message in reversed(messages):
        if message.get("role") != "tool":
            break
        tail.append(message)
    calls = _calls_before(messages, len(tail))
    for n, message in enumerate(reversed(tail)):
        name = str(message.get("tool_name") or "")
        args = calls[n] if n < len(calls) and calls[n][0] == name else (name, {})
        said.append(_said_by_one(name, _text(message.get("content")).strip(), args[1]))
    return "\n\n".join(s for s in said if s)


def _calls_before(messages: list[dict], results: int) -> list[tuple[str, dict]]:
    """The (name, arguments) of the calls the last `results` tool messages
    answer, in order: the assistant turn just before them."""
    at = len(messages) - results - 1
    if at < 0 or messages[at].get("role") != "assistant":
        return []
    out = []
    for call in messages[at].get("tool_calls") or []:
        fn = (call or {}).get("function") or {}
        args = fn.get("arguments")
        if isinstance(args, str):
            try:
                args = json.loads(args)
            except ValueError:
                args = {}
        out.append((str(fn.get("name") or ""), args if isinstance(args, dict) else {}))
    return out


def voice_now() -> str:
    """The voice the person picked for the composer (Settings, Chat); the
    default voice when no preference can be read."""
    try:
        from tessellate.core import deps

        return str(deps.get_config().get_preference("composer_voice", "natural"))
    except Exception:  # noqa: BLE001  # no config in a bare test or a fresh process
        return "natural"


def _said_by_one(name: str, words: str, args: dict | None = None) -> str:
    from tessellate.ai import tool_say

    if words[:1] not in ("{", "["):
        return words[:600]
    try:
        result = json.loads(words)
    except ValueError:
        result = None
    if not isinstance(result, dict):
        return "Done."
    #: The composer words the acts it decides itself (`needle_control.confirm`).
    mood = compose.mood_of("", voice=voice_now(), seed=words, intent="act")
    return needle_control.confirm(name, result, args or {}, mood) or tool_say.say(name, result, args or {}, datetime.now().date())["text"]


def _usable_schemas(tools: list[dict] | None) -> list[dict]:
    """The tool schemas needle may be shown: the ones that work without a model."""
    return [
        t["function"] for t in tools or []
        if isinstance(t, dict) and t.get("function") and t["function"].get("name") not in NOT_WITHOUT_A_MODEL
    ]


class NeedleProvider(Provider):
    """A `Provider` that can only call tools. See the module docstring."""

    name = "needle"

    def _engine(self) -> _Engine:
        return _get_engine()

    # --- what a backend reports ---------------------------------------------------

    def context_length(self, model: str) -> int | None:
        return None

    def is_running(self) -> bool:
        return _folder() is not None

    def list_models(self) -> list[dict]:
        return [{"name": MODEL_NAME, "size": 0, "modified_at": ""}]

    def supports(self, model: str, capability: str) -> bool | None:
        return capability == "tools"

    # --- generation ---------------------------------------------------------------

    def chat(self, model: str, messages: list[dict], mode: str | None = None) -> dict:
        raise ProviderError(
            "needle picks tools and writes no replies. A written answer needs a "
            "model server such as Ollama (Settings, Models)."
        )

    def chat_stream(self, model: str, messages: list[dict], mode: str | None = None):
        raise ProviderError(
            "needle picks tools and writes no replies. A written answer needs a "
            "model server such as Ollama (Settings, Models)."
        )

    def embed(self, model: str, text: str) -> list[float]:
        raise ProviderError("needle is not used for search here.")

    def chat_tools(
        self,
        model: str,
        messages: list[dict],
        tools: list[dict],
        mode: str | None = None,
    ) -> dict:
        started = time.monotonic()
        last = messages[-1] if messages else {}
        if last.get("role") == "tool":
            # The tools have run. There is no model to write the reply, so the
            # reply is what they said, in order, since the last request.
            return self._reply(_said_by_tools(messages) or "Done.", [], started)

        text = request_of(next(
            (_text(m.get("content")) for m in reversed(messages) if m.get("role") == "user"), ""
        ))
        schemas = _usable_schemas(tools)
        mood = compose.mood_of(text, voice=voice_now(), seed=text, intent="act")
        decided = needle_control.decide(text, {s.get("name") for s in schemas})
        #: The composer decides; needle is shown only the decided tool and
        #: fills its slots (`ai/needle_control.py`).
        shown = needle_control.offer(schemas, decided) if decided else shortlist(schemas, text)
        answer = self._engine().complete(_date_fact(), json.dumps(shown), text)
        raw_calls = _cleaned_calls(answer.get("function_calls") or [], shown, text, strict=not decided)
        if decided:
            verdict = needle_control.validate(decided, raw_calls, text, datetime.now(), mood)
            raw_calls = [needle_control.call_for(decided, verdict.call)] if verdict.call else []
            return self._reply(verdict.say, raw_calls, started, answer)
        return self._reply("" if raw_calls else needle_control.nothing_fits(mood), raw_calls, started, answer)

    def chat_tools_stream(
        self,
        model: str,
        messages: list[dict],
        tools: list[dict],
        mode: str | None = None,
    ) -> Iterator[dict]:
        """One final piece: needle answers whole, and has no prose to stream."""
        yield {"final": {**self.chat_tools(model, messages, tools, mode), "streamed": False}}

    @staticmethod
    def _reply(content: str, raw_calls: list[dict], started: float, answer: dict | None = None) -> dict:
        return {
            "content": content,
            "thinking": (answer or {}).get("reasoning") or None,
            "tool_calls": normalise_tool_calls(raw_calls),
            "raw_tool_calls": raw_calls,
            #: The same keys the other providers report. needle counts no
            #: tokens, so the counts are None rather than a guess.
            "stats": {
                "model": MODEL_NAME,
                "prompt_tokens": None,
                "output_tokens": None,
                "total_ms": round((time.monotonic() - started) * 1000),
                "eval_ms": None,
                "context_tokens": None,
                "usage_source": "estimated",
            },
        }
