"""L-documents-2: a daily word goal and a writing streak, counted per day in prefs.

The block between the `writing-streak` markers in documents.js is run in node with a fixed clock, a fake
prefs store and a fake status-bar element, so the day roll-over, the streak and the paste guard are
checked without a browser. The menu and the bar are measured in Chromium (scratchpad/ui-sweeps).
"""

from __future__ import annotations

from tests.test_code_documents import JS, _node

DOCS = (JS / "documents.js").read_text(encoding="utf-8")
BLOCK = DOCS[DOCS.index("// writing-streak:begin") : DOCS.index("// writing-streak:end")]

PRELUDE = (
    "const store = {};\n"
    "const prefs = { get: (k, d) => (k in store ? store[k] : d), set: (k, v) => { store[k] = v; } };\n"
    "const RealDate = Date; let day = '2026-11-10T12:00:00';\n"
    "globalThis.Date = class extends RealDate { constructor(...a) { super(...(a.length ? a : [day])); } };\n"
    "const listeners = {};\n"
    "const counts = { textContent: '', title: '', addEventListener(t, f) { listeners[t] = f; }, getBoundingClientRect: () => ({ left: 0, top: 0 }) };\n"
    "const $ = () => counts; const DOC_COUNTS_TITLE_PROSE = 'T';\n"
    "const docIsCodeFile = () => false; let menu = null;\n"
    "const openMenuAtPoint = (items) => { menu = items; };\n"
    "let held = null; const wireLongPress = (el, fn) => { held = fn; };\n"
    + BLOCK
    + "\nconst count = (id, words) => { counts.textContent = 'x'; listeners['doc:counted']({ detail: { id, words } }); };\n"
    "const setGoal = (g) => { listeners.contextmenu({ preventDefault() {}, clientX: 1, clientY: 1 }); menu.find((i) => i.label.endsWith(g)).run(); };\n"
    "const state = () => JSON.parse(store.docWriting);\n"
)


def run(body: str):
    return _node(PRELUDE, f"(() => {{ {body} }})()")


def test_words_added_are_counted_for_the_day_and_a_first_count_is_only_a_baseline():
    got = run("count(1, 100); count(1, 130); count(1, 125); count(1, 140); return state();")
    assert got["words"] == 45 and got["day"] == "2026-11-10"


def test_a_paste_or_a_switch_of_document_is_not_credited():
    got = run("count(1, 100); count(1, 900); count(2, 5); count(2, 20); return state();")
    assert got["words"] == 15


def test_reaching_the_goal_starts_a_streak_and_a_next_day_extends_it_but_a_gap_ends_it():
    got = run(
        "count(1, 0); setGoal('250 words'); setGoal('250 words');\n"
        "for (let w = 100; w <= 300; w += 100) count(1, w);\n"
        "const first = state();\n"
        "day = '2026-11-11T12:00:00'; count(1, 300); for (let w = 400; w <= 600; w += 100) count(1, w);\n"
        "const second = state();\n"
        "day = '2026-11-14T12:00:00'; count(1, 600); count(1, 700); count(1, 800); count(1, 900);\n"
        "return { first, second, third: state(), line: menuLine() };\n"
        .replace("menuLine()", "(listeners.contextmenu({ preventDefault() {} }), menu[0].label)")
    )
    assert got["first"]["streak"] == 1 and got["first"]["last"] == "2026-11-10"
    assert got["second"]["streak"] == 2 and got["second"]["last"] == "2026-11-11"
    assert got["third"]["streak"] == 1 and got["third"]["last"] == "2026-11-14"
    assert "of 250 words today, 1-day streak" in got["line"]


def test_the_menu_offers_four_goals_and_no_goal_and_marks_the_current_one():
    got = run(
        "count(1, 0); setGoal('500 words'); listeners.contextmenu({ preventDefault() {} });\n"
        "return menu.map((i) => i.label);"
    )
    assert got[0] == "ph:pencil-simple-line 0 of 500 words today"
    assert "ph:check 500 words" in got and "ph:flag 250 words" in got and "ph:x No daily goal" in got


def test_the_bar_says_how_far_today_is_only_with_a_goal_and_a_streak_that_lapsed_is_not_shown():
    got = run(
        "count(1, 0); count(1, 50); const none = counts.textContent; setGoal('250 words'); count(1, 80);\n"
        "const withGoal = counts.textContent;\n"
        "day = '2026-11-20T12:00:00'; listeners.contextmenu({ preventDefault() {} });\n"
        "return { none, withGoal, title: counts.title, line: menu[0].label };"
    )
    assert got["none"] == "x"
    assert got["withGoal"].endswith("of 250 today")
    assert "Right-click for the daily word goal" in got["title"]
    assert "streak" not in got["line"]


def test_a_hold_on_the_counts_opens_the_same_menu_as_a_right_click():
    got = run("count(1, 0); held({}, { x: 5, y: 6 }); return menu.map((i) => i.label).slice(1, 3);")
    assert got == ["ph:flag 250 words", "ph:flag 500 words"]
