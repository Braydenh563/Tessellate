#!/usr/bin/env python3
"""A stand-in model that answers with prose quoting the notes it was given.

    .venv/bin/python scratchpad/fake_answer_server.py 8809

Grounding (`ai/grounding.py`) works on the *answer text* against the notes
that were retrieved, so testing it end to end needs a model whose answer
really does restate those notes. A canned sentence would ground to nothing
and the probe would report the feature broken when it was the fixture.

So this reads the prompt it is sent, pulls out the note bodies the app put in
it, and answers with one sentence per note built from that note's own words.
That is the shape a real answer has, and it is what makes the citation
numbers testable: sentence 1 must cite the note it was built from.

Speaks the OpenAI `/v1` dialect, streaming and not, like
`scratchpad/fake_openai_server.py`, which does the tool-calling half.
"""

from __future__ import annotations

import json
import os
import re
import sys
import time
from http.server import BaseHTTPRequestHandler, HTTPServer

#: FAKE_MODEL renames it, for a screenshot whose model badge a reader sees.
MODEL = os.environ.get("FAKE_MODEL") or "fake-answerer"
DUMP = os.environ.get("FAKE_DUMP") or ""
#: Milliseconds to wait between streamed words, off by default.
#:
#: A fixture that sends a whole answer inside one tick cannot be used to
#: measure anything the page does *while* it is streaming: the busy
#: affordance of INBOX 298 exists only between the first request and the last
#: token, and a probe polling for it saw either nothing or one frame. A real
#: small model takes seconds per sentence, so pacing the fixture is the
#: honest fixture, not a slower one.
STREAM_DELAY_MS = float(os.environ.get("FAKE_DELAY_MS") or 0)
#: `markdown` answers the way a real instruct model does (INBOX 318): a
#: lead-in ending in a colon, a bullet list whose items open with a bold
#: label, and a closing paragraph with emphasis inside a sentence. The plain
#: style (one bare sentence per note) is the easiest possible case for the
#: citation markers and hid every way they fail against formatted prose.
STYLE = os.environ.get("FAKE_STYLE") or "plain"
#: A written answer for a screenshot (`scratchpad/ui-sweeps/readme-ask.js`).
#: The quoting answerer above is right for a probe and wrong for the README:
#: it echoes note sentences back in a row, which proves the citations and
#: reads like nothing a model would write. With this set, a request carrying
#: the app's notes context ("My notes:") is answered with the file's text
#: instead, and the follow-up prompt with the lines of `FAKE_FOLLOWUPS_FILE`.
#: The answer still has to earn its citations: grounding scores it against
#: the retrieved notes like any other answer, so it is written in their words.
ANSWER_FILE = os.environ.get("FAKE_ANSWER_FILE") or ""
FOLLOWUPS_FILE = os.environ.get("FAKE_FOLLOWUPS_FILE") or ""
#: Thinking sent as `reasoning_content` before the answer (INBOX 534: a chat
#: scroll sweep needs the thinking fold to exist while the answer streams).
THINK_FILE = os.environ.get("FAKE_THINK_FILE") or ""


def _read(path: str) -> str:
    with open(path, encoding="utf-8") as fh:
        return fh.read().strip()


def _markdown_answer(sentences: list[str]) -> str:
    """The same sentences, dressed the way a model dresses them."""
    if len(sentences) < 2:
        return " ".join(sentences)
    lead = "Here is what your notes say:"
    items = []
    for sentence in sentences[:-1]:
        words = sentence.split()
        label = words[1].strip(".,").capitalize() if len(words) > 1 else "Note"
        items.append(f"- **{label}:** {sentence}")
    last = sentences[-1].split()
    #: Emphasis mid-sentence, so the sentence spans three text nodes once
    #: rendered: the shape a marker matched per text node can never find.
    if len(last) > 4:
        last[2] = f"*{last[2]}*"
    return lead + "\n\n" + "\n".join(items) + "\n\nAlso, " + " ".join(last)


def _sentences_from_prompt(prompt: str) -> list[str]:
    """One sentence per note the app put in the prompt.

    The app's context block is a numbered list under "My notes:", one note per
    line, shaped `3. [General] (similarity: 0.56) the note's text`. Parsing
    that shape rather than "any long line" matters: the first version took the
    system preamble and the category prefixes with it, and the answer came
    back opening "You are Atlas, this notebook's librarian. General] ...". A
    probe reading that answer would blame the product for a fixture that had
    never quoted a note cleanly in the first place.

    A note's own first sentence is what a model would paraphrase, and echoing
    it verbatim is the strongest possible grounding signal, which is what a
    probe wants: if the numbers are wrong here they are wrong everywhere.
    """
    out: list[str] = []
    #: Since SEC-02 a note's words are fenced on the lines after its header
    #: (`1. [General] (written ...) <<<data note>>>`, the text, `<<<end
    #: data>>>`); the fence is folded back onto the header line here, so the
    #: parse below reads the shape it always read.
    folded: list[str] = []
    fenced = False
    for line in prompt.splitlines():
        if line.rstrip().endswith(">>>") and "<<<data" in line:
            folded.append(line[: line.index("<<<data")].rstrip())
            fenced = True
            continue
        if fenced:
            if line.strip().startswith("<<<end data"):
                fenced = False
                continue
            folded[-1] += " " + line.strip()
            continue
        folded.append(line)
    for line in folded:
        #: Split rather than matched. CodeQL flagged the regex this replaces
        #: (`^\s*\d+\.\s+(.*)$`, high severity: polynomial backtracking on
        #: uncontrolled data) because the prompt is attacker-shaped input as
        #: far as it is concerned and the two whitespace classes around the
        #: number can be made to backtrack. `partition` cannot backtrack at
        #: all, and says the same thing in fewer characters.
        head, dot, rest = line.strip().partition(".")
        if not dot or not head.isdigit():
            continue
        text = rest.strip()
        text = re.sub(r"^\[[^\]]*\]\s*", "", text)          # [General]
        #: Every leading group, not the first: the header now carries several
        #: (`(matched: boots) (tags: gear)`), and the answer quoted them.
        while text.startswith("(") and ")" in text:
            text = text[text.index(")") + 1 :].lstrip()  # (similarity: 0.56)
        if len(text.split()) < 6:
            continue
        first = re.split(r"(?<=[.!?])\s", text)[0]
        if first not in out:
            out.append(first if first.endswith((".", "!", "?")) else first + ".")
        if len(out) >= 4:
            break
    return out or ["I could not find anything in your notes about that."]


