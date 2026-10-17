"""INBOX 904 (the owner's 2026-10-17 bug list), the UI rows: B01, B05, B76, B81.

The suite cannot open a browser, so these hold the shapes as text; the
measurements are in `scratchpad/ui-sweeps/ui1017-*.js`.
"""

from __future__ import annotations

from pathlib import Path

from tests._app_js import frontend_text

ROOT = Path(__file__).resolve().parent.parent
INDEX = (ROOT / "frontend" / "index.html").read_text(encoding="utf-8")


def test_b01_first_steps_stay_reachable_in_a_menu_and_the_bell():
    """A setup popup was closed by accident with no way back. The dashboard dock
    has a Get started menu and the bell's first row is the same checklist."""
    first = frontend_text("first-run.js")
    assert "function getStartedSteps(" in first
    assert "function getStartedItems(" in first
    assert "function firstStepsBellRow(" in first
    assert "async function renderGetStarted(" in first
    steps = first[first.index("async function renderFirstSteps(") :]
    assert steps.index("renderGetStarted();") < steps.index("firstStepsState()"), "drawn whether or not the card is"
    assert "renderFirstSteps(host, skip)" in frontend_text("dashboard.js")
    assert 'id="dash-start"' in INDEX
    assert INDEX.index('id="dash-start"') < INDEX.index('id="dash-customise"')
    notif = frontend_text("notifications.js")
    assert "firstStepsBellRow" in notif


def test_b05_connect_a_model_is_a_split_button_with_a_hide_row():
    """The caret half holds Hide these popups, the Settings preference, so the
    switch need not be found in Settings, Models."""
    status = frontend_text("status.js")
    body = status[status.index("function renderAiOfflineNotice(") :].split("\n}\n")[0]
    assert "aiOfflineSplit(link)" in body
    js = (ROOT / "frontend" / "js" / "offline-split.js").read_text(encoding="utf-8")
    split = js[js.index("function aiOfflineSplit(") :]
    assert "split-button-main" in split and "split-button-caret" in split
    assert "kebabMenu(" in split and "Hide these popups" in split
    hide = js[js.index("function hideAiOfflineNotices(") :].split("\n}\n")[0]
    assert '"hideOfflineNotice"' in hide and "Show them again" in hide
    css = (ROOT / "frontend" / "css" / "offline-split-lazy.css").read_text(encoding="utf-8")
    assert ".ai-offline-split" in css


def test_b76_the_drafting_spinner_is_on_the_atlas_side():
    """The spinner and its words were the user's status line under their thoughts;
    they are the Atlas column's head now, with the Thinking panel."""
    body = INDEX[INDEX.index('<div class="draft-column">', INDEX.index('id="draft-status"')) :]
    head = body[: body.index('id="draft-thinking"')]
    assert 'id="draft-working"' in head
    desk = (ROOT / "frontend" / "js" / "writing-desk.js").read_text(encoding="utf-8")
    run = desk[desk.index("async function composeDraft(") : desk.index("async function streamDraft(")]
    assert 'setDraftWorking(draft.trim() ? "ph:spin Revising…" : "ph:spin Drafting…")' in run
    assert 'setLabel($("draft-status"), "ph:spin' not in desk
    busy = desk[desk.index("function setDraftBusy(") :].split("\n}\n")[0]
    assert "if (!busy) setDraftWorking();" in busy


def test_a_finished_jobs_logs_button_stays_top_right_on_the_title_line():
    """BACKLOG "Start of the next PR": the Logs button wrapped to a row of its own
    under a long line (123px down at 390). The row is the name and the button, on
    one line that does not wrap; the when and model line sits under it."""
    css = (ROOT / "frontend" / "css" / "01-forms-settings.css").read_text(encoding="utf-8")
    row = css[css.index("#task-history .entry-meta {") :].split("}")[0]
    assert "flex-wrap: nowrap" in row
    assert "margin-inline-start: auto" in css[css.index("#task-history .row-actions {") :].split("}")[0]
    js = (ROOT / "frontend" / "js" / "chat-tasks.js").read_text(encoding="utf-8")
    assert "row.append(name, taskLogButton(item));" in js and "li.append(row, when);" in js


def test_ocr_workspace_without_a_renderer_lists_the_file_and_links_to_packages():
    """The "m o" chord opened on a PDF with an empty rail (the switch had fallen
    back to Files, the rail waited for pages) and a notice with no way on."""
    lib = (ROOT / "frontend" / "js" / "library.js").read_text(encoding="utf-8")
    build = lib[lib.index("function ocrBuildPageRail(") :].split("\n}\n")[0]
    assert 'if (!rail.children.length) ocrRenderRail(image);' in build
    link = lib[lib.index("function ocrNoRendererLink(") :].split("\n}\n")[0]
    assert "Settings, Packages" in link and 'openSettingsModal("extras")' in link
    assert "ocrNoRendererLink();" in lib


def test_the_new_chat_page_paints_at_once_with_skeleton_starters():
    """The owner, 2026-10-12: the page "appears a second or two late and all at
    once". The card is no longer hidden while the starters load: the mark and the
    heading paint on the first frame and `#chat-suggest` holds four skeleton
    pieces in its own box (so nothing moves), which `loadChatSuggestions` clears.
    Measured by `scratchpad/ui-sweeps/chatemptypaint.js` (NEW=1 DELAY=1200):
    heading visible at 854 ms before, 15 ms after; heading shift 39px to 0."""
    chat = frontend_text("chat.js")
    render = chat[chat.index("function renderChatEmptyState(") :].split("\n}\n")[0]
    assert 'showSkeletons(suggest, 4, "span")' in render
    assert "loadChatSuggestions.pending" in render and "chatEmptySettle(empty)" in render
    css = (ROOT / "frontend" / "css" / "08-consistency.css").read_text(encoding="utf-8")
    assert ".chat-empty.chat-empty-waiting {\n  opacity: 0;" not in css, "the card must not wait unseen"
    assert ".chat-empty-waiting #chat-suggest > .skeleton" in css
    load = frontend_text("sheets-selects.js")
    load = load[load.index("async function loadChatSuggestions(") :].split("\n}\n")[0]
    assert "clearSkeletons(box)" in load and "loadChatSuggestions.pending = false" in load
    assert "clearSkeletons(suggest)" in chat[chat.index("function clearChatEmptyState(") :].split("\n}\n")[0]


def test_the_ocr_workspace_base_rules_load_with_the_library_bundle():
    """Boot CSS was at its cap: sixteen pure `.ocr-*` rules moved from
    07-whiteboard-misc.css to library-lazy.css (the workspace opens from the
    Library bundle). A class that a boot or later rule still names stays behind
    (a boot override would lose to a rule that loads after it); the computed
    styles of the workspace's 139 elements were identical at 1440, 1024 and
    390 (`scratchpad/ui-sweeps/computeddump.js`)."""
    boot = (ROOT / "frontend" / "css" / "07-whiteboard-misc.css").read_text(encoding="utf-8")
    lazy = (ROOT / "frontend" / "css" / "library-lazy.css").read_text(encoding="utf-8")
    assert "\n.ocr-head-right {" in lazy and "\n.ocr-head-right {" not in boot
    assert "\n.ocr-head-top {" in boot, "shares an element with .dialog-head: moving it flipped the gap"
