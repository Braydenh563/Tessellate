"""Static shapes behind the boot long-task and handler-lag fixes (L-world-class-354, 355).

Measured in headless Chromium at 4x CPU by scratchpad/ui-sweeps/bootlongtasks.js and
handlerlag.js; these checks hold the shape so a later edit cannot quietly bring the cost back.
"""
import re
from pathlib import Path

JS = Path(__file__).resolve().parent.parent / "frontend" / "js"


def read(name):
    return (JS / name).read_text(encoding="utf-8")


def test_usage_ledger_wires_inside_onsurface():
    # A top-level $("id") for an id in an unbuilt surface builds the whole surface at boot (151-186 ms at 4x).
    src = read("usage-ledger.js")
    head = src.split('onSurface("settings"', 1)[0]
    assert not re.search(r"^\s*\$\(", head, re.M), "top-level $() before onSurface(settings)"


def test_meaning_text_is_memoized():
    src = read("meaning.js")
    assert re.search(r"meaningTexts\s*=\s*new Map\(\)", src)
    assert "meaningTexts.get(" in src and "meaningTexts.set(" in src


def test_settings_find_caches_row_text_and_warms_idle():
    src = read("settings-find.js")
    assert "row.said ??=" in src
    #: Focus on the search box starts the warm; delegated (`focusin`) because the
    #: Settings body can be parsed after this file loads.
    assert "function settingRowsWarm" in src and '"focusin"' in src and '"settings-search"' in src


def test_filter_settings_defers_pane_build():
    # Building the matched pane on the key that changes the first match was 100-190 ms of that key.
    src = read("settings.js")
    body = src.split("function filterSettings", 1)[1].split("\nfunction ", 1)[0]
    assert "setTimeout(function showFirstSettingsMatch" in body
    tail = body.split("showFirstSettingsMatch", 1)[0]
    assert "showSettingsSection(first)" not in tail


def test_label_optics_waits_for_the_first_frame():
    # Its probe's getBoundingClientRect was the document's first full layout, forced inside
    # settings.js's eval (75 of 99 ms at 4x CPU); after the first frame that layout is done.
    src = read("settings.js")
    body = src.split("function measureLabelOptics(", 1)[1].split("\n}\n", 1)[0]
    assert "if (!labelOptics.booted) return;" in body
    assert not re.search(r"^measureLabelOptics\(\);", src, re.M), "a bare boot call forces layout mid-parse"
    assert "afterFrames(() => setTimeout(function labelOpticsFirst()" in src


def test_first_clock_paint_is_its_own_task():
    # The page's first Intl call is about 50 ms of ICU set-up at 4x CPU; in shell-reminders.js's
    # eval it made one 94 ms task of the two.
    src = read("shell-reminders.js")
    assert not re.search(r"^(startClockTicker|tickClocks)\(\);", src, re.M)
    assert "setTimeout(function firstClockPaint()" in src


def test_atlas_looks_build_on_first_read():
    # Both looks built at eval were 52 of atlas.js's 86 ms eval at 4x CPU.
    src = read("atlas.js")
    build = src.split("function atlasBuild() {", 1)[1].split("\n}\n", 1)[0]
    assert "Object.values(ATLAS_LOOKS)" not in build
    assert "function atlasBuildLook(spec)" in src
    assert "Object.defineProperty(ATLAS_LOOKS, name" in src
    assert "function atlasWarmLook()" in src


def test_dashboard_render_yields_between_its_parts():
    # Greeting, menus and the widget grid in one task were 74 ms of a 119 ms boot microtask at 4x.
    src = read("dashboard.js")
    body = src.split("async function renderDashboard(", 1)[1].split("\n}\n", 1)[0]
    assert body.count("await dashYield();") >= 2
    assert body.index("renderDashboardGreeting();") < body.index("await dashYield();") < body.index("grid.replaceChildren();")
    tail = body.split("grid.replaceChildren();", 1)[1].split("for (const name of layout.order)", 1)[0]
    assert "await " not in tail, "the grid is rebuilt in one go, so two renders cannot interleave cards"


