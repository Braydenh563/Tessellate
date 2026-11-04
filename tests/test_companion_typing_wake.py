"""Typing in a document does not wake the companion's rig on every key (audit 1102 DX1).

Measured at 4x CPU in a 3,120-line document (60 keys at 60 ms): with the corner
companion on the page the typing made 57 long tasks (4.8 s); with it removed,
13 (0.95 s). Cause: the companion's keydown handler called
`classList.add("nmb-watch")` on every key, and `add` of a token already there
still rewrites the attribute, so the MutationObserver on the rig saw a class
change per key (84 wakes in 3.5 s), and each wake sets the rig dirty, so its
next frame reads `getComputedStyle` and pays a style pass over the editor's
fresh DOM. Two guards: the handler touches the class list only on a change,
and the rig's observer ignores a class record that left the value as it was.
"""

from __future__ import annotations

import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
JS = ROOT / "frontend" / "js"
AVATARS = (JS / "avatars.js").read_text(encoding="utf-8")
MOTION = (JS / "atlas-motion.js").read_text(encoding="utf-8")


def _typing_handler() -> str:
    start = AVATARS.index("Typing near it: it watches the field")
    end = AVATARS.index("}, { passive: true, capture: true });", start)
    return AVATARS[start:end]


def test_keydown_adds_watch_only_when_absent():
    body = _typing_handler()
    assert not re.search(r'^\s*buddy\.classList\.add\("nmb-watch"\);', body, re.M), "an unconditional add rewrites the class on every key"
    assert 'contains("nmb-watch")' in body


def test_keydown_toggles_nod_only_on_change():
    body = _typing_handler()
    assert not re.search(r'buddy\.classList\.toggle\("nmb-nod", nmb\.keyRun >= 5\);', body)
    assert 'contains("nmb-nod")' in body


def test_rig_observer_skips_a_class_record_that_changed_nothing():
    start = MOTION.index("rig.observer = new MutationObserver(")
    chunk = MOTION[start : start + 900]
    assert "attributeOldValue: true" in chunk
    assert "oldValue" in chunk and 'attributeName !== "class"' in chunk
