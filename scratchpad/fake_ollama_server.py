"""A stand-in Ollama for UI sweeps (INBOX 444).

    python3 scratchpad/fake_ollama_server.py 11500 &
    OLLAMA_URL=http://127.0.0.1:11500 bash scratchpad/ui-sweeps/serve.sh 8787 /tmp/mm-settings

The Models screen hides its pickers, the installed list and the suggested
downloads whenever Ollama is not running, so a sweep in a sandbox with no
Ollama measures a half-empty pane. This answers just enough for that screen:
`/api/tags` (two installed models), `/api/show`, `/api/delete`, and a slow
`/api/pull` that streams `completed`/`total` so a progress bar and a cancel
can be driven. It is not a model: chat requests get one fixed line.

**The tool-call dialect (WORLD_CLASS_PLAN row 19).** A `/api/chat` that
carries `tools` and no tool result yet is answered the way Ollama answers
one: NDJSON lines, the calls in one `message.tool_calls` list with each
call's `arguments` an object (not a JSON string, the OpenAI dialect's shape)
and a `function.index`, then a `done` line. `FAKE_OLLAMA_CALLS=2` sends two
calls in that one message, the concurrent case. A request with a `format`
schema (the forced round, `OllamaClient.forced_call_format`) is answered as
a grammar-decoded model answers it: the call as a JSON object in `content`,
split across lines; `FAKE_OLLAMA_REJECT_FORMAT=1` answers it 400 the way an
Ollama without schema formats does. A request with a tool result in it gets
prose. `GET /__requests` returns every chat body received, so a test can
read what the client sent.

Not verified against a real Ollama, which is the standing caveat (CLAUDE.md
section 4): the shapes here are the ones `ollama_client.py` reads, written
from Ollama's API documentation (`/api/chat`, "Chat request (with tools)").
"""

from __future__ import annotations

import json
import os
import sys
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

INSTALLED = [
    {"name": "llama3.2:latest", "size": 2_019_393_189, "modified_at": "2026-09-01T10:00:00Z"},
    {"name": "nomic-embed-text:latest", "size": 274_302_450, "modified_at": "2026-09-01T10:00:00Z"},
]


#: Every `/api/chat` body received, oldest first (`GET /__requests`).
REQUESTS: list[dict] = []

#: Read-only tools first, so a turn driven by this fake never stops on a
#: confirmation card; arguments only for the ones that need them.
PREFERRED = ("list_tags", "search_notes", "count_notes", "list_categories")
ARGUMENTS = {"search_notes": {"query": "notes"}}
ANSWER = "I looked through your notebook with the tools above."


def _offered(tools: list[dict]) -> list[str]:
    return [(t.get("function") or {}).get("name") for t in tools or [] if (t.get("function") or {}).get("name")]


def pick_calls(tools: list[dict], count: int) -> list[dict]:
    names = _offered(tools)
    ordered = [n for n in PREFERRED if n in names] + [n for n in names if n not in PREFERRED]
    return [{"name": n, "arguments": ARGUMENTS.get(n, {})} for n in ordered[: max(1, count)]]


