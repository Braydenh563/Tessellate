"""L692 (INBOX B55): the web clipper is easy to learn, to reach and to read.

"Idk how to use the web clipper, it is unintuitive to use and hidden in
settings". Settings, Import & export says it in three numbered steps, the Web
panel's menu and the command palette open it, a Try it button shows the clip
window without leaving the app, and the window shows an excerpt of what it
will keep, in a size that works at 360 px.
"""

from __future__ import annotations

import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def _text(*parts: str) -> str:
    return (ROOT.joinpath(*parts)).read_text(encoding="utf-8")


def test_settings_says_how_in_three_numbered_steps():
    html = _text("frontend", "index.html")
    box = html.split('id="web-clip-box"', 1)[1].split("</details>", 1)[0]
    steps = re.search(r'<ol class="web-clip-steps">(.*?)</ol>', box, re.S)
    assert steps and steps.group(1).count("<li>") == 3
    assert 'id="web-clip-try"' in box


def test_the_window_has_a_preview_excerpt_and_never_calls_missing_helpers():
    html = _text("frontend", "clip.html")
    js = _text("frontend", "js", "clip.js")
    assert 'id="clip-excerpt"' in html and 'id="clip-count"' in html
    # clip.html loads no app scripts, so the app's wordCount and nounCount do
    # not exist there: calling them stopped the preview from ever drawing.
    assert "function wordCount(" in js and "function nounCount(" in js
    assert "DOMParser" in js


def test_the_window_reads_the_page_inertly():
    js = _text("frontend", "js", "clip.js")
    assert "parseFromString(" in js and "innerHTML" not in js


def test_the_try_button_opens_the_window_on_a_sample_and_the_menu_and_palette_reach_it():
    web = _text("frontend", "js", "web-clip.js")
    assert 'getElementById("web-clip-try")' in web or '$("web-clip-try")' in web
    chat = _text("frontend", "js", "web-results.js")
    assert 'openSettingsModal("data", "web-clip-box")' in chat
    assert "Clip a page from your browser" in chat
    assert 'openSettingsModal("data", "web-clip-box")' in _text("frontend", "js", "app-palette.js")


def test_copy_is_plain():
    for rel in (("frontend", "clip.html"), ("frontend", "js", "clip.js")):
        text = _text(*rel)
        assert "\u2014" not in text
        for literal in re.findall(r'"([^"\n]*)"', text):
            assert "!" not in literal, literal


def test_help_names_the_steps_and_the_try_button():
    from tessellate.ai import help_topics_more as h

    body = next(t["body"] for t in h.MORE_TOPICS if t["id"] == "web-clipper-bookmark")
    assert "Try it" in body and "Web panel" in body
