"""Delayed OpenAI-compatible stub: /v1/models and a streamed /v1/chat/completions that
sends reasoning_content for THINK seconds, then content words, one every GAP seconds.
Usage: python stub_llm.py PORT [THINK=3] [GAP=0.25]"""

import json
import sys
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

PORT = int(sys.argv[1])
THINK = float(sys.argv[2]) if len(sys.argv) > 2 else 3.0
GAP = float(sys.argv[3]) if len(sys.argv) > 3 else 0.25
LOG_PATH = f"/tmp/stub_llm_{PORT}.log"


def log(event):
    with open(LOG_PATH, "a") as f:
        f.write(f"{time.time():.2f} {event}\n")


class H(BaseHTTPRequestHandler):
    protocol_version = "HTTP/1.1"

    def log_message(self, *a):
        pass

    def _send(self, code, body, ctype="application/json"):
        data = body if isinstance(body, bytes) else json.dumps(body).encode()
        self.send_response(code)
        self.send_header("Content-Type", ctype)
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)

    def do_GET(self):
        self._send(200, {"object": "list", "data": [{"id": "stub-1", "object": "model"}]})

    def do_POST(self):
        n = int(self.headers.get("Content-Length") or 0)
        body = json.loads(self.rfile.read(n) or b"{}")
        if not body.get("stream"):
            self._send(
                200,
                {
                    "id": "x",
                    "object": "chat.completion",
                    "choices": [
                        {
                            "index": 0,
                            "message": {"role": "assistant", "content": "Stub reply."},
                            "finish_reason": "stop",
                        }
                    ],
                },
            )
            return
        self.send_response(200)
        self.send_header("Content-Type", "text/event-stream")
        self.send_header("Transfer-Encoding", "chunked")
        self.end_headers()

        def chunk(delta, fin=None):
            payload = {
                "id": "x",
                "object": "chat.completion.chunk",
                "choices": [{"index": 0, "delta": delta, "finish_reason": fin}],
            }
            data = ("data: " + json.dumps(payload) + "\n\n").encode()
            self.wfile.write(b"%x\r\n" % len(data) + data + b"\r\n")
            self.wfile.flush()

        try:
            log("start")
            t0 = time.time()
            i = 0
            while time.time() - t0 < THINK:
                chunk({"reasoning_content": f"thinking step {i}. "})
                i += 1
                time.sleep(GAP)
            words = (
                "The weekend trip needs a tent, a stove and two warm layers, packed the night before so the morning is calm. "
                * 6
            ).split()
            for w in words:
                chunk({"content": w + " "})
                time.sleep(GAP)
            chunk({}, "stop")
            self.wfile.write(b"0\r\n\r\n")
            self.wfile.flush()
            log("finished")
        except (BrokenPipeError, ConnectionResetError):
            log("client_closed")
        return


ThreadingHTTPServer(("127.0.0.1", PORT), H).serve_forever()