class Handler(BaseHTTPRequestHandler):
    def log_message(self, *args):  # quiet
        pass

    def _json(self, payload, status=200):
        body = json.dumps(payload).encode()
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def _body(self):
        length = int(self.headers.get("Content-Length") or 0)
        return json.loads(self.rfile.read(length) or b"{}") if length else {}

    def _slow(self, which: str = "FAKE_OLLAMA_DELAY"):
        """`FAKE_OLLAMA_DELAY=<seconds>`: a runner busy loading a model answers
        its list, show and chat calls that late (INBOX 1492's /models/status);
        `FAKE_OLLAMA_SHOW_DELAY` slows `/api/show` alone, `FAKE_OLLAMA_TAGS_DELAY`
        the list alone."""
        time.sleep(float(os.environ.get(which) or os.environ.get("FAKE_OLLAMA_DELAY") or 0))

    def do_GET(self):
        if self.path.startswith("/api/tags"):
            self._slow("FAKE_OLLAMA_TAGS_DELAY")
            return self._json({"models": INSTALLED})
        if self.path.startswith("/__requests"):
            return self._json({"requests": REQUESTS})
        if self.path.startswith("/api/version"):
            return self._json({"version": "0.0-fake"})
        return self._json({"error": "not found"}, 404)

    def do_DELETE(self):
        name = self._body().get("name", "")
        INSTALLED[:] = [m for m in INSTALLED if m["name"] != name]
        self._json({})

    def do_POST(self):
        body = self._body()
        if self.path.startswith("/api/show"):
            self._slow("FAKE_OLLAMA_SHOW_DELAY")
        elif self.path.startswith("/api/chat"):
            self._slow()
        if self.path.startswith("/api/show"):
            return self._json({"capabilities": ["completion"], "model_info": {"llama.context_length": 8192}, "details": {"parameter_size": "3B", "quantization_level": "Q4_K_M"}})
        if self.path.startswith("/api/pull"):
            name = body.get("name", "x")
            self.send_response(200)
            self.send_header("Content-Type", "application/x-ndjson")
            self.end_headers()
            total = 3_000_000_000
            try:
                for step in range(0, 101):
                    # Padded past 512 bytes: the client reads the stream in
                    # 512-byte chunks, and real Ollama's progress lines arrive
                    # far faster than this fake's, so an unpadded one shows no
                    # progress for several seconds.
                    line = {"status": "pulling", "digest": "sha256:" + "0" * 480, "total": total, "completed": total * step // 100}
                    self.wfile.write((json.dumps(line) + "\n").encode())
                    self.wfile.flush()
                    time.sleep(0.4)
                INSTALLED.append({"name": name if ":" in name else name + ":latest", "size": total, "modified_at": "2026-10-03T10:00:00Z"})
                self.wfile.write((json.dumps({"status": "success"}) + "\n").encode())
            except (BrokenPipeError, ConnectionResetError):
                # The client cancelled the download: nothing left to send.
                pass
            return None
        if self.path.startswith("/api/chat"):
            REQUESTS.append(body)
            if body.get("tools"):
                return self._tools_chat(body)
            line = {"model": body.get("model"), "message": {"role": "assistant", "content": "ok"}, "done": True}
            return self._json(line)
        return self._json({"error": "not found"}, 404)

    def _tools_chat(self, body: dict):
        """Ollama's native tool-call dialect; see the module docstring."""
        model = body.get("model")
        answered = any((m or {}).get("role") == "tool" for m in body.get("messages") or [])
        if body.get("format") is not None and os.environ.get("FAKE_OLLAMA_REJECT_FORMAT"):
            return self._json({"error": "invalid format: schema not supported"}, 400)
        lines: list[dict] = []
        if answered:
            lines.append({"message": {"role": "assistant", "content": ANSWER}, "done": False})
        elif body.get("format") is not None:
            # Grammar-decoded: the call is the content, in pieces.
            call = pick_calls(body["tools"], 1)[0]
            text = json.dumps(call)
            lines += [{"message": {"role": "assistant", "content": text[i : i + 7]}, "done": False} for i in range(0, len(text), 7)]
        else:
            calls = pick_calls(body["tools"], int(os.environ.get("FAKE_OLLAMA_CALLS") or 1))
            lines.append(
                {
                    "message": {
                        "role": "assistant",
                        "content": "",
                        "tool_calls": [
                            {"function": {"index": i, "name": c["name"], "arguments": c["arguments"]}}
                            for i, c in enumerate(calls)
                        ],
                    },
                    "done": False,
                }
            )
        final = {"message": {"role": "assistant", "content": ""}, "done": True, "done_reason": "stop", "prompt_eval_count": 40, "eval_count": 12}
        if body.get("stream") is False:
            merged = {"role": "assistant", "content": "".join(line["message"].get("content") or "" for line in lines)}
            calls = [c for line in lines for c in line["message"].get("tool_calls") or []]
            if calls:
                merged["tool_calls"] = calls
            return self._json({"model": model, **final, "message": merged})
        self.send_response(200)
        self.send_header("Content-Type", "application/x-ndjson")
        self.end_headers()
        for line in [*lines, final]:
            self.wfile.write((json.dumps({"model": model, **line}) + "\n").encode())
            self.wfile.flush()
        return None


def serve(port: int = 0) -> ThreadingHTTPServer:
    """A server on `port` (0 for any free one), not yet serving; a test runs
    `serve_forever` in a thread and reads `server_address`."""
    return ThreadingHTTPServer(("127.0.0.1", port), Handler)


if __name__ == "__main__":
    port = int(sys.argv[1]) if len(sys.argv) > 1 else 11500
    ThreadingHTTPServer(("127.0.0.1", port), Handler).serve_forever()