class Handler(BaseHTTPRequestHandler):
    #: Chunked, like LM Studio / llama.cpp: a close-delimited HTTP/1.0 stream
    #: is read by `requests` in 512-byte blocks and reaches the page in bursts
    #: (INBOX 534: a sweep of a *live* stream saw the whole answer land at once).
    protocol_version = "HTTP/1.1"

    def log_message(self, *_args) -> None:  # noqa: ANN002
        pass

    def do_GET(self) -> None:  # noqa: N802
        if self.path.rstrip("/").endswith("/models"):
            self._json({"object": "list", "data": [{"id": MODEL, "object": "model"}]})
        else:
            self.send_error(404)

    def do_POST(self) -> None:  # noqa: N802
        length = int(self.headers.get("Content-Length") or 0)
        body = json.loads(self.rfile.read(length) or b"{}")
        prompt = "\n".join(str(m.get("content") or "") for m in body.get("messages", []))
        if DUMP:
            with open(DUMP, "a", encoding="utf-8") as fh:
                fh.write("=== prompt ===\n" + prompt + "\n")
        self.prompt = prompt
        if FOLLOWUPS_FILE and "Suggest short follow-up questions" in prompt:
            answer = _read(FOLLOWUPS_FILE)
        elif ANSWER_FILE and "My notes:" in prompt:
            answer = _read(ANSWER_FILE)
        else:
            sentences = _sentences_from_prompt(prompt)
            answer = _markdown_answer(sentences) if STYLE == "markdown" else " ".join(sentences)
        if body.get("stream"):
            self._sse(answer)
        else:
            self._json({
                "id": "fake", "object": "chat.completion", "model": MODEL,
                "choices": [{"index": 0, "message": {"role": "assistant", "content": answer},
                             "finish_reason": "stop"}],
            })

    def _json(self, payload: dict) -> None:
        raw = json.dumps(payload).encode()
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(raw)))
        self.end_headers()
        self.wfile.write(raw)

    def _sse(self, answer: str) -> None:
        self.send_response(200)
        self.send_header("Content-Type", "text/event-stream")
        self.send_header("Transfer-Encoding", "chunked")
        self.end_headers()
        raw_write = self.wfile.write

        def chunked(data: bytes) -> None:
            raw_write(b"%x\r\n" % len(data) + data + b"\r\n")

        self.wfile.write = chunked  # type: ignore[method-assign]
        #: Word by word, because the Ask tab renders as it streams and the
        #: citation markers are written against the finished text: a fake that
        #: sent the answer in one chunk would not exercise that ordering.
        think = _read(THINK_FILE) if THINK_FILE and ANSWER_FILE and "My notes:" in self.prompt else ""
        for word in think.split(" ") if think else []:
            chunk = {"choices": [{"index": 0, "delta": {"reasoning_content": word + " "}}]}
            self.wfile.write(f"data: {json.dumps(chunk)}\n\n".encode())
            self.wfile.flush()
            if STREAM_DELAY_MS:
                time.sleep(STREAM_DELAY_MS / 1000)
        for word in answer.split(" "):
            chunk = {"choices": [{"index": 0, "delta": {"content": word + " "}}]}
            self.wfile.write(f"data: {json.dumps(chunk)}\n\n".encode())
            self.wfile.flush()
            if STREAM_DELAY_MS:
                time.sleep(STREAM_DELAY_MS / 1000)
        done = {"choices": [{"index": 0, "delta": {}, "finish_reason": "stop"}]}
        self.wfile.write(f"data: {json.dumps(done)}\n\n".encode())
        self.wfile.write(b"data: [DONE]\n\n")
        raw_write(b"0\r\n\r\n")
        self.wfile.flush()


if __name__ == "__main__":
    port = int(sys.argv[1]) if len(sys.argv) > 1 else 8809
    print(f"fake answerer on http://127.0.0.1:{port}/v1", flush=True)
    HTTPServer(("127.0.0.1", port), Handler).serve_forever()
