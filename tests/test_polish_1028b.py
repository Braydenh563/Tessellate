"""Sweep 1028b small fixes: W16 (a topic name has no trailing blank lines), W25 (the browser log
tag clears 4.5:1: measured 10+ in both themes, with no opacity dimming it)."""

from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def _read(rel: str) -> str:
    return (ROOT / rel).read_text(encoding="utf-8")


def test_a_topic_name_is_saved_without_trailing_blank_lines():
    text = _read("frontend/js/whiteboard-map.js")
    assert 'wbEditedText(this).replace(/\\s+$/, "")' in text


def test_the_browser_log_tag_is_not_dimmed_below_contrast():
    css = _read("frontend/css/06-timeline-dialogs.css")
    block = css.split(".log-source-tag {", 1)[1].split("}", 1)[0]
    assert "opacity" not in block
    assert ".log-source-browser {\n  color: var(--accent-text);" in css


def test_a_failed_unlock_marks_and_describes_the_field_and_refocuses_it():
    text = _read("frontend/js/settings-wiring.js")
    assert 'field.setAttribute("aria-invalid", "true")' in text
    # Described by the error line from the start (in the page, not script: the boot gzip cap).
    assert 'aria-describedby="lock-error"' in _read("frontend/index.html").split('id="lock-password"', 1)[1].split(">", 1)[0]
    assert text.count("lockFail(") >= 3


def test_the_splash_going_away_does_not_take_focus_off_an_open_lock_screen():
    text = _read("frontend/js/phone-shell.js")
    assert '$("lock-overlay").classList.contains("hidden")' in text.split("function tabFromTop", 1)[1][:400]
