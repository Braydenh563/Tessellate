#!/usr/bin/env python3
"""A stdlib stand-in for LM Studio / llama.cpp / Jan / vLLM, with tool calls.

**Why this exists.** CLAUDE.md's standing caveat: every provider test in this
repo runs against a fake `requests` transport, so `chat_tools` /
`chat_tools_stream` — the code that reassembles a tool call out of streamed
fragments — had never met a real socket. A previous session lifted the
*plain*-streaming half of that caveat with a server like this one; this is the
tool-calling half, and it is what Phase C's "verify tool calls render in the
chat transcript" is driven against.

It is a real `http.server` on a real port speaking the OpenAI `/v1` dialect:

  GET  /v1/models             one model, so the Models screen and
                              `is_running()` see a reachable backend.
  POST /v1/chat/completions   non-streaming and `stream: true` SSE.

**The script it follows** is the smallest one that exercises the whole path:

  * a request that carries `tools` and has **no** `role: "tool"` message in it
    yet is a *first* call, and is answered with exactly ONE tool call;
  * a request that already has a tool result in its history is a *second*
    call, and is answered with plain prose.

That is what makes a turn terminate: the agent loop calls the tool, appends
the result, asks again, and gets an answer.

**The tool it picks comes from the request, never from a hard-coded name.**
The app offers a different subset per turn (Settings → "How many are offered
at once", and Phase B's small-model mode narrows it to one), so a fixed name
would be refused as unknown on any turn that did not happen to include it.
`list_tags` and `search_notes` are preferred because both are read-only —
a destructive tool would stop the turn on a confirmation card instead.

**The streamed shape is OpenAI's, fragment for fragment**, because that is the
part this repo has never been able to test: index 0 with the `id` and
`function.name` on the FIRST fragment only, then `function.arguments` split
across several later chunks, each carrying nothing else. `_accumulate_tool_calls`
in `ai/openai_client.py` folds those back together by index, and if it did not,
the argument JSON would arrive truncated and the call would fail to parse.

**Concurrent calls (`--calls 2` or `FAKE_CALLS=2`, WORLD_CLASS_PLAN row 19).**
Two calls in one reply, streamed the hard way: index 1's identity arrives in
the same `tool_calls` delta as index 0's first argument piece, and from then
on the two indices' argument pieces alternate, so a client that keyed the
fragments by arrival order, or kept only index 0, joins one call's JSON onto
the other's. The second call's later pieces carry no `id`, as OpenAI's do.

Run it:  python3 scratchpad/fake_openai_server.py --port 8799
Point the app at it with POST /models/provider {"provider":"openai",
"base_url":"http://127.0.0.1:8799/v1"}.
"""

from __future__ import annotations

import argparse
import json
import os
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

#: The model the catalogue advertises. Deliberately carries no parameter count
#: in its name: `model_manager.parameter_count` reads a size out of a model
#: name and Phase B's `small_model_mode: auto` treats "no idea" as off, so a
#: name like this keeps auto-mode's answer stable while the toggle is tested.
MODEL_ID = "fake-local-tools"

#: Read-only tools, in preference order — see the module docstring.
PREFERRED_TOOLS = ("list_tags", "search_notes")

#: Arguments per tool, only for the ones that need any.
ARGUMENTS = {"search_notes": {"query": "notes"}}

#: **Overrides, for a sweep that needs a *particular* tool called.** Added for
#: the typed-cards sweep (PLAN.md §4 A1), which has to see a file, a board and
#: a reminder come back — none of which `list_tags` or `search_notes` can
#: produce. Env rather than a flag so an existing sweep's command line is
#: untouched, and both default to empty, which leaves every earlier run
#: byte-identical.
#:
#:   FAKE_TOOLS=list_reminders FAKE_ARGS='{"list_reminders":{}}' python3 …
_ENV_TOOLS = tuple(name.strip() for name in os.environ.get("FAKE_TOOLS", "").split(",") if name.strip())
try:
    _ENV_ARGUMENTS = json.loads(os.environ.get("FAKE_ARGS") or "{}")
except ValueError:
    _ENV_ARGUMENTS = {}

ANSWER = (
    "I checked your notebook with the tool above and there is nothing "
    "surprising in it."
)


#: Calls per tool round (`--calls`, `FAKE_CALLS`); see the module docstring.
CALLS = max(1, int(os.environ.get("FAKE_CALLS") or 1))

#: A server that cannot honour `tool_choice` and says so with an empty 200
#: (`FAKE_BREAK_TOOL_CHOICE=1`, B69: llama-cpp-python's chatml-function-calling
#: handler asserts on "required" after the stream has opened). A request that
#: names the field gets headers and a clean end with no frame.
BREAK_TOOL_CHOICE = bool(os.environ.get("FAKE_BREAK_TOOL_CHOICE"))

