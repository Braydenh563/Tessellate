"""The reminder chime's AudioContext is not built inside the first gesture.

Performance pass, 2026-10-03 (INBOX 441, item 6). `new AudioContext()` opens the
audio device synchronously, and as the session's first pointerdown it was the
longest script on the lock screen: 44 to 56 ms of the unlock click's handlers,
measured with an event-timing observer (`scratchpad/ui-sweeps` boot, headless
Chromium). It is built when the browser is idle just after the gesture; the
listeners stay on until the context is running so a browser that wants the
gesture itself can still resume it.

The suite cannot see a browser, so this pins the shape of the source: the
constructor sits in a deferred callback, and the listeners are not `once`.
"""

from __future__ import annotations

import re

from tests._app_js import JS_DIR


def _prime_function() -> str:
    text = (JS_DIR / "status.js").read_text(encoding="utf-8")
    start = text.index("function primeReminderAudio()")
    return text[start : text.index("\nfunction playReminderChime", start)]


def test_the_context_is_built_in_a_deferred_callback_not_in_the_gesture():
    body = _prime_function()
    constructor = body.index("new (window.AudioContext")
    before = body[:constructor]
    assert "const build = () =>" in before, "the constructor must sit inside a deferred `build`"
    assert "requestIdleCallback" in body and "setTimeout(build" in body


def test_the_gesture_listeners_stay_on_until_the_context_is_running():
    text = (JS_DIR / "status.js").read_text(encoding="utf-8")
    listeners = re.findall(r'document\.addEventListener\("(?:pointerdown|keydown)", primeReminderAudio, (\{[^}]*\})', text)
    assert len(listeners) == 2
    assert all("once" not in options for options in listeners), listeners
    assert 'removeEventListener("pointerdown", primeReminderAudio)' in text


# INBOX 1446 (the owner's lag log, 2026-10-29): "frame 571ms on dashboard:
# status.js build 557ms" and "input 536ms on dashboard: keydown on
# input#lock-password". The context was built after the first gesture of every
# session, a main-thread block of 557ms where the audio device opens, whether
# or not a reminder was anywhere near. It is built now only when a reminder is
# due within five minutes (3e5), or when a chime is wanted and there is
# none (the chime then plays once it exists).


def _status() -> str:
    return (JS_DIR / "status.js").read_text(encoding="utf-8")


def test_the_context_is_built_only_when_a_reminder_is_near():
    text = _status()
    body = _prime_function()
    gate = body.index("reminderAudio.nextAt - Date.now() > 3e5")
    assert gate < body.index("reminderAudio.building = true;")
    arm = text[text.index("function armReminderTimer(") :]
    arm = arm[: arm.index("\n}\n")]
    assert arm.index("reminderAudio.nextAt =") < arm.index("if (!Number.isFinite(next)) return;")


def test_a_chime_with_no_context_builds_one_and_plays_when_it_exists():
    text = _status()
    play = text[text.index("function playReminderChime()") :]
    play = play[: play.index("\n}\n")]
    assert "reminderAudio.after = playReminderChime" in play and "primeReminderAudio()" in play
    body = _prime_function()
    # No context to show for it (no Web Audio): the wish is dropped, not retried forever.
    assert "reminderAudio.after = null" in body
