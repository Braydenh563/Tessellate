"""INBOX 1301 D2 and D3: the dashboard's Get started card and button.

D2 (the owner): the first steps needed "a better, more functional, better
positioned, sized etc modern and professional redesign". Measured by
`scratchpad/ui-sweeps/getstarted1301.js`: the card was 350px tall at
1440x900 (658px at 390x844, the widgets starting at 1065) and its name tile
was 16px taller than the others, so ticking step one shrank the card. Now
one head row and three tiles of one height: 114px (275px on a phone), the
same height at 0, 1 and 2 steps done.

D3 (the owner): "the user should be able to hide or mark as complete the
getting started button." Mark all as done and Hide Get started, in the
card's menu and the dock's, persisted, with Customise, Show Get started as
the way back. The suite cannot open a browser, so the shapes are held here.
"""

from __future__ import annotations

from pathlib import Path

from tessellate.ai.help_topics_more import MORE_TOPICS
from tests._app_js import frontend_text

ROOT = Path(__file__).resolve().parent.parent
FIRST = frontend_text("first-run.js")
DASH = frontend_text("dashboard.js")
CSS05 = (ROOT / "frontend" / "css" / "05-sidebars-themes.css").read_text(encoding="utf-8")
LAZY = (ROOT / "frontend" / "css" / "first-run-lazy.css").read_text(encoding="utf-8")
INDEX = (ROOT / "frontend" / "index.html").read_text(encoding="utf-8")


def _body(text: str, head: str) -> str:
    return text[text.index(head) :].split("\n}\n")[0]


def test_the_card_is_one_head_row_over_the_steps():
    card = _body(FIRST, "function firstStepsCard(")
    for part in ('"first-steps-head"', '"first-steps-progress"', '"progressbar"', '"aria-valuenow"', "kebabMenu(", '"aria-expanded"'):
        assert part in card, part
    #: The fill moves by transform through the CSSOM: the CSP refuses style=.
    assert "fill.style.transform = `scaleX(${done / 3})`" in card
    #: The row of doors under the steps came and went with the sample notes.
    assert "first-steps-more" not in FIRST and "first-steps-more" not in LAZY
    assert "firstStepsDoor" not in FIRST


def test_every_tile_has_one_height_so_a_tick_moves_nothing():
    steps = CSS05[CSS05.index(".start-steps {") :].split("}")[0]
    assert "grid-auto-rows: minmax(3.75rem, auto);" in steps
    form = LAZY[LAZY.index(".start-step-form input {") :].split("}")[0]
    assert "margin: 0;" in form, "the field's own bottom margin was the extra 10px"
    assert ".dash-getting-started" not in CSS05, "the centred 2rem panel is gone"


def test_the_fold_is_remembered_and_turns_the_caret():
    card = _body(FIRST, "function firstStepsCard(")
    assert 'prefs.get("firstStepsCollapsed", "") !== "1"' in card
    assert 'prefs.set("firstStepsCollapsed", open ? "1" : "0")' in card
    assert ".first-steps.is-folded .first-steps-fold .ph {\n  transform: rotate(-90deg);" in LAZY


def test_hide_and_mark_all_done_are_in_both_menus():
    card_menu = _body(FIRST, "function firstStepsMenuItems(")
    dock_menu = _body(FIRST, "function getStartedItems(")
    for menu in (card_menu, dock_menu):
        assert "Mark all as done" in menu and "getStartedMarkDone" in menu
        assert "Hide Get started" in menu and "getStartedHide" in menu


def test_the_choices_persist_and_are_honoured_everywhere():
    hide = _body(FIRST, "function getStartedHide(")
    assert 'prefs.set("getStartedHidden", "1")' in hide
    done = _body(FIRST, "function getStartedMarkDone(")
    assert 'prefs.set("getStartedDone", "1")' in done
    #: 79c7e07 split the read out of `firstStepsState` (now the shared in-flight
    #: wrapper) into `firstStepsRead`; the "marked done" check lives in the read.
    state = _body(FIRST, "async function firstStepsRead(")
    assert 'prefs.get("getStartedDone", "") === "1"' in state
    assert 'prefs.get("getStartedHidden", "") === "1"' in _body(FIRST, "async function renderGetStarted(")
    assert 'prefs.get("getStartedHidden", "") === "1"' in _body(FIRST, "async function firstStepsBellRow(")
    lazy = _body(DASH, "function renderFirstStepsLazy(")
    assert lazy.index('"getStartedHidden"') < lazy.index('lazyScript("/js/first-run.js")'), "hidden: nothing to load"


def test_customise_brings_it_back():
    items = _body(DASH, "function dashCustomiseItems(")
    assert "Show Get started" in items and '.then(() => getStartedShow())' in items
    #: INBOX 1304: one way back shared by Customise, the hide toast and the palette;
    #: in the lazy first-run.js, loaded first by callers outside it (boot budget).
    show = _body(FIRST, "function getStartedShow(")
    for key in ("getStartedHidden", "getStartedDone", "firstStepsHidden"):
        assert f'"{key}"' in show, key


def test_help_names_the_new_controls():
    topic = next(t for t in MORE_TOPICS if t["id"] == "first-steps")
    for words in ("Mark all as done", "Hide Get started", "Show Get started"):
        assert words in topic["body"], words
    popover = INDEX[INDEX.index('id="dash-help"') :].split("</div>")[0]
    assert "Show Get started" in popover
