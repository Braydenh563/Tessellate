"""The Ask answer's head shows what was pressed (INBOX 1423), and a lone Alt is
not handed to the window (INBOX 1422).

Source-reading tests, the repo's style: the behaviour was measured in the
running app (scratchpad sweep named in the INBOX result lines).
"""

from __future__ import annotations

import re
from pathlib import Path

from _app_js import app_js_text

ROOT = Path(__file__).resolve().parents[1]
CSS = (ROOT / "frontend/css/ask-compose-lazy.css").read_text(encoding="utf-8")


def _body(js: str, name: str) -> str:
    start = js.index(f"function {name}(")
    return js[start : js.index("\n}\n", start)]


def test_copy_in_the_head_swaps_to_a_tick_and_back() -> None:
    js = app_js_text()
    assert '$("copy-btn"))' in _body(js, "copyAnswer")
    flash = _body(js, "flashCopied")
    assert 'setLabel(button, "ph:check")' in flash and "1200" in flash
    assert "is-done" in flash and "_copiedWas" in flash  # a second press keeps the real icon


def test_read_aloud_shows_stop_and_aria_pressed_while_speaking() -> None:
    js = app_js_text()
    speak = _body(js, "speakText")
    assert "aria-pressed" in speak and '"ph:stop"' in speak
    assert 'speechSynthesis.cancel()' in speak  # a second press still stops it
    assert re.search(r'speak-btn"\)\.addEventListener\("click", \(e\) => speakText\(.*e\.currentTarget', js)


def test_regenerate_stays_visible_and_busy_while_it_runs() -> None:
    js = app_js_text()
    ask = _body(js, "askQuestion")
    assert 'hide("retry-btn"' not in ask
    assert 'setBusy(retryBtn, true, "")' in ask and 'setBusy($("retry-btn"), false)' in ask


def test_the_head_buttons_have_a_pressed_ground_from_tokens() -> None:
    rule = re.search(r"\.answer-actions \.ghost:is\(([^)]*)\)[^{]*\{([^}]*)\}", CSS)
    assert rule, "no pressed rule for the answer head's buttons"
    assert ":active" in rule.group(1) and 'aria-pressed="true"' in rule.group(1)
    assert "var(--accent-soft)" in rule.group(2)
    assert ".is-done" in rule.group(1) and "[aria-expanded" in rule.group(1)


def test_a_lone_alt_release_is_cancelled_and_a_modifier_use_is_not() -> None:
    js = (ROOT / "frontend/js/lazy-entries.js").read_text(encoding="utf-8")
    assert 'e.key === "Alt" && altAlone) e.preventDefault()' in js
    # Any other key between press and release clears it, as does the window losing focus.
    assert 'altAlone = e.key === "Alt"' in js
    assert 'addEventListener("blur", () => { altAlone = false; })' in js
