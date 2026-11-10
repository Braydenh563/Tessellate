"""Rotating "thinking words" beside the 3-dot indicator (chat.js, sheets-
selects.js): the frontend half of the backend's `PersonaItem.thinking_words`
(tests/test_thinking_words.py). The suite cannot open a browser, so these
hold the DOM-shaped facts as text; `scratchpad/ui-sweeps/thinkingwords.js`
measures the rendered rotation, row width and console cleanliness.
"""

from __future__ import annotations

import re
from pathlib import Path

from tests._app_js import app_js_text, with_pieces

ROOT = Path(__file__).resolve().parents[1]
APP = app_js_text()
SHEETS = with_pieces("sheets-selects.js")
CSS = (ROOT / "frontend" / "css" / "01-forms-settings.css").read_text(encoding="utf-8")
SETTINGS_JS = with_pieces("settings.js")
INDEX_HTML = (ROOT / "frontend" / "index.html").read_text(encoding="utf-8")


def _function(source: str, name: str) -> str:
    start = source.index(f"function {name}(")
    rest = source[start + len(f"function {name}(") :]
    end = re.search(r"\n(?:async )?function \w+\(", rest)
    return source[start : start + len(f"function {name}(") + (end.start() if end else len(rest))]


# --- the word lists and the resolver (sheets-selects.js) --------------------


def test_the_four_word_lists_exist_with_sixteen_items_each() -> None:
    for name in (
        "DEFAULT_THINKING_WORDS",
        "ATLAS_THINKING_WORDS",
        "COACH_THINKING_WORDS",
        "ANALYST_THINKING_WORDS",
    ):
        match = re.search(rf"const {name} = \[(.*?)\];", SHEETS, re.S)
        assert match, f"{name} is missing"
        items = re.findall(r'"([^"]*)"', match.group(1))
        assert len(items) == 16, f"{name} has {len(items)} items, expected 16"
        for word in items:
            assert len(word) <= 40, f"{name}: {word!r} is over 40 characters"
            assert "!" not in word
            assert chr(0x2014) not in word
            assert word[0].isupper() or not word[0].isalpha()


def test_default_list_matches_the_coordinators_spec_exactly() -> None:
    match = re.search(r"const DEFAULT_THINKING_WORDS = \[(.*?)\];", SHEETS, re.S)
    items = re.findall(r'"([^"]*)"', match.group(1))
    assert items == [
        "Thinking", "Pondering", "Leafing through your notes", "Connecting the dots",
        "Following a thread", "Mulling it over", "Cross-referencing", "Gathering thoughts",
        "Tracing the links", "Sifting", "Weighing it up", "Piecing it together",
        "Reading between the lines", "Consulting the margins", "Untangling", "Distilling",
    ]


def test_atlas_list_matches_the_coordinators_spec_exactly() -> None:
    match = re.search(r"const ATLAS_THINKING_WORDS = \[(.*?)\];", SHEETS, re.S)
    items = re.findall(r'"([^"]*)"', match.group(1))
    assert items == [
        "Stargazing", "Charting constellations", "Consulting the stars", "Drifting through the nebula",
        "Orbiting the question", "Tracing starlight", "Aligning the planets", "Catching a comet",
        "Listening between the stars", "Counting moons", "Weaving stardust", "Following a meteor",
        "Spinning up a galaxy", "Reading the night sky", "Gathering starlight", "Mapping your cosmos",
    ]


def test_thinking_words_for_prefers_a_custom_override() -> None:
    body = _function(SHEETS, "thinkingWordsFor")
    assert "custom.thinking_words" in body
    assert "builtinThinkingWords" in body
    assert "DEFAULT_THINKING_WORDS" in body


def test_builtin_thinking_words_keys_atlas_by_the_ai_name_not_a_literal() -> None:
    """The app's own persona's key is whatever the AI is named (the same
    test builtinPersonas() itself needs, test_persona_atlas.py), and Atlas's
    own list applies only while that name really is Atlas."""
    body = _function(SHEETS, "builtinThinkingWords")
    assert "aiNameNow()" in body
    assert '=== "Atlas"' in body
    assert "Coach: COACH_THINKING_WORDS" in body
    assert "Analyst: ANALYST_THINKING_WORDS" in body