#: A slow backend (`FAKE_STREAM_DELAY_MS`, ledger 1530): the plain-text answer
#: arrives as `STREAM_PIECES` pieces with this pause before each, so a Stop
#: pressed mid-answer has something to stop. 0 is the ordinary instant stand-in.
STREAM_DELAY_MS = int(os.environ.get("FAKE_STREAM_DELAY_MS") or 0)
STREAM_PIECES = 8


def _pick_tools(tools: list[dict], count: int) -> list[tuple[str, dict]]:
    """`count` distinct tools out of what the request offered, the preferred
    read-only ones first."""
    names = [((e or {}).get("function") or {}).get("name") or (e or {}).get("name") for e in tools or []]
    names = [n for n in names if n]
    arguments = {**ARGUMENTS, **_ENV_ARGUMENTS}
    ordered = [n for n in (*_ENV_TOOLS, *PREFERRED_TOOLS) if n in names] + names
    picked: list[str] = []
    for name in ordered:
        if name not in picked:
            picked.append(name)
    return [(n, arguments.get(n, {})) for n in picked[:count]]


#: A scripted run (`FAKE_SCRIPT=calls.json`, Brief 87): a JSON list of
#: `[name, arguments]`, one popped per tool round while it lasts, so a plan
#: run can make a different write in each step. Then the default pick.
_SCRIPT: list = []
if os.environ.get("FAKE_SCRIPT"):
    with open(os.environ["FAKE_SCRIPT"], encoding="utf-8") as handle:
        _SCRIPT = json.load(handle)


def _pick_tool(tools: list[dict]) -> tuple[str, dict] | None:
    """The tool to call, chosen out of what this very request offered."""
    names = []
    for entry in tools or []:
        function = (entry or {}).get("function") or {}
        name = function.get("name") or entry.get("name")
        if name:
            names.append(name)
    if not names:
        return None
    #: Popped only by a request that offers the scripted tool, so a side
    #: request (a classifier, a title) does not eat a step's write.
    if os.environ.get("FAKE_LOG"):
        print("offered", len(names), "script", [c[0] for c in _SCRIPT], ",".join(names), flush=True)
    if _SCRIPT and _SCRIPT[0][0] in names:
        name, arguments = _SCRIPT.pop(0)
        return name, arguments
    arguments = {**ARGUMENTS, **_ENV_ARGUMENTS}
    for preferred in (*_ENV_TOOLS, *PREFERRED_TOOLS):
        if preferred in names:
            return preferred, arguments.get(preferred, {})
    return names[0], arguments.get(names[0], {})


#: Milliseconds to hold a *nudged* round open (`--nudge-delay`). Phase A's
#: re-prompt is the only time a step sits in the `retrying` state, and against
#: a server that answers in three milliseconds that state exists for less than
#: a frame — so it cannot be screenshotted or polled for, only caught by a
#: MutationObserver. A real model takes seconds; this makes the stand-in take
#: some too, but only on the rounds where it matters.
NUDGE_DELAY_MS = 0


def _is_nudged(messages: list[dict]) -> bool:
    """True when this request carries a contract nudge (`skills.contract_nudge`
    — "You did not call `list_notes`. Call it now.")."""
    for message in messages or []:
        content = (message or {}).get("content")
        if isinstance(content, str) and "You did not" in content:
            return True
    return False


#: Tool rounds before the answer (`--tool-rounds`); H1's plan card needs a
#: three-round turn, which one call then prose never makes.
TOOL_ROUNDS = 1
#: Milliseconds every request waits (`--round-delay`), so a live state lasts.
ROUND_DELAY_MS = 0


def _already_called(messages: list[dict]) -> bool:
    """True once `TOOL_ROUNDS` tool results are in the history, i.e. the
    model is expected to answer in words."""
    done = sum(1 for message in messages or [] if (message or {}).get("role") == "tool")
    return done >= TOOL_ROUNDS


