"""The Ask header's "Use AI" control (INBOX 714, part 2; a chip since K6).

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


def test_the_pill_is_gone_and_one_chip_stands_in_its_place():
    # K6 (2026-10-26): the bare switch drew as on with no model; the Chat
    # dock's toggle chip (`#web-search-toggle`) replaced it.
    header = _ask_header()
    assert "ask-source-seg" not in header
    assert "data-answer-from" not in header
    assert "From your notes</button>" not in header
    assert 'type="checkbox"' not in header[header.index("ask-header-actions") :]
    match = re.search(r'<button type="button" id="ask-use-ai"([^>]*)>(.*?)</button>', header, re.S)
    assert match, "the header has no button#ask-use-ai"
    attrs, inner = match.groups()
    # Drawn from the provider status: unpressed and disabled until it answers.
    assert 'aria-pressed="false"' in attrs and " disabled" in attrs
    assert "Use AI" in inner and "ph-sparkle" in inner
    assert header.index("ask-header-actions") < header.index('id="ask-use-ai"')
    assert header.index('id="ask-use-ai"') < header.index('data-help-for="ask-source-help"')


def test_the_help_popover_names_the_switch_and_says_what_off_means():
    start = HTML.index('id="ask-source-help"')
    popover = HTML[start : HTML.index("</div>", start)]
    assert "Use AI" in popover
    assert "From your notes" in popover
    assert "AI | From your notes" not in popover


def test_the_chip_keeps_the_stored_choice_and_gives_the_reason_when_no_model_runs():
    assert 'const ASK_ANSWER_FROM_KEY = "ask-answer-from";' in COMPOSE
    assert 'prefs.set(ASK_ANSWER_FROM_KEY, askAnswerFrom() === "ai" ? "notes" : "ai")' in COMPOSE
    assert 'prefs.get(ASK_ANSWER_FROM_KEY) === "notes" ? "notes" : "ai"' in COMPOSE
    assert "chip.disabled = off;" in COMPOSE
    assert 'chip.setAttribute("aria-pressed"' in COMPOSE and 'classList.toggle("active", on)' in COMPOSE
    assert "ASK_AI_OFF_REASON" in COMPOSE
    assert "data-answer-from" not in COMPOSE


def test_the_chip_wears_the_chat_toggles_on_state_and_the_old_switch_recipe_is_gone():
    forms = _css("01-forms-settings.css")
    assert "#ask-use-ai.active," in forms and "#ask-use-ai.active i," in forms
    assert "#ask-use-ai:not(.active)" in forms
    assert ".ask-use-ai" not in _css("06-timeline-dialogs.css")
    assert "min-height: max(var(--control-h), var(--target-min))" in forms[forms.index("#ask-use-ai {") :][:200]
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
