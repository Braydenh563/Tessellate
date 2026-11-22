"""L212 (C12): an Ask turn keeps the notes it cited (and the frame) in its history record, as Chat's
does, so "tell me more about it" after an Ask answer keeps the subject. The server half is pinned by
`test_composer_w9b_1111.py` (B21) and `test_frame_roundtrip_l125.py`."""

import re

from tests._app_js import app_js_text


def test_ask_pushes_objects_and_frame_with_each_turn():
    js = app_js_text()
    pushes = re.findall(r"conversation\.push\(\{ question, answer: answerRaw, objects: chatTurnObjects\(liveSources\)(?:, \.\.\.\(turnFrame[^)]*\))?", js)
    assert pushes, "Ask's turn record lost its objects"
    assert "turnFrame ? { frame: turnFrame }" in js
