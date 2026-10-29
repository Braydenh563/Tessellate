"""Audit 1029 X1, X2, X3, X7: a recording is unsaved work, and the voice dialog
does not start it by itself.

Source-reading tests: the recorder needs a microphone, which no test has.
"""
from __future__ import annotations

import re
from pathlib import Path

from tests._app_js import app_js_text

ROOT = Path(__file__).resolve().parents[1]
HTML = (ROOT / "frontend" / "index.html").read_text(encoding="utf-8")


def _fn(js: str, head: str) -> str:
    start = js.index(head)
    nxt = re.search(r"\n(?:async )?function |\n//: \*\*", js[start + len(head):])
    return js[start : start + len(head) + (nxt.start() if nxt else 4000)]


def test_leaving_the_page_while_recording_asks_first():
    js = app_js_text()
    body = js[js.index('window.addEventListener("beforeunload"'):]
    body = body[: body.index("});")]
    assert "recordingLive()" in body
    helper = _fn(js, "function recordingLive")
    assert "meetingRecorder" in helper and "inactive" in helper


def test_pause_and_stop_flush_the_tail():
    js = app_js_text()
    pause = _fn(js, "function toggleMeetingPause")
    assert pause.index(".pause()") < pause.index("requestData()")
    stop = _fn(js, "async function toggleMeetingRecording")
    assert 'state === "paused") meetingRecorder.requestData' not in stop, "stop flushes from any live state"
    assert stop.index("requestData()") < stop.index("meetingRecorder.stop()")


def test_chunks_are_short():
    js = app_js_text()
    ms = int(re.search(r"const MEETING_CHUNK_MS = (\d+);", js).group(1))
    assert ms <= 2000


def test_status_shows_the_real_saved_size_never_a_fixed_claim():
    js = app_js_text()
    assert "Saved as it goes" not in js
    line = _fn(js, "function meetingStatusLine")
    assert "meetingTake.bytes" in line and "Nothing saved yet" in line
    append = _fn(js, "function meetingTakeAppend")
    assert "size_bytes" in append


def test_the_voice_dialog_never_opens_on_record():
    js = app_js_text()
    for head in ("async function openMeetingRecorder", "function showMeetingRecorder"):
        assert '$("meeting-record").focus()' not in _fn(js, head), head
    assert "function meetingFocusFirstField" in js


def test_single_key_chords_are_inert_under_any_modal():
    js = app_js_text()
    block = js[js.index("const overlayOpen ="):]
    block = block[: block.index(";")]
    assert "activeOverlay()" in block and "dialog[open]" in block


def test_buttons_are_labelled_by_outcome():
    js = app_js_text()
    assert "Start and record" not in js
    assert "Start and open recorder" in js
    assert 'Record</button>' not in HTML[HTML.index('id="recordings-record"'):][:300]
    assert "Open recorder" in HTML[HTML.index('id="recordings-record"'):][:300]
    assert 'record.append(mic, " Record")' not in js
