"""INBOX 435, the owner's mid-work reports, each pinned as measured.

* The AI status dot's "checking" glyph sat 3px off its centre (an ellipsis
  rides the baseline; a font-tuned translate missed on Windows): drawn by CSS
  now, 0.5px from the centre measured from pixels.
* The companion, perched on the status bar, drew over the AI status popup:
  a bar with an open popup steps above the companion's band (z 50).
* Settings, Models said "Can't reach the Tessellate server" while the app ran:
  shown on a first open before the status answered and on a slow poll.
* A note nothing could file offers its likely categories as one-tap chips.
"""

from __future__ import annotations

from pathlib import Path

from tests._app_js import app_js_text

ROOT = Path(__file__).resolve().parent.parent
CSS = ROOT / "frontend" / "css"


def test_the_checking_dot_is_drawn_and_centred_by_the_grid():
    shell = (CSS / "00-tokens-shell.css").read_text(encoding="utf-8")
    rule = shell[shell.index('.ai-status[data-level="idle"] .ai-status-dot {'):]
    rule = rule[: rule.index("}")]
    assert "radial-gradient(" in rule and "transform" not in rule
    assert 'translateY(-0.16em)' not in shell
    code = app_js_text()
    assert 'textContent = state.level === "idle" ? "" : AI_STATUS_GLYPH[state.level]' in code


def test_a_bar_with_an_open_popup_stands_above_the_companion():
    css = (CSS / "08-consistency.css").read_text(encoding="utf-8")
    at = css.index("#status-bar:has(.ai-status-wrap:hover")
    rule = css[at:css.index("}", at)]
    assert "header#top-bar:has(" in rule and "z-index: 51;" in rule
    assert "#nm-buddy-band {" in css and "z-index: 44;" in css[css.index("#nm-buddy-band {"):][:900]


def test_models_says_cannot_reach_only_when_the_server_is_down():
    code = app_js_text()
    render = code[code.index("function renderSettings() {"):]
    render = render[: render.index("\n}\n")]
    assert '"Checking the models…"' in render
    assert 'down: "Can\'t reach the Tessellate server."' in render
    assert 'slow: "The model server is slow to answer. Checking again…"' in render
    poll = code[code.index("async function refreshModelStatus() {"):]
    poll = poll[: poll.index("\n}\n")]
    assert 'modelStatusProblem = up ? "error" : "down";' in poll
    assert '"TimeoutError"' in poll
    # A slow answer keeps the last good status and flags itself (ledger 1520);
    # only a fault or an unreachable server drops it.
    slow = poll[poll.index('modelStatusProblem = "slow"'):]
    assert "modelStatus = null" not in poll[: poll.index('modelStatusProblem = "slow"')]
    assert slow.index("modelStatus = null") > slow.index("else {")
    assert 'if (modelStatusProblem === "slow") {' in render
    assert "Showing the last answer." in render


def test_an_unfiled_note_offers_one_tap_categories():
    code = app_js_text()
    settle = code[code.index("function settleCaptureStatus(status"):]
    settle = settle[: settle.index("\n}\n")]
    assert "status.suggestions" in settle and "moveNotesToCategory([status.id], name)" in settle
    assert 'status.filed_by === "words"' in code


def test_the_needle_caveat_says_it_is_offline_and_nothing_is_asked():
    extras = (ROOT / "src" / "tessellate" / "core" / "extras.py").read_text(encoding="utf-8")
    assert "Runs offline, inside the app." in extras and "Nothing for you to do." in extras


def test_the_tags_field_has_the_apps_own_list_not_a_datalist():
    html = (ROOT / "frontend" / "index.html").read_text(encoding="utf-8")
    assert 'id="tag-suggestions"' not in html and 'list="tag-suggestions"' not in html
    code = app_js_text()
    assert 'tagSuggest: ["/js/tag-suggest.js"]' in code and 'tagSuggest: ["openTagSuggest", "renderReevaluateResult"]' in code
    # The edit form's tags are chips with one input since INBOX 606.
    #: One listener now serves the tags fields and every search box (Brief 86), so it reads the target once.
    assert 'box.matches?.("#entry-tags, .note-edit-tags > input")) openTagSuggest(box)' in code
    suggest = (ROOT / "frontend" / "js" / "tag-suggest.js").read_text(encoding="utf-8")
    # Sized and placed to the field, a combobox, one open at a time.
    assert "box.style.width = `${Math.min(field.width" in suggest
    assert 'input.setAttribute("role", "combobox")' in suggest
    assert "if (tagSuggestOpening?.input === input) {" in suggest
    css = (CSS / "05-sidebars-themes.css").read_text(encoding="utf-8")
    assert ".tag-suggest {" in css


