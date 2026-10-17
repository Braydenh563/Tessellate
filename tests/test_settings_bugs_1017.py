"""The owner's 2026-10-17 settings bugs (INBOX 904), one test per bug.

Source-level, in the style of the neighbouring `test_settings_*.py`: the suite
cannot see the DOM, so each test pins the cause the browser measurement found.
The measurement itself is named in the comment above each test.
"""

from __future__ import annotations

import re
from pathlib import Path

from tests._css_paths import CSS_FILES

ROOT = Path(__file__).resolve().parents[1]


def _css() -> str:
    text = "\n".join(p.read_text(encoding="utf-8") for p in CSS_FILES)
    return re.sub(r"/\*.*?\*/", "", text, flags=re.S)


def _rules(css: str):
    for match in re.finditer(r"([^{}]+)\{([^{}]*)\}", css):
        yield [s.strip() for s in match.group(1).split(",")], match.group(2)


# B60: Settings, Packages, the OCR row. `.settings-section label` sets
# `align-items: flex-start` for a wrapped caption; the language picker is a
# <label> too, so its "Reads in" caption sat 7px above the select's centre
# line (label centre y 2186, select centre y 2193 at 1440).
def test_b60_ocr_language_picker_centres_its_caption_in_settings():
    hits = [
        body
        for selectors, body in _rules(_css())
        if any(
            ".settings-section" in s and "ocr-engine-lang-wrap" in s and ":" not in s
            for s in selectors
        )
    ]
    assert hits, "no .settings-section .ocr-engine-lang-wrap rule"
    assert any("align-items: center" in body for body in hits)


def _fn(js_name: str, name: str) -> str:
    text = (ROOT / "frontend" / "js" / js_name).read_text(encoding="utf-8")
    start = text.index(f"function {name}(")
    end = text.index("\n}\n", start)
    return text[start:end]


# B65: with the backend up and no model chosen (0 options) or nothing in
# memory, "Use this model" and "Stop the model" were both enabled (probe:
# MODE=empty, apply.disabled false with 0 options; stop.disabled false with
# loaded null).
def test_b65_chat_model_buttons_follow_what_there_is_to_act_on():
    body = _fn("ai-tools.js", "renderChatModelPicker")
    assert re.search(r'chat-model-apply"\)\.disabled\s*=', body), "Use this model is never disabled"
    assert re.search(r'\bstop\.disabled\s*=', body) and '"chat-model-stop"' in body, "Stop the model is never disabled"


# B56: Settings, Appearance, every "Auto" showed only the word. The closed face
# must say what Auto resolved to (probe p/b56.js: density-seg shown "Auto" at
# 900px and at 600px tall).
def test_b56_every_auto_choice_says_what_it_resolved_to():
    text = (ROOT / "frontend" / "js" / "settings.js").read_text(encoding="utf-8")
    # In the lazy settings-controls.js: the boot budget has no room for it.
    body = _fn("settings-controls.js", "renderAutoChoices")
    for select in ("density-seg", "perf-mode", "progress-motion", "bg-motion", "atlas-look"):
        assert f'"{select}"' in body, select
    # drawn with the rest of Appearance, and again when the window is resized
    # settings-controls.js registers it in `settingsReadouts` (status.js) when it loads, so a boot file
    # needs no `typeof` guard on a function that may not exist yet.
    assert "settingsReadouts.auto?.()" in text.split("function renderAppearance", 1)[1]
    assert "settingsReadouts.auto?.()" in text.split("DENSITY_SHORT.addEventListener", 1)[1][:400]
    controls = (ROOT / "frontend" / "js" / "settings-controls.js").read_text(encoding="utf-8")
    assert "settingsReadouts.auto = renderAutoChoices;" in controls


def test_b56_status_says_whether_the_chat_model_reads_as_small(client):
    body = client.get("/models/status").json()
    assert "chat_model_small" in body


def _run_node(script: str) -> str:
    import shutil
    import subprocess

    import pytest

    node = shutil.which("node")
    if node is None:
        pytest.skip("node is not installed")
    done = subprocess.run([node, "-e", script], capture_output=True, text=True, timeout=60, check=True)
    return done.stdout.strip()