def test_wants_thinking_words_defaults_true_and_never_touches_the_server() -> None:
    """Stored the way its nearest sibling control, `progress-motion`, is: a
    per-browser `localStorage` setting, never a `/preferences` field."""
    body = _function(SHEETS, "wantsThinkingWords")
    assert 'prefs.get("show-thinking-words", null)' in body
    assert '!== "off"' in body, "missing/unset must read as on"
    assert "prefsCache" not in body


# --- typingDots itself (chat.js) --------------------------------------------


def _typing_dots_body() -> str:
    start = APP.index("function typingDots(")
    return APP[start : APP.index("\n// **A working signal", start)]


def test_typing_dots_takes_persona_and_words_options_defaulted_off() -> None:
    body = _typing_dots_body()
    assert 'function typingDots(label = null, { persona = null, words = false } = {})' in body


def test_the_rotation_only_starts_in_the_enhanced_motion_branch() -> None:
    body = _typing_dots_body()
    enhanced = body[body.index("if (progressMotionWanted())") : body.index("return dots;\n  }")]
    assert "startThinkingWordRotation" in enhanced
    #: The reduced-motion branch (after the first `return dots;`) must not
    #: also start it: reduced motion already gets its own single word from
    #: the existing `.typing-word`, never a rotating one.
    reduced = body[body.index("return dots;\n  }") :]
    assert "startThinkingWordRotation" not in reduced


def test_rotation_is_gated_by_the_settings_toggle() -> None:
    body = _typing_dots_body()
    #: Unguarded since Brief 86 dropped the redundant typeof guards on eager-file functions.
    assert "words && wantsThinkingWords()" in body and "typeof wantsThinkingWords" not in body
    assert "wantsThinkingWords()" in body


def test_writing_phase_stops_the_rotation() -> None:
    body = _typing_dots_body()
    set_phase = body[body.index("dots.setPhase = (phase) => {") :]
    set_phase = set_phase[: set_phase.index("};") + 2]
    assert "stopThinkingWordRotation(dots)" in set_phase


def test_the_word_is_aria_hidden_the_row_keeps_its_own_label() -> None:
    body = _function(APP, "startThinkingWordRotation")
    assert 'wordEl.setAttribute("aria-hidden", "true")' in body


def test_the_word_reserves_no_width() -> None:
    """Reserving the longest phrase's width pushed the status and tips far
    right (the owner at release); the word sizes to itself."""
    caller = _function(APP, "startThinkingWordRotation")
    assert "style.minWidth" not in caller
    assert "thinkingWordMinWidth" not in APP


def test_the_tick_checks_phase_and_connectedness_before_rotating() -> None:
    """Stop on phase "writing" or when removed: `scheduleThinkingWordTick`
    is the one place both are checked, before it ever touches the word."""
    body = _function(APP, "scheduleThinkingWordTick")
    assert 'dots.dataset.phase === "writing"' in body
    assert "dots.isConnected" in body
    assert "THINKING_WORD_GRACE_TICKS" in body, "a re-parented node must get a few rechecks, not stop instantly"


def test_the_tick_delay_is_jittered_within_spec() -> None:
    assert "const THINKING_WORD_MIN_MS = 3750;" in APP
    assert "const THINKING_WORD_JITTER_MS = 1500;" in APP


def test_the_crossfade_reuses_the_progress_musings_own_technique() -> None:
    """`classList.remove` + a forced reflow + `classList.add`, the same
    three lines `progressLine`'s `showMusing` uses and explains why: a text
    swap between two frames reads as a glitch without it."""
    body = _function(APP, "scheduleThinkingWordTick")
    assert 'wordEl.classList.remove("is-shown")' in body
    assert "void wordEl.offsetWidth" in body
    assert 'wordEl.classList.add("is-shown")' in body


# --- the three wired call sites ---------------------------------------------


def test_chat_passes_the_persona_that_was_actually_sent() -> None:
    text = with_pieces("chat-attach.js")
    assert 'progressLine(null, { persona: sentPersona, words: true })' in text


def test_capture_ask_opts_in_with_no_persona_picker_of_its_own() -> None:
    text = with_pieces("capture-ask.js")
    assert "progressLine(text, { words: true })" in text


