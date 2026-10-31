"""Audit 1031 extras (Z rows): source-level checks for the fixes that have no server half.

Each test names its row. The behaviour was driven in a browser (numbers in
docs/roadmap/agent-remaining/xfix-1031.md); these keep the shape from drifting.
"""
from __future__ import annotations

from tests._app_js import frontend_text


def test_z11_tools_and_features_draws_a_first_page_and_the_rest_on_scroll() -> None:
    js = frontend_text("dashboard.js")
    assert "const FEATURES_FIRST_ROWS = 40;" in js
    body = js[js.index("function featuresPaint"):js.index("function renderFeatures")]
    assert "IntersectionObserver" in body and "isIntersecting" in body
    assert "createDocumentFragment" in body


def test_z3_every_palette_row_is_in_the_catalogue_or_found_by_its_words() -> None:
    js = frontend_text("app-features.js")
    rows = js[js.index("function featureCommandRows"):]
    rows = rows[: rows.index("\n}\n")]
    assert "!r.group" in rows, "the open document's own rows are left out"
    assert "held.also" in rows, "a row held under another name is found by the palette's words"
    render = frontend_text("dashboard.js")
    render = render[render.index("function renderFeatures"):]
    render = render[: render.index("\n}\n")]
    assert "featureCommandRows(groups)" in render and "item.also" in render


def test_z17_palette_rows_never_name_the_lazy_caught_const_directly() -> None:
    js = frontend_text("settings-panes.js")
    panes = js[js.index("function paletteCommands"):]
    panes = panes[: panes.index("\n}\n")]
    assert "paletteCaught)" not in panes and "...paletteCaught }" not in panes
    assert "paletteCaughtNow()" in panes
    assert 'typeof paletteCaught === "undefined"' in js


def test_z19_a_carried_note_is_filed_by_a_drop_on_a_category_or_a_space() -> None:
    js = frontend_text("obj-carry.js")
    assert "OBJ_FILE_DESTS" in js and "#category-list li[data-category]" in js
    assert "OBJ_RENDERERS.category" in js and "OBJ_RENDERERS.space" in js
    assert "moveNotesToCategory([ref.id]" in js and "moveNotesToSpace([ref.id]" in js
    assert 'g.ref?.kind !== "note"' in js, "only notes are filed"
    assert "data-space-id" in js and ':not([data-space-id="all"])' in js
    assert "closeSpaceMenu()" in js, "the menu the hover opened is closed at the end"
    assert "dataset.category = category" in frontend_text("notes-list.js")
    assert "async function moveNotesToSpace" in frontend_text("batch-space.js")


def test_z6_a_question_move_says_so_offers_undo_and_keeps_the_focus_in_the_list() -> None:
    js = frontend_text("questions-view.js")
    body = js[js.index("const move = (state"):]
    body = body[: body.index("actions.append")]
    assert "offerUndo(" in body and "SAID[state]" in body
    assert "questionsFocusAfter(at)" in body
    assert "function questionsFocusAfter" in js


def test_z2_stopping_a_clock_is_offered_back() -> None:
    js = frontend_text("utility-tools.js")
    body = js[js.index("function stopUtilityClock"):]
    body = body[: body.index("\n}\n")]
    assert "offerUndo(" in body and "utilityResume(clock, seconds)" in body


def test_z5_a_pickable_chart_has_full_size_chips_on_a_phone() -> None:
    js = frontend_text("ask-chart.js")
    assert "function askChartChips" in js and "chart.interactive && chart.onPick" in js
    css = (frontend_text("ask-chart.js") and open("frontend/css/utilities-lazy.css", encoding="utf-8").read())
    assert ".ask-chart-chips {\n  display: none;" in css
    assert "min-height: var(--target-min);" in css


def test_z14_live_captions_doors_are_hidden_when_no_engine_is_installed() -> None:
    js = frontend_text("meetings.js")
    body = js[js.index("async function syncCaptionsDoors"):]
    body = body[: body.index("\n}\n")]
    assert "/voice/status" in body and "captions?.available === false" in body
    assert '"meeting-captions"' in body and '"recordings-captions"' in body
    assert "captions-off" in body, "its own class, so the dialog's state toggle of `hidden` never undoes it"
    assert "syncCaptionsDoors()" in js[js.index("async function openMeetingRecorder"):js.index("function openVoiceNote")]
    assert "syncCaptionsDoors()" in js[js.index("async function renderRecordings"):][:400]
    css = open("frontend/css/meetings-lazy.css", encoding="utf-8").read()
    assert ".captions-off {\n  display: none !important;" in css