def test_default_swatch_is_read_after_the_frame():
    # The lift-and-read settled the style of the pane the press had just shown (90 of 250 ms at 4x).
    src = read("settings.js")
    body = src.split("function renderAppearance() {", 1)[1].split("renderCustomThemes();", 1)[0]
    assert "afterFrames(() => setTimeout(() => (button.style.background = themeDefaultAccent()" in body
    assert body.count("themeDefaultAccent()") == 1


def test_library_warm_waits_for_calm_in_an_idle_slot():
    # graph.js's eval, started just before a press, landed inside Settings -> Data's first show.
    src = read("lazy-entries.js")
    body = src.split("function warmLibraryAfterInput()", 1)[1].split("\nwarmLibraryAfterInput();", 1)[0]
    assert "requestIdleCallback(fn" in body
    assert body.count("Date.now() < calmAt") == 2
    assert '["pointerdown", "keydown", "click"]' in body


def test_settings_search_warms_rows_and_vocab_before_the_first_key():
    # The first key scanned the pane, built the vocab and the meaning memo (133-141 ms at 4x; L-world-class-359).
    src = read("settings-find.js")
    assert "function settingRowsWarmSoon(" in src
    assert "settingVocab(rows)" in src and "meaningMissing([]" in src
    assert "renderHelpTopics()" in src
    assert 'settingRowsWarmSoon(0)' in src
    settings = read("settings.js")
    assert "settingRowsScan?.panes.delete(pane)) window.settingRowsScan?.warmSoon?.()" in settings
    assert "warmSoon?.(1500)" in settings


def test_pane_title_echo_writes_only_on_change():
    # Removing and re-adding the class on every key dirtied the pane for the search index.
    body = read("phone-shell.js").split("function echoSettingsPaneTitle", 1)[1][:900]
    assert 'want && want.classList.toggle("jump-echo", true)' in body  # want can be false, and false?.x is not nullish


def test_chat_model_panel_does_not_build_a_surface():
    # `$` builds an unbuilt surface; a scroll while Settings showed built Chat inside a key (60-77 ms; L-world-class-360).
    body = read("ai-tools.js").split("function placeChatModelPanel", 1)[1][:500]
    assert 'document.getElementById("chat-model-panel")' in body
    assert '$("chat-model-panel")' not in body


def test_settings_body_parses_in_pieces():
    # One 56 ms parse task at 4x; 22 pieces of about 1 ms each (L-world-class-361).
    # The mark is in the script, not an attribute on the tag: the test lints read the tag as `<template id=.. data-surface="settings">`.
    assert 'splitMark(entry)' in read("settings-body.js") and "data-split-at" not in (JS.parent / "index.html").read_text(encoding="utf-8")
    src = read("settings-body.js")
    assert "parseNext(entry, budget)" in src and "parseNext(next[1], 8)" in src


def test_first_face_is_two_tasks():
    # Drawn, then cut and measured: 86 ms as one task, about 43 each (L-world-class-362).
    assert 'nameMark(seed, +holders[0]?.dataset.userMark || 18, "draw")' in read("chat-agent.js")
    src = read("avatars.js")
    assert "nameMarkGenerated(seed, size, drawOnly = false)" in src
    assert "nameMarkGenerated(seed, 56, true)" in src


def test_dashboard_menus_yield_one_task_each():
    # The post-yield piece was 56-82 ms at 4x: the four menus ran back to back (L-world-class-363).
    src = read("dashboard.js")
    menus = "renderQuickLinks(); await dashYield(); renderDashMore(); await dashYield(); wireDashDensity(); await dashYield(); renderFirstStepsLazy(); await dashYield();"
    assert menus in " ".join(src.split())