def test_lazily_loaded_lists_show_placeholders_while_they_load():
    # skeletons.js with every request held 1.5s: 1 of 11 views showed
    # placeholders before (the Timeline); 9 after, the other two answered.
    code = app_js_text() + "\n".join(
        (ROOT / "frontend" / "js" / name).read_text(encoding="utf-8") for name in ("documents.js", "library.js", "whiteboard.js")
    )
    for container, fetch in (
        ('showSkeletons(list, 4, "li");\n  if (!list.children.length', '"/conversations"'),
        ('showSkeletons(sideList, 4, "li");', "loadDocumentsNow(selectId)"),
        ("showSkeletons(grid, 4);\n  const listed", '"/whiteboard/boards"'),
        ('showSkeletons($("reminder-groups"), 3);', '"/reminders"'),
        ('if (ifUnchanged !== "skip") showSkeletons(grid, 6);', '"/media"'),
        ("showSkeletons(container, 3);", '"/audit?limit=100&entity_type=skill"'),
        ("showSkeletons(outline, 4);", "clearSkeletons(outline);"),
    ):
        assert container in code, container
        assert fetch in code, fetch
    assert code.count("clearSkeletons(") >= 9


def test_the_tags_list_follows_the_pointer_and_takes_a_chosen_row():
    """INBOX 441: "no changing hover states for this dropdown menu and no way
    to navigate with keyboard". Pointing lights a row as the arrows do, and
    Enter takes a row chosen either way, not only once something is typed."""
    suggest = (ROOT / "frontend" / "js" / "tag-suggest.js").read_text(encoding="utf-8")
    assert 'row.addEventListener("pointermove"' in suggest
    assert "(state.moved || tagSuggestToken(input).token)" in suggest



def test_an_image_line_being_edited_keeps_its_picture():
    """INBOX 442: the graph popup's Edit put the caret on a note's last line,
    its picture, which revealed as markdown and lost the image. A revealed
    image keeps a widget after its source."""
    docs = (ROOT / "frontend" / "js" / "documents.js").read_text(encoding="utf-8")
    assert "new DocImageWidget(src, text.slice(2, close), true), side: 1" in docs
    assert '".cm-md-image-under"' in docs


def test_the_source_choice_stays_with_the_boxes_that_have_the_toggle():
    """INBOX 447: Source pressed in Capture was remembered for every note box,
    so the graph popup (no toggle) showed raw markdown and image links."""
    docs = (ROOT / "frontend" / "js" / "documents.js").read_text(encoding="utf-8")
    assert 'NOTE_SOURCE_HOSTS = new Set(["entry-content", "entry-edit-content"])' in docs
    assert "noteSourceWanted() && NOTE_SOURCE_HOSTS.has(host.id) ? [] : live" in docs




def test_a_timed_out_status_poll_is_not_logged_as_a_warning():
    """The poll retries by itself and the pill already says "slow": the
    browser log used to record `WARN [Network] GET /models/status: signal
    timed out` each time. A silent request's timeout is not logged (the poll
    is the only caller that sets its own `AbortSignal.timeout`); every other
    timeout, and every real network failure, still is."""
    code = app_js_text()
    poll = code[code.index("async function refreshModelStatus() {"):]
    poll = poll[: poll.index("\n}\n")]
    assert "silent: true" in poll and "AbortSignal.timeout(8000)" in poll
    assert '!(silent && networkErr?.name === "TimeoutError")' in code


def test_a_late_tag_list_does_not_open_after_the_tag_was_entered():
    # Found by tests-e2e/specs/notes.spec.js flaking: the first open waits for
    # GET /tags; a tag typed and entered meanwhile left the field empty, and
    # the late list then opened with every tag over the form's Save button.
    source = (Path(__file__).resolve().parent.parent / "frontend" / "js" / "tag-suggest.js").read_text(encoding="utf-8")
    start = source.index("async function openTagSuggest(input) {")
    body = source[start : source.index("\n}\n", start)]
    waiting = body.index("if (tagSuggestOpening?.input === input) {")
    assert "if (input.value !== tagSuggestOpening.value) tagSuggestOpening.typed = true;" in body[waiting : waiting + 260]
    after = body[body.index('await apiJson("/tags"') :]
    assert "if (!tagSuggestToken(input).token && (opening.typed || input.dataset.tagged)) return;" in after
    # A tag entered before this file arrived: the note form marks the field,
    # a key or press in it clears the mark, and the list stays shut till then.
    fill = source[source.index("function fillTagSuggest() {") :]
    assert "if (!token && input.dataset.tagged) {" in fill[:400]
    panels = (Path(__file__).resolve().parent.parent / "frontend" / "js" / "note-edit-panels.js").read_text(encoding="utf-8")
    commit = panels[panels.index("const commitTag = () => {") :]
    commit = commit[: commit.index("\n  };")]
    assert 'tagEntry.dataset.tagged = "1";' in commit
    assert 'for (const type of ["focus", "pointerdown"]) tagEntry.addEventListener(type, () => delete tagEntry.dataset.tagged);' in panels