def _js_function(path: str, name: str) -> str:
    src = (ROOT / "frontend" / "js" / path).read_text(encoding="utf-8")
    start = src.index(f"function {name}(")
    if src[max(0, start - 6) : start] == "async ":
        start -= 6
    return src[start : src.index("\n}\n", start) + 3]


# B63: the dashboard hero's logo (#dash-hero-emblem) is not an EMBLEM_SLOTS
# slot, so a theme or colour change left its gradient on the old colours until
# a reload (probe p/b63.js: after applyAccent('crimson') the span's gradient
# stayed rgb(91, 124, 255)/rgb(79, 109, 245)/rgb(169, 39, 216)).
def test_b63_recolouring_the_brand_logo_redraws_the_dashboard_hero_mark():
    body = _js_function("phone-shell.js", "renderBrandLogo")
    assert "paintDashEmblem()" in body


# B57: pick an accent, then "Default": the app wore #4664f0 (the swatch's
# fallback hex) as an inline --accent instead of the palette's own (#2f5bd3 on
# the sandbox's palette, probe p/b57.js). "indigo" is the stored name of
# "Default", which means no accent at all, so nothing may be set inline.
def test_b57_default_accent_sets_no_inline_colour():
    import json

    src = (ROOT / "frontend" / "js" / "settings.js").read_text(encoding="utf-8")
    accents = src[src.index("const ACCENTS = [") : src.index("];", src.index("const ACCENTS = [")) + 2]
    script = (
        accents
        + "\nconst store = { accent: 'indigo' };"
        + "\nconst prefs = { get: (k, d) => (k in store ? store[k] : d) };"
        + "\nconst calls = [];"
        + "\nfunction applyCustomAccent(hex) { calls.push(hex); }"
        + "\nconst document = { documentElement: { dataset: {} } };\n"
        + _js_function("settings.js", "applyEffectiveAccent")
        + "\napplyEffectiveAccent();"
        + "\nconsole.log(JSON.stringify({ calls, data: document.documentElement.dataset.accent || null }));\n"
    )
    assert json.loads(_run_node(script)) == {"calls": [None], "data": None}


# B14: "Each settings page should have an expand and collapse all sections
# button at the top". Panes with two or more folds (Skills 2, Appearance 8,
# Shortcuts 3, Help 168 at probe p/b14.js) get one in their dock; a pane with
# one fold or none has nothing to expand all of.
def test_b14_a_pane_with_folds_gets_an_expand_all_button_in_its_dock():
    body = _js_function("settings-controls.js", "ensureSettingsFoldAll")
    assert "data-fold-all" in body or "foldAll" in body
    assert ".dock-actions" in body and "Expand all" in body and "Collapse all" in body
    shown = _js_function("settings.js", "showSettingsSection")
    assert "ensureSettingsFoldAll(" in shown


# B68: "Gemma4 26b is a4b". The pull tag stays gemma4:26b (a plain
# gemma4:26b-a4b would 404, model_manager.py's note), so the card's label and
# its purpose say what the model is: 26B of weights, about 4B active.
def test_b68_the_gemma4_26b_card_says_it_is_a4b():
    from tessellate.ai.model_manager import SUGGESTED_MODELS

    entry = next(m for m in SUGGESTED_MODELS["moe"] if m["name"] == "gemma4:26b")
    assert entry["label"] == "gemma4:26b (a4b)"
    assert "a4b" in entry["purpose"] and "12B-class" not in entry["purpose"]
    cards = (ROOT / "frontend" / "js" / "settings-models.js").read_text(encoding="utf-8")
    assert "model.label ||" in cards


# B61 (the backend half is tests/test_voice_models.py). Probe p/b61.js: the
# options carried no installed marker and choosing a size sent only
# `PUT /preferences`, with no word about a download at the first dictation.
def test_b61_the_dictation_size_menu_marks_installed_confirms_and_removes():
    js = (ROOT / "frontend" / "js" / "settings-packages.js").read_text(encoding="utf-8")
    assert "(on this computer)" in js and "to download)" in js
    assert "confirmDialog(" in js.split("function voiceModelsWire", 1)[1]
    assert "/voice/models/" in js and 'method: "DELETE"' in js
    html = (ROOT / "frontend" / "index.html").read_text(encoding="utf-8")
    assert 'id="voice-model-remove"' in html and 'id="voice-model-note"' in html