def test_the_popup_agent_passes_the_persona_it_asked_with() -> None:
    text = (ROOT / "frontend" / "js" / "palette.js").read_text(encoding="utf-8")
    assert 'progressLine(null, { persona: askedPersona, words: true })' in text


# --- CSS ---------------------------------------------------------------------


def test_the_word_has_a_crossfade_and_a_2px_rise() -> None:
    match = re.search(r"\.typing-thinking-word\s*\{([^}]*)\}", CSS)
    assert match, ".typing-thinking-word is missing"
    rule = match.group(1)
    assert "opacity: 0;" in rule
    assert "translateY(2px);" in rule
    assert "transition:" in rule


# --- the Settings toggle ----------------------------------------------------


def test_the_settings_checkbox_exists_and_defaults_checked() -> None:
    match = re.search(r'<input type="checkbox" id="pref-show-thinking-words"[^>]*>', INDEX_HTML)
    assert match, "the Settings checkbox is missing"
    assert "checked" in match.group(0)


def test_the_checkbox_renders_from_and_saves_to_local_storage_not_the_server() -> None:
    assert '$("pref-show-thinking-words").checked = appearancePref("show-thinking-words") !== "off";' in SETTINGS_JS
    change = SETTINGS_JS[SETTINGS_JS.index('$("pref-show-thinking-words")?.addEventListener("change"') :]
    change = change[: change.index("});") + 3]
    assert 'prefs.set("show-thinking-words"' in change
    assert "apiJson" not in change, "this is a localStorage setting, not a /preferences field"


def test_it_sits_beside_progress_motion_which_governs_the_same_indicator() -> None:
    idx = INDEX_HTML.index('id="progress-motion-row"')
    nearby = INDEX_HTML[idx : idx + 2500]
    assert 'id="pref-show-thinking-words"' in nearby


# --- the persona editor's own field -----------------------------------------


def test_the_persona_rows_carry_thinking_words_pre_filled_from_the_builtin() -> None:
    body = _function(SHEETS, "renderPersonas")
    assert "thinkingWords" in body
    assert "builtinThinkingWords()[name] || DEFAULT_THINKING_WORDS" in body


def test_the_editor_has_a_textarea_a_suggest_button_and_client_side_validation() -> None:
    body = _function(SHEETS, "renderPersonas")
    assert '"persona-words-box"' in body
    assert '"Suggest with AI"' in body
    assert "/personas/suggest-thinking-words" in body
    #: The same three rules the backend enforces (PersonaItem, routes_settings.py),
    #: checked here too so a mistake reads as one sentence beside the box
    #: rather than a raw 422 after Save has already closed the editor.
    assert "thinkingWords.length < 8 || thinkingWords.length > 40" in body
    assert 'w.length > 40' in body
    assert 'w.includes("!")' in body
    assert "String.fromCharCode(8212)" in body


def test_save_sends_thinking_words_as_a_plain_array() -> None:
    body = _function(SHEETS, "renderPersonas")
    assert "thinking_words: thinkingWords" in body


def test_a_save_failure_is_shown_not_swallowed() -> None:
    """`savePersonaList` throws on a validation error the client check
    missed; before this it was an unhandled rejection (a console error, no
    UI at all) rather than something the person editing the persona could
    see and fix."""
    # The closure's indent removed: personas-pane.js is wrapped in one closure (audit row 37a), which added two spaces to every line
    # and pushed the catch past the 2600-character window; the window measures the handler, not its indent.
    body = re.sub(r"^  ", "", _function(SHEETS, "renderPersonas"), flags=re.M)
    save_at = body.index('"Save"')
    save_block = body[save_at : save_at + 2600]
    assert "try {" in save_block
    assert "await savePersonaList(updated);" in save_block
    assert "catch (error)" in save_block
    assert "wordsStatus.textContent = error.message" in save_block


def test_reduced_motion_re_declares_rather_than_removes_the_transition() -> None:
    """Same reasoning as the reduced-motion `.typing-word`: this element only
    exists when "always" deliberately overrode the OS setting, so turning
    the transition off here would be the bug the stepped-word fix closed,
    back."""
    idx = CSS.index(".typing-thinking-word")
    reduced = CSS[idx : idx + 1200]
    assert ':where(:root[data-motion="reduced"]) .typing-thinking-word' in reduced
    assert reduced.count("transition:") >= 2
