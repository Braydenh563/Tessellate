"""A stopped answer ends with a `done` line, and the page shows it stopped (W1, t20#9).

Activity's Stop ended the chat stream after an answer delta with no `done`
line, so the page drew a cut-off answer as a finished one: no "Stopped" on the
bubble, Atlas pleased, the run marked done. Measured with a slow fake model
(w1stop.js, MODE=activity): last line `answer_final`, meta "3.3s Agent
llama3.2"; the browser's own Stop left the same meta line.
"""

from __future__ import annotations

import json
import re
import shutil
import subprocess

import pytest

from tessellate.core import activity
from tests._app_js import JS_DIR, app_js_text


def _lines(stop_after: int, event: activity.StopEvent, last_done: bool = False):
    for i in range(5):
        if i == stop_after:
            event.set()
        yield json.dumps({"type": "answer", "delta": f"w{i} "}) + "\n"
    if last_done:
        yield json.dumps({"type": "done"}) + "\n"


def test_a_stopped_stream_ends_with_a_stopped_done_line():
    event = activity.StopEvent()
    out = list(activity.tracked_stream("generation", "t", _lines(1, event), stop_event=event, stopped_line=activity.STOPPED_DONE))
    assert [json.loads(line)["type"] for line in out] == ["answer", "answer", "done"]
    assert json.loads(out[-1]) == {"type": "done", "stopped": True}


def test_every_answer_stream_asks_for_the_stopped_line():
    """Chat, the Guide, the documents check and the drafting desk read NDJSON
    with a closing `done`; each passes the line (other streams keep none)."""
    from pathlib import Path

    api = Path(activity.__file__).parents[1] / "api"
    for name in ("routes_chat.py", "routes_help.py", "routes_documents.py", "routes_drafts.py"):
        assert "stopped_line=activity.STOPPED_DONE" in (api / name).read_text(encoding="utf-8"), name


def test_a_stream_that_ended_on_its_own_done_gets_no_second_one():
    event = activity.StopEvent()
    out = list(activity.tracked_stream("generation", "t", _lines(9, event, last_done=True), stop_event=event, stopped_line=activity.STOPPED_DONE))
    assert [json.loads(line)["type"] for line in out].count("done") == 1
    assert "stopped" not in json.loads(out[-1])


def test_the_stream_reader_reads_a_stopped_done_as_a_stop():
    """`streamChatEvents` throws the AbortError a browser Stop throws, so the
    turn ends down the one stopped path (status, run state, meta line)."""
    kit = (JS_DIR / "answer-kit.js").read_text(encoding="utf-8")
    assert "else if (event.stopped) throw Object.assign(Error(), { name: \"AbortError\" });" in kit


@pytest.mark.skipif(not shutil.which("node"), reason="needs node")
def test_the_meta_line_of_a_stopped_answer_says_stopped():
    kit = (JS_DIR / "answer-kit.js").read_text(encoding="utf-8")
    body = re.search(r"^function messageMetaLine\(.*?^\}", kit, re.S | re.M).group(0)
    item = re.search(r"^function metaItem\(.*?^\}", kit, re.S | re.M).group(0)
    script = f"""
function el(tag) {{ const n = {{ tag, children: [], className: "", textContent: "", attrs: {{}},
  appendChild(c) {{ this.children.push(c); return c; }}, append(...c) {{ this.children.push(...c); }},
  prepend(c) {{ this.children.unshift(c); }},
  setAttribute(k, v) {{ this.attrs[k] = v; }}, get title() {{ return this.attrs.title; }}, set title(v) {{ this.attrs.title = v; }} }};
  return n; }}
const document = {{ createElement: el, createTextNode: (t) => ({{ textContent: t }}) }};
const setLabel = (n, t) => {{ n.textContent = t; }};
const formatTokens = (n) => String(n), msgTime = () => "", humanModelName = (m) => m;
{item}
{body}
const text = (row) => row.children.map((c) => c.textContent || (c.children || []).map((x) => x.textContent).join("")).join("|");
process.stdout.write(JSON.stringify([text(messageMetaLine({{ elapsedMs: 3300, stopped: true }})), text(messageMetaLine({{ elapsedMs: 3300 }}))]));
"""
    stopped, ended = json.loads(subprocess.run(["node", "-e", script], capture_output=True, text=True, check=True).stdout)
    assert stopped.split("|")[0] == "Stopped"
    assert "Stopped" not in ended


def test_a_stopped_turn_is_saved_and_redrawn_stopped():
    js = app_js_text()
    assert re.search(r"elapsed_ms: elapsedMs,(\s*//[^\n]*)?\s*stopped,", js), "the turn payload carries stopped"
    assert "...message, // stats and stopped, as saved" in js, "a reopened chat draws it"


def test_the_saved_reply_keeps_stopped_and_wrote_only_when_true():
    from tessellate.api.routes_conversations import TurnBody, _turn_messages

    kept = _turn_messages(TurnBody(question="q", answer="a", stopped=True, wrote=True))[1]
    assert kept["stopped"] is True and kept["wrote"] is True
    plain = _turn_messages(TurnBody(question="q", answer="a", stopped=False, wrote=False))[1]
    assert "stopped" not in plain and "wrote" not in plain


def test_a_reopened_reply_that_wrote_asks_before_regenerate():
    """The live bubble's `dataset.wrote` was lost on reload, so Regenerate on a
    reopened "note to self" answer re-ran it unasked (w1regen.js: wroteLive
    ["1","",""], wroteReloaded ["","",""], no confirm)."""
    js = app_js_text()
    assert "wrote: bubble.dataset.wrote," in js
    assert 'if (message.wrote) handles.bubble.dataset.wrote = "1";' in js


def test_a_stopped_plain_answer_offers_continue_and_the_guide_says_so():
    """E60: Stop kept the words and offered nothing; a plain stopped answer
    now has a Continue button (a press, never automatic), and the Guide says so."""
    js = app_js_text()
    assert "stopped && (spec.skill || spec.hasTools || spec.cutWords)" in js
    assert "cutWords: Boolean(answerRaw)" in js
    from tessellate.ai.help_chat import HELP_TOPICS

    body = next(t["body"] for t in HELP_TOPICS if t["id"] == "chat-controls")
    assert "stays, with a Continue button" in body