# B75: help popovers ("tooltip dropdowns") drew their text at two sizes. A
# `.help-body` popover reads 14.72px (--text-lg, inherited from the body) but a
# Settings hint promoted into the same shell is a <small>, which the browser
# shrinks: 12.27px (probe p/b75d.js, Models "muted setting-hint help-popover").
# The shell sets the size itself, so what it holds cannot choose another.
def test_b75_the_help_popover_shell_sets_one_text_size():
    sized = [
        body
        for selectors, body in _rules(_css())
        if ".help-popover" in selectors and "font-size" in body
    ]
    assert sized, "no .help-popover rule sets a font-size"
    assert all("font-size: var(--text-lg)" in body for body in sized)


# B55 (second half): "the button in the dropdown for starting searxng in the
# web sidebar in the chat tab is gone". With the search provider on DuckDuckGo
# the strip returned before drawing the engine's command (probe p/b55.js with
# PROVIDER=duckduckgo and a stopped engine: menu items ["Web search settings"]).
# The command is still offered there, since starting the engine is how someone
# on DuckDuckGo gets to try SearXNG; the dot keeps saying DuckDuckGo answers.
def test_b55_the_web_menu_still_offers_to_start_searxng_on_duckduckgo():
    import json

    script = (
        "const calls = { menu: [], dot: [] };\n"
        "let prefsCache = { search_provider: 'duckduckgo', web_search_enabled: true };\n"
        "let webSearxngTimer = null, webEngineInfo = null;\n"
        "async function apiJson() { return { backend: 'source', state: 'stopped', responding: false, installing: false }; }\n"
        "function setWebEngineDot(state, provider) { calls.dot.push(state); }\n"
        "function renderWebPanelMenu(engine) { calls.menu.push(engine); }\n"
        + _js_function("chat.js", "refreshWebSearxngStrip")
        + "\nrefreshWebSearxngStrip().then(() => console.log(JSON.stringify(calls)));\n"
    )
    calls = json.loads(_run_node(script))
    assert calls["menu"] and calls["menu"][-1] == {"state": "stopped", "running": False}
    assert calls["dot"][-1] == "remote"


# B55 (first half, the smallest honest part of "hard to find"): the clipper's
# bookmark lived only in Settings, Import & export. Typing clip, clipper or
# bookmarklet in the palette now offers a row that opens it. A redesign of the
# clipper's flow is not done.
def test_b55_the_palette_finds_the_web_clipper():
    palette = (ROOT / "frontend" / "js" / "app-palette.js").read_text(encoding="utf-8")
    assert "Web clipper" in palette and 'openSettingsModal("data", "web-clip-box")' in palette
    html = (ROOT / "frontend" / "index.html").read_text(encoding="utf-8")
    assert 'id="web-clip-box"' in html


# B56, the rest: the Timeline's "Bucket by" Auto and the Context window box said
# only "Auto". Measured at 1440: the bucket shell read "Auto (week now)" for 14
# months of notes (216 px wide for a 109 px label), and the box placeholder read
# "Auto (131,072)" at 207 px wide for a 91 px label.
def test_b56_timeline_bucket_auto_names_the_bucket_it_chose():
    js = (ROOT / "frontend" / "js" / "timeline.js").read_text(encoding="utf-8")
    paint = js[js.index("function paintTimelineFeed") :][:700]
    assert '$("timeline-scale").options[0].textContent = `Auto (${scale} now)`' in paint
    assert '<option value="auto" selected>Auto</option>' in (ROOT / "frontend" / "index.html").read_text(encoding="utf-8")


def test_b56_context_window_placeholder_carries_what_auto_found():
    js = (ROOT / "frontend" / "js" / "chat.js").read_text(encoding="utf-8")
    box = js[js.index("function renderModelContextBox") :][:1200]
    assert 'box.placeholder = usable ? `Auto (${Number(usable).toLocaleString()})` : "Auto";' in box
