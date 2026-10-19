"""The Ask header's "Use AI" switch (INBOX 714, part 2).

The owner, 2026-10-06, of the "AI | From your notes" segmented pill beside the
Ask title: "that ai/from your notes toggle looks out of place and i dont like
it, it doesnt feel modern and professional". Decision, taken: one compact
switch row labelled "Use AI" in the header's control group, built from the
app's pill-switch recipe (06-timeline-dialogs.css), on meaning an AI-composed
answer and off meaning From your notes. Only the control changed: the stored
choice (`ask-answer-from`, "ai" or "notes") and what the request carries are
the same, so INBOX 688's server tests stand.

These are the source halves; the heights and the centre line are the sweep's
(scratchpad/ui-sweeps/askuseai714.js).
"""

from __future__ import annotations

import re
from pathlib import Path

from tessellate.ai import help_chat, help_topics_more
from tests._css_paths import CSS_DIR

ROOT = Path(__file__).resolve().parents[1]
HTML = (ROOT / "frontend" / "index.html").read_text(encoding="utf-8")
COMPOSE = (ROOT / "frontend" / "js" / "ask-compose.js").read_text(encoding="utf-8")


def _css(name: str) -> str:
    return (CSS_DIR / name).read_text(encoding="utf-8")


def _ask_header() -> str:
    start = HTML.index('<section class="card" id="ask">')
    return HTML[start : HTML.index('id="ask-source-help"', start)]


def test_the_pill_is_gone_and_one_switch_row_stands_in_its_place():
    header = _ask_header()
    assert "ask-source-seg" not in header
    assert "data-answer-from" not in header
    assert "From your notes</button>" not in header
    match = re.search(r'<label class="ask-use-ai"[^>]*>(.*?)</label>', header, re.S)
    assert match, "the header has no label.ask-use-ai"
    inner = match.group(1)
    assert 'type="checkbox"' in inner and 'id="ask-use-ai"' in inner
    assert "<span>Use AI</span>" in inner
    # In the right-hand control group, ahead of its '?' popover trigger.
    assert header.index("ask-header-actions") < header.index('class="ask-use-ai"')
    assert header.index('class="ask-use-ai"') < header.index('data-help-for="ask-source-help"')


def test_the_help_popover_names_the_switch_and_says_what_off_means():
    start = HTML.index('id="ask-source-help"')
    popover = HTML[start : HTML.index("</div>", start)]
    assert "Use AI" in popover
    assert "From your notes" in popover
    assert "AI | From your notes" not in popover


def test_the_switch_keeps_the_stored_choice_and_gives_the_reason_when_no_model_runs():
    assert 'const ASK_ANSWER_FROM_KEY = "ask-answer-from";' in COMPOSE
    assert 'prefs.set(ASK_ANSWER_FROM_KEY, box.checked ? "ai" : "notes")' in COMPOSE
    assert 'prefs.get(ASK_ANSWER_FROM_KEY) === "notes" ? "notes" : "ai"' in COMPOSE
    assert "box.disabled = off;" in COMPOSE
    assert "ASK_AI_OFF_REASON" in COMPOSE
    assert "data-answer-from" not in COMPOSE


def test_the_switch_is_in_every_list_of_the_pill_switch_recipe():
    css = _css("06-timeline-dialogs.css")
    for state in ("", "::after", ":hover", ":checked", ":checked::after", ":disabled"):
        assert f'.ask-use-ai input[type="checkbox"]{state}' in css, state


def test_the_row_is_a_control_high_row_on_the_header_line():
    css = _css("01-forms-settings.css")
    rule = re.search(r"\n\.ask-use-ai \{([^}]*)\}", css)
    assert rule, "no .ask-use-ai rule"
    assert "min-height: max(var(--control-h), var(--target-min))" in rule.group(1)
    assert "align-items: center" in rule.group(1)
    assert ".ask-source-seg" not in _css("10-responsive.css")


def test_every_help_surface_names_the_switch():
    source = Path(help_topics_more.__file__).read_text(encoding="utf-8")
    chat = Path(help_chat.__file__).read_text(encoding="utf-8")
    assert "Ask on the Notes tab has a Use AI switch" in source
    assert "Notes tab, Ask, the Use AI switch" in source
    assert "Turn Use AI off beside the title." in source
    assert "Its Use AI switch " in chat
    for text in (source, chat):
        assert "AI and From your notes switch" not in text
        assert "AI, or From your notes" not in text


def test_the_switch_is_drawn_from_the_first_status_not_the_preload():
    # The owner, 2026-10-19: the switch was off in fact but drawn on until it
    # was clicked. The markup's "checked" stands only until ask-compose.js
    # loads, and that was a 3 s timer after boot; the status poll now loads it.
    status = (ROOT / "frontend" / "js" / "status.js").read_text(encoding="utf-8")
    assert 'ensureModule("askCompose");' in status
    assert status.index('"No model connected. Ask shows the matching records below."') < status.index(
        'ensureModule("askCompose");'
    )
