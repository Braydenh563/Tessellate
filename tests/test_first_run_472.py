"""INBOX 472, the first-run walk: what a new person meets on a fresh notebook
with no AI, each item pinned as measured (scratchpad/first-run-472.md, the
sweeps `scratchpad/ui-sweeps/firstrun.js` and `firstrun2.js`).

The suite cannot open a browser, so these hold the shapes as text.
"""

from __future__ import annotations

from pathlib import Path

from tests._app_js import frontend_text

ROOT = Path(__file__).resolve().parent.parent
CSS = ROOT / "frontend" / "css"


def _state_branch(js: str, title: str) -> str:
    at = js.index(f'title: "{title}"')
    start = js.rindex("return {", 0, at)
    return js[start : js.index("};", at)]


def test_no_ai_is_a_calm_off_state_not_a_warning():
    """The supported no-AI state drew an amber "!" (a 44px amber circle in
    the phone's top bar, the loudest thing on the first screen). It is
    level "off" now: the neutral chip colours and a drawn ring, the same
    "not running" mark Settings > Models uses, and the popup names where a
    model is connected."""
    js = frontend_text("status.js")
    # UX-17 (audit 2026-10-05): "Everything works" beside "AI off" read as a
    # contradiction; the notebook is what is ready.
    for title in ("Notebook ready · AI off", "Notebook ready · chat AI off"):
        branch = _state_branch(js, title)
        assert 'level: "off"' in branch, title
        assert "Settings, Models" in branch, title
    glyphs = js[js.index("const AI_STATUS_GLYPH") :].split(";")[0]
    assert 'off: ""' in glyphs
    shell = (CSS / "00-tokens-shell.css").read_text(encoding="utf-8")
    rule = shell[shell.index('.ai-status[data-level="off"] {') :]
    rule = rule[: rule.index("}")]
    assert "var(--chip-bg)" in rule and "var(--muted)" in rule
    # INBOX 656 ("can the no ai available ai status icon be better??"): the
    # ring became the app's AI sparkle with a slash, in currentColor, so it
    # keeps the neutral chip colours above; an svg with no name of its own.
    off = js[js.index("function aiOffGlyph") :]
    off = off[: off.index("\n}\n")]
    assert 'stroke: "currentColor"' in off and '"aria-hidden": "true"' in off
    assert 'mask: "url(#ai-off-gap)"' in off
    assert 'if (state.level === "off")' in js and "aiOffGlyph()" in js
    assert ".ai-off-glyph {" in shell


def test_the_start_tiles_draw_the_quick_access_tile_recipe():
    """The empty dashboard's start tiles drew their description at 600 and
    their label at 900 (a `strong` inside a 600 button), against 400 and
    600 on the Quick access tiles one row above."""
    css = (CSS / "05-sidebars-themes.css").read_text(encoding="utf-8")
    label = css[css.index(".start-step strong {") :].split("}")[0]
    note = css[css.index(".start-step .muted {") :].split("}")[0]
    assert "font-weight: 600;" in label
    assert "font-weight: 400;" in note and "var(--text-sm)" in note


def test_the_empty_dashboard_says_empty_once_and_in_sentences():
    """The hero said "Your notebook is empty, capture a thought to begin" and
    the card under it "Your notebook is empty, here's the whole idea": the
    same fact twice, each a comma splice."""
    js = frontend_text("dashboard.js") + frontend_text("first-run.js")
    assert "Your notebook is empty," not in js
    #: The card under the hero is the first steps (first-run.js, 25c).
    #: Named as the dock's button is (INBOX 1301 D2): one thing, one name.
    assert 'title.textContent = "Get started";' in js


