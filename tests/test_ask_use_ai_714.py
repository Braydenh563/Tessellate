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


def _controls() -> str:
    start = HTML.index('class="ask-controls"')
    return HTML[start : HTML.index('id="ask-btn"', start)]


def test_the_pill_is_gone_and_one_switch_stands_in_the_input_row():
    # K34 (2026-10-26): a compact pill switch beside the answer-length select,
    # neutral (unchecked, enabled) until the first model status lands.
    header = _ask_header()
    assert "ask-source-seg" not in header and "ask-use-ai" not in header
    controls = _controls()
    match = re.search(r'<label class="checkbox-label ask-ai-switch"[^>]*>(.*?)</label>', controls, re.S)
    assert match, "the control row has no AI switch label"
    inner = match.group(1)
    assert 'type="checkbox"' in inner and 'id="ask-use-ai"' in inner and 'role="switch"' in inner
    assert "disabled" not in inner and "checked" not in inner
    assert "<span>AI</span>" in inner
    assert controls.index('id="ask-use-ai"') < controls.index('id="ask-mode-select"')
    assert header.index("ask-header-actions") < header.index('data-help-for="ask-source-help"')


def test_the_help_popover_names_the_switch_and_says_what_off_means():
    start = HTML.index('id="ask-source-help"')
    popover = HTML[start : HTML.index("</div>", start)]
    assert "switch labelled AI" in popover
    assert "From your notes" in popover
    assert "AI | From your notes" not in popover


def test_the_switch_keeps_the_stored_choice_and_names_the_cause_when_no_model_runs():
    assert 'const ASK_ANSWER_FROM_KEY = "ask-answer-from";' in COMPOSE
    assert 'prefs.set(ASK_ANSWER_FROM_KEY, box.checked ? "ai" : "notes")' in COMPOSE
    assert 'prefs.get(ASK_ANSWER_FROM_KEY) === "notes" ? "notes" : "ai"' in COMPOSE
    assert "box.disabled = off;" in COMPOSE
    # Neutral until the first status: nothing is drawn before it lands.
    assert "if (!modelStatus) return;" in COMPOSE
    # The three causes, each from the status, the first with the server's URL.
    assert "is not answering" in COMPOSE and "s.base_url" in COMPOSE
    assert "has no models pulled" in COMPOSE
    assert 'is not installed' in COMPOSE and "s.chat_model" in COMPOSE
    assert "data-answer-from" not in COMPOSE


def test_the_switch_wears_the_pill_switch_recipe_and_the_chip_rules_are_gone():
    forms = _css("01-forms-settings.css")
    #: The switch's own rules are lazy with ask-compose.js (boot CSS cap).
    assert "#ask-use-ai" not in forms and ".ask-ai-switch {" in _css("ask-compose-lazy.css")
    assert ".ask-use-ai" not in _css("06-timeline-dialogs.css")
    assert "#ask-use-ai" not in _css("10-responsive.css")
    assert ".ask-source-seg" not in _css("10-responsive.css")


def test_every_help_surface_names_the_switch():
    source = Path(help_topics_more.__file__).read_text(encoding="utf-8")
    chat = Path(help_chat.__file__).read_text(encoding="utf-8")
    assert "Ask on the Notes tab has an AI switch beside its answer-length picker" in source
    assert "Notes tab, Ask, the AI switch" in source
    assert "Turn the AI switch off beside the answer length." in source
    assert "Its AI switch " in chat
    for text in (source, chat):
        assert "AI and From your notes switch" not in text
        assert "AI, or From your notes" not in text
        assert "Use AI button" not in text


def test_the_switch_is_drawn_from_the_first_status_not_the_preload():
    # The owner, 2026-10-19: the switch was off in fact but drawn on until it
    # was clicked. The markup's "checked" stands only until ask-compose.js
    # loads, and that was a 3 s timer after boot; the status poll now loads it.
    status = (ROOT / "frontend" / "js" / "status.js").read_text(encoding="utf-8")
    assert 'ensureModule("askCompose");' in status
    assert status.index('"No model connected. Ask shows the matching records below."') < status.index(
        'ensureModule("askCompose");'
    )