def _usage(messages: list[dict], output: str) -> dict:
    prompt = sum(len(str((m or {}).get("content") or "")) for m in messages or [])
    return {
        "prompt_tokens": max(1, prompt // 4),
        "completion_tokens": max(1, len(output) // 4),
        "total_tokens": max(2, (prompt + len(output)) // 4),
    }


class Handler(BaseHTTPRequestHandler):
    protocol_version = "HTTP/1.1"

    # Quiet: this runs beside a Playwright script and its own access log is
    # noise in the transcript. The app's log is the one being read.
    def log_message(self, *_args) -> None:  # noqa: D102
        return

    # --- plumbing -----------------------------------------------------------

    def _json(self, payload: dict, status: int = 200) -> None:
        body = json.dumps(payload).encode()
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def _sse_open(self) -> None:
        self.send_response(200)
        self.send_header("Content-Type", "text/event-stream")
        self.send_header("Cache-Control", "no-cache")
        # Chunked rather than a length: the app reads this with
        # `requests`' `iter_lines`, and a stream is what it is.
        self.send_header("Transfer-Encoding", "chunked")
        self.end_headers()

    def _sse_send(self, payload: dict | str) -> None:
        line = payload if isinstance(payload, str) else json.dumps(payload)
        chunk = f"data: {line}\n\n".encode()
        self.wfile.write(b"%x\r\n" % len(chunk) + chunk + b"\r\n")
        self.wfile.flush()

    def _sse_close(self) -> None:
        self._sse_send("[DONE]")
        self.wfile.write(b"0\r\n\r\n")
        self.wfile.flush()

    # --- routes -------------------------------------------------------------

    def do_GET(self) -> None:  # noqa: N802 — BaseHTTPRequestHandler's name
        if self.path.rstrip("/") in ("/v1/models", "/models"):
            self._json(
                {
                    "object": "list",
                    "data": [
                        {
                            "id": MODEL_ID,
                            "object": "model",
                            "created": int(time.time()),
                            "owned_by": "fake",
                            # What LM Studio reports and what the app reads to
                            # budget the prompt. Big enough that nothing is
                            # trimmed during a test run.
                            "max_context_length": 32768,
                            "loaded_context_length": 32768,
                        }
                    ],
                }
            )
            return
        # Everything else — `/api/v0/models`, `/props` — is a probe the client
        # is written to survive a 404 on.
        self._json({"error": "not found"}, status=404)

    def do_POST(self) -> None:  # noqa: N802
        length = int(self.headers.get("Content-Length") or 0)
        try:
            body = json.loads(self.rfile.read(length) or b"{}")
        except ValueError:
            self._json({"error": "bad json"}, status=400)
            return
        if self.path.rstrip("/") not in ("/v1/chat/completions", "/chat/completions"):
            self._json({"error": "not found"}, status=404)
            return

        messages = body.get("messages") or []
        tools = body.get("tools") or []
        if ROUND_DELAY_MS:
            time.sleep(ROUND_DELAY_MS / 1000)
        if NUDGE_DELAY_MS and _is_nudged(messages):
            time.sleep(NUDGE_DELAY_MS / 1000)
        if CALLS > 1:
            calls = [] if _already_called(messages) else _pick_tools(tools, CALLS)
            if body.get("stream"):
                self._stream_many(calls) if calls else self._stream(None)
            else:
                self._complete_many(calls, messages)
            return
        if BREAK_TOOL_CHOICE and body.get("tool_choice") and body.get("stream"):
            self._sse_open()
            self.wfile.write(b"0\r\n\r\n")
            self.wfile.flush()
            return
        call = None if _already_called(messages) else _pick_tool(tools)
        if body.get("stream"):
            self._stream(call)
        else:
            self._complete(call, messages)

    def _complete_many(self, calls: list[tuple[str, dict]], messages: list[dict]) -> None:
        if not calls:
            self._complete(None, messages)
            return
        message = {
            "role": "assistant",
            "content": None,
            "tool_calls": [
                {"id": f"call_fake_{i}", "type": "function", "function": {"name": n, "arguments": json.dumps(a)}}
                for i, (n, a) in enumerate(calls)
            ],
        }
        self._json(
            {
                "id": "chatcmpl-fake",
                "object": "chat.completion",
                "created": int(time.time()),
                "model": MODEL_ID,
                "choices": [{"index": 0, "message": message, "finish_reason": "tool_calls"}],
                "usage": _usage(messages, ""),
            }
        )

    def _stream_many(self, calls: list[tuple[str, dict]]) -> None:
        """Several calls in one streamed reply, interleaved by index."""
        created = int(time.time())

        def frame(delta: dict, finish: str | None = None) -> dict:
            return {
                "id": "chatcmpl-fake",
                "object": "chat.completion.chunk",
                "created": created,
                "model": MODEL_ID,
                "choices": [{"index": 0, "delta": delta, "finish_reason": finish}],
            }

        def head(i: int, name: str) -> dict:
            return {"index": i, "id": f"call_fake_{i}", "type": "function", "function": {"name": name, "arguments": ""}}

        pieces = [[json.dumps(a)[k : k + 3] for k in range(0, len(json.dumps(a)), 3)] for _n, a in calls]
        self._sse_open()
        self._sse_send(frame({"role": "assistant"}))
        self._sse_send(frame({"tool_calls": [head(0, calls[0][0])]}))
        # Index 1 announced in the same delta as index 0's first piece.
        first = [{"index": 0, "function": {"arguments": pieces[0].pop(0)}}]
        first.extend(head(i, name) for i, (name, _a) in enumerate(calls) if i)
        self._sse_send(frame({"tool_calls": first}))
        while any(pieces):
            for i, rest in enumerate(pieces):
                if rest:
                    self._sse_send(frame({"tool_calls": [{"index": i, "function": {"arguments": rest.pop(0)}}]}))
        self._sse_send(frame({}, finish="tool_calls"))
        self._sse_close()

    # --- the two answer shapes ----------------------------------------------

    def _complete(self, call: tuple[str, dict] | None, messages: list[dict]) -> None:
        created = int(time.time())
        if call:
            name, arguments = call
            message = {
                "role": "assistant",
                # Null content beside `tool_calls` is what the spec says and
                # what real servers send.
                "content": None,
                "tool_calls": [
                    {
                        "id": "call_fake_0",
                        "type": "function",
                        "function": {"name": name, "arguments": json.dumps(arguments)},
                    }
                ],
            }
            finish = "tool_calls"
            output = ""
        else:
            message = {"role": "assistant", "content": ANSWER}
            finish = "stop"
            output = ANSWER
        self._json(
            {
                "id": "chatcmpl-fake",
                "object": "chat.completion",
                "created": created,
                "model": MODEL_ID,
                "choices": [{"index": 0, "message": message, "finish_reason": finish}],
                "usage": _usage(messages, output),
            }
        )

    def _stream(self, call: tuple[str, dict] | None) -> None:
        created = int(time.time())

        def frame(delta: dict, finish: str | None = None) -> dict:
            return {
                "id": "chatcmpl-fake",
                "object": "chat.completion.chunk",
                "created": created,
                "model": MODEL_ID,
                "choices": [{"index": 0, "delta": delta, "finish_reason": finish}],
            }

        self._sse_open()
        self._sse_send(frame({"role": "assistant"}))
        if call:
            name, arguments = call
            # **Fragment one carries the identity and nothing else.** This is
            # the exact shape OpenAI streams and the one this repo had never
            # exercised against a socket: id + name here, arguments nowhere.
            self._sse_send(
                frame(
                    {
                        "tool_calls": [
                            {
                                "index": 0,
                                "id": "call_fake_0",
                                "type": "function",
                                "function": {"name": name, "arguments": ""},
                            }
                        ]
                    }
                )
            )
            # …and the argument JSON arrives in pieces, each one only an
            # `arguments` string on the same index. Split at three characters
            # so a `{"query": "notes"}` is spread over several chunks and a
            # client that forgot to concatenate would produce invalid JSON.
            encoded = json.dumps(arguments)
            for start in range(0, len(encoded), 3):
                self._sse_send(
                    frame(
                        {
                            "tool_calls": [
                                {
                                    "index": 0,
                                    "function": {"arguments": encoded[start : start + 3]},
                                }
                            ]
                        }
                    )
                )
            self._sse_send(frame({}, finish="tool_calls"))
        else:
            if STREAM_DELAY_MS:
                size = max(1, -(-len(ANSWER) // STREAM_PIECES))
                pieces = [ANSWER[i : i + size] for i in range(0, len(ANSWER), size)]
            else:
                pieces = [ANSWER[:40], ANSWER[40:]]
            for piece in pieces:
                if STREAM_DELAY_MS:
                    time.sleep(STREAM_DELAY_MS / 1000)
                self._sse_send(frame({"content": piece}))
            self._sse_send(frame({}, finish="stop"))
        self._sse_close()


def serve(port: int = 0, host: str = "127.0.0.1") -> ThreadingHTTPServer:
    """A server on `port` (0 for any free one), not yet serving; a test runs
    `serve_forever` in a thread and reads `server_address`."""
    return ThreadingHTTPServer((host, port), Handler)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--port", type=int, default=8799)
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument(
        "--nudge-delay",
        type=int,
        default=0,
        help="ms to hold a contract-nudge round open, so the retrying state is visible",
    )
    parser.add_argument("--tool-rounds", type=int, default=1, help="tool rounds before the answer")
    parser.add_argument("--round-delay", type=int, default=0, help="ms every request waits")
    parser.add_argument("--calls", type=int, default=0, help="tool calls per round, interleaved (FAKE_CALLS)")
    args = parser.parse_args()
    global NUDGE_DELAY_MS, TOOL_ROUNDS, ROUND_DELAY_MS, CALLS
    CALLS = max(1, args.calls) if args.calls else CALLS
    NUDGE_DELAY_MS = args.nudge_delay
    TOOL_ROUNDS = max(1, args.tool_rounds)
    ROUND_DELAY_MS = args.round_delay
    server = serve(args.port, args.host)
    print(f"fake OpenAI server on http://{args.host}:{args.port}/v1", flush=True)
    server.serve_forever()


if __name__ == "__main__":
    main()