def test_every_library_empty_state_has_a_title_and_one_sentence():
    """Library, All on a new notebook put two bold sentences in the title;
    Bookmarks had a title and a button with no sentence between."""
    html = (ROOT / "frontend" / "index.html").read_text(encoding="utf-8")
    assert 'id="library-empty-text"' in html
    bookmark = html.split('id="bookmark-empty"')[1].split("</div>")[0]
    assert bookmark.count("<p") == 2, bookmark
    js = frontend_text("library.js")
    assert "Nothing here yet. Make" not in js
    assert '"Nothing here yet"' in js


def test_the_setup_slide_is_short_and_offers_the_ai_setup():
    """The welcome's setup card stacked two marks, repeated the first card's
    privacy sentence, said "0.0 MB so far", and had no way from "Ollama
    isn't running" to where a model is connected."""
    js = frontend_text("onboarding.js")
    diag = js.split("async function loadOnboardingDiagnostics(")[1].split("\nfunction ")[0]
    assert "nothing here leaves this machine" not in diag
    assert "MB so far" not in diag
    offers = js.split("function renderOnboardingActions(")[1].split("\nfunction ")[0]
    assert 'openSettingsModal("models")' in offers and "!models.ollama_running" in offers
    slide = js.split("function renderOnboardingSlide(")[1].split("\nfunction ")[0]
    assert '$("onboarding-icon").classList.add("hidden")' in slide


def test_chat_suggestions_with_no_model_go_to_ask():
    """With no model the Chat box is disabled, but its "Try asking" chips
    still sent, and a model-less chat answered "I couldn't find any saved
    notes" over a notebook that had some. They ask in Notes, Ask instead,
    which answers from the notes without a model."""
    js = frontend_text("sheets-selects.js")
    body = js.split("async function loadChatSuggestions(")[1].split("\nfunction ")[0]
    assert "aiIsOff()" in body and 'showNotesSection("ask")' in body
    assert body.index("aiIsOff()") < body.index("sendChatMessage(question)")


def test_first_run_surfaces_take_turns():
    """The owner, 2026-10-10: "popups and notifications clash with each other,
    the tour gets cancelled". Measured before on a fresh data dir: the
    recovery-key offer drew over the welcome (478x172 px), and the update
    question opened with the tour, which then judged its steps against the
    question's overlay and kept one ("1 of 1"). After (scratchpad cu/firstq.js):
    0 overlapping pairs in the first 10 s; welcome, the whole tour, the
    recovery offer, the update question, one at a time. Every one of the
    three goes through one queue, and the welcome's turn lasts through the
    tour it starts."""
    onboarding = frontend_text("onboarding.js")
    assert "function firstRunTurn(show, slot)" in onboarding
    assert 'document.addEventListener("tour-closed"' in onboarding
    assert 'firstRunTurn(() => showRecoveryOffer(password), "recovery")' in frontend_text("account-recovery.js")
    assert 'firstRunTurn(ask, "updates")' in frontend_text("update-dialogs.js")
    tour = frontend_text("tour.js")
    assert tour.count('document.dispatchEvent(new Event("tour-closed"))') == 2, (
        "the tour says it closed both when it ends and when it had nothing to show"
    )


def test_a_first_run_surface_waits_for_settings_to_close():
    """Scan 2026-10-11: the welcome's "Connect a model" opens Settings, and the
    recovery-key offer then drew over it (measured on a fresh data dir). The
    queue's "is something open" test names the Settings modal."""
    body = frontend_text("onboarding.js").split("function firstRunSurfaceOpen()")[1].split("\n}\n")[0]
    assert 'shown("settings-modal")' in body
    # ...and the welcome's button opens Settings before it closes the welcome,
    # because Settings loads lazily and the queue would otherwise see a clear
    # screen in between.
    offers = frontend_text("onboarding.js").split("Connect a model")[1][:700]
    assert offers.index('openSettingsModal("models")') < offers.index("closeOnboarding()")


def test_the_tour_card_is_hidden_until_placed():
    """INBOX 745 (d): a blank tour card showed in the top left for a couple of
    seconds while the first step's tab loaded."""
    tour = frontend_text("tour.js")
    assert 'getElementById("tour-card").style.visibility = "hidden"' in tour
    assert 'if (el.id === "tour-card") el.style.visibility = "";' in tour


def test_the_context_pill_opens_its_breakdown_not_compact():
    """The owner, 2026-10-10: "when I click the token window button pill, i
    expect to see a dropdown to see my token distribution stats, not it to be
    a button to compact the conversation". Measured: the pill opens a 320 px
    popover with the total, a bar and four parts; Compact is its one action
    (compress clicks: 0 on opening, 1 on Compact)."""
    wiring = frontend_text("wiring.js")
    assert '$("chat-context")?.addEventListener("click", () => $("chat-compress")' not in wiring
    ledger = frontend_text("usage-ledger.js")
    assert 'wireHelpPopover($("chat-context"), $("chat-context-pop"))' in ledger
    assert "function renderChatContextPop(" in ledger
    html = (ROOT / "frontend" / "index.html").read_text(encoding="utf-8")
    assert 'aria-controls="chat-context-pop"' in html
    assert 'id="chat-context-compact"' in html
    #: "why is the token window limit for this model soooo low :(": the
    #: popover says how the size is set and opens the setting.
    assert 'id="chat-context-window"' in html
    assert 'openSettingsModal("models", "model-context-window");' in ledger


def test_the_no_chats_line_sits_under_its_heading():
    """The owner: "should that no chats text be at the top not the bottom??"
    Measured: the line at 142 px, 21 px under the heading (it was at the foot
    of the sidebar, beside All in Library)."""
    html = (ROOT / "frontend" / "index.html").read_text(encoding="utf-8")
    assert html.index('id="conv-empty"') < html.index('id="conversation-list"')


def test_first_setup_says_it_needs_the_internet_once():
    """Brief 40: a fresh clone on a train met pip errors with no warning."""
    from tessellate.core import extras

    js = frontend_text("onboarding.js")
    assert "The first setup downloads the search model and the packages you chose" in js
    assert "after that Tessellate works offline." in js
    assert extras.download_mb(extras.EXTRAS_BY_ID["semantic"]) == 2000
    assert extras.download_mb(extras.EXTRAS_BY_ID["documents"]) > 0
    for doc in ("README.md", "docs/INSTALL.md"):
        assert "A first install needs the internet once." in (ROOT / doc).read_text(encoding="utf-8")


def test_first_run_surfaces_go_in_a_fixed_order():
    """The owner, 2026-10-11, from the Windows app: "popup panels appearing at
    the start on a new install are messy and clash/overlap a lot". The
    desktop's console question never took a turn and opened on the welcome's
    `looksReady`; the companion's offer drew over the tour's Settings step
    (263x72 px); at 390 the last surface's toast sat on the next question's
    card (337x47 px). Measured after (fr.js, a fresh data dir, `/health`
    faked as the desktop, 1440 light and 390 dark): welcome, tour, recovery
    key, console question, update question, one at a time; no overlap but the
    tour's own Settings step."""
    onboarding = frontend_text("onboarding.js")
    assert 'const FIRST_RUN_ORDER = ["welcome", "recovery", "console", "updates"];' in onboarding
    assert 'firstRunTurn(showOnboardingTurn, "welcome")' in onboarding
    console_intro = onboarding.split("async function maybeShowConsoleViewIntro()")[1].split("\n}\n")[0]
    assert "await firstRunTurn(() => confirmDialog(" in console_intro and '"console")' in console_intro
    pump = onboarding.split("async function firstRunPump()")[1].split("\n}\n")[0]
    assert "firstRunWelcomeDue()" in pump and "firstRunToastsGone(" in pump
    assert "a.rank - b.rank" in pump
    hint = frontend_text("avatars.js").split("function nameMarkBuddyHint(")[1].split("\n}\n")[0]
    assert '"tour-card", "onboarding-overlay"' in hint
