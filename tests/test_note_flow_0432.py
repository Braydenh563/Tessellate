"""The note flow as a person drives it (INBOX 432).

Each test pins one defect measured in Chromium on 2026-10-03:

* Ctrl+Enter in the capture box saved nothing once the editor view was
  mounted over the textarea (the textarea's own listener stopped hearing
  keys), and the edit form had no chord at all.
* After a save the focus stayed on the Save button, so "keep writing" typed
  into nothing.
* A note nothing could file said "Filed under Uncategorised (0% sure)", read
  twice (the composer's line and a toast), with no way to pick a category.
* A single note's category could only be changed by dragging its chip or
  opening the whole edit form; the card's menu had no Move.
"""

import re
import time
from pathlib import Path

from tessellate.api import routes_entries

ROOT = Path(__file__).resolve().parent.parent
FRONTEND = ROOT / "frontend"


def _read(name: str) -> str:
    return (FRONTEND / ("js/" + name if name.endswith(".js") else name)).read_text(encoding="utf-8")


def _function(source: str, name: str) -> str:
    start = re.search(rf"^(?:async )?function {name}\(", source, re.M)
    assert start, f"{name} not found"
    rest = source[start.end():]
    end = re.search(r"^}", rest, re.M)
    return rest[: end.start()]


def _wait_settled(client, entry_id, timeout=10.0):
    deadline = time.time() + timeout
    while time.time() < deadline:
        status = client.get(f"/entries/{entry_id}/filing").json()
        if status["filing_state"] != "pending":
            return status
        time.sleep(0.05)
    return status


def test_a_note_nothing_could_file_says_so(client, monkeypatch):
    monkeypatch.setattr(routes_entries, "_file_entry_now", lambda *a, **k: ("Uncategorised", 0, "none"))
    created = client.post("/entries", json={"content": "buy milk", "defer_filing": True}).json()
    status = _wait_settled(client, created["id"])
    assert status["filed_by"] == "none"
    assert status["category"] == "Uncategorised"


def test_a_note_the_model_filed_says_ai(client, monkeypatch):
    monkeypatch.setattr(routes_entries, "_file_entry_now", lambda *a, **k: ("Groceries", 82, "llm"))
    created = client.post("/entries", json={"content": "buy milk", "defer_filing": True}).json()
    status = _wait_settled(client, created["id"])
    assert status["filed_by"] == "ai"
    assert status["category"] == "Groceries"


def test_a_note_filed_by_the_person_says_user(client):
    created = client.post("/entries", json={"content": "buy milk", "category": "Errands"}).json()
    assert client.get(f"/entries/{created['id']}/filing").json()["filed_by"] == "user"


def test_ctrl_enter_reaches_the_box_under_the_editor():
    keymap = _function(_read("documents.js"), "noteSurfaceKeymap")
    assert '"Mod-Enter"' in keymap
    assert "host.dispatchEvent" in keymap and "defaultPrevented" in keymap
    # The capture listener claims the chord (or the editor inserts a line too)
    # and answers Cmd on a Mac.
    wiring = _read("settings-wiring.js")
    capture = wiring[wiring.index('$("entry-content").addEventListener("keydown"'):][:300]
    assert "preventDefault" in capture and "metaKey" in capture
    # The edit form has the same chord.
    form = _function(_read("note-edit-panels.js"), "renderEditForm")
    assert 'event.key === "Enter"' in form and "saveButton.click()" in form


def test_saving_puts_the_caret_back_in_the_box():
    capture = _read("capture-ask.js")
    for name in ("saveEntry", "saveEntryAsDraft"):
        body = _function(capture, name)
        reset = body.index("resetCaptureForm(")
        assert "focusCaptureBox()" in body[reset:], name


def test_the_filing_outcome_is_said_once_and_never_as_zero_percent():
    capture = _read("capture-ask.js")
    watch = _function(capture, "watchFiling")
    assert "settleCaptureStatus(status)" in watch and "!shown" in watch
    outcome = _function(capture, "filingOutcomeText")
    assert 'filed_by === "none"' in outcome
    # A confidence is quoted only when something decided.
    assert "status.ai_confidence\n    ?" in outcome
    # Unfiled offers a category, not a jump.
    assert "chooseNoteCategory" in watch and "chooseNoteCategory" in _function(capture, "settleCaptureStatus")
    # The line knows which note it is about.
    assert "status.dataset.entryId" in _function(capture, "saveEntry")


def test_one_note_moves_from_its_chip_and_its_menu():
    # In the lazy categories piece, reached from boot code through app.js's
    # LAZY_ENTRY_POINTS.
    assert "function chooseNoteCategory(" in _read("categories-panel.js")
    assert '"chooseNoteCategory"' in _read("app.js")
    cards = _read("note-cards.js")
    chip_block = cards[cards.index('const categoryEl = chip("", "category")'):][:3200]
    # INBOX 447 (5): the chip opens a menu (chip-menus.js), whose second row is the move.
    assert "openCategoryChipMenu(categoryEl, entry)" in chip_block
    assert "chooseNoteCategory([entry.id], name)" in _read("chip-menus.js")
    assert 'setAttribute("role", "button")' in chip_block
    assert "Move to category" in _read("menus.js")


def test_the_batch_move_lists_empty_categories():
    batch = _function(_read("skills.js"), "fillBatchCategories")
    assert "categoryMeta.keys()" in batch


# --- the list and the sidebar (the second audit, 2026-10-03) ---------------


def test_an_open_edit_keeps_its_text_through_a_redraw():
    form = _function(_read("note-edit-panels.js"), "renderEditForm")
    assert "noteFormDraft.id === entry.id" in form
    assert "draft ? draft.content :" in form and "draft ? draft.title :" in form
    # The title is its own field and goes back on as the leading heading.
    #: Under the note's property block, held aside while editing (meetings-644).
    assert "const typed = textarea.value.trim();" in form
    assert "parts.block : \"\") + withTitle(typed, titleInput.value)" in form
    # Cleared only on purpose: Save and Cancel (closeNoteForm).
    assert "noteFormDraft = null" in form
    assert "noteFormDraft = null" in _function(_read("note-edit-panels.js"), "closeNoteForm")


def test_leaving_a_changed_form_asks_and_an_empty_one_is_refused():
    notes = _read("notes-list.js")
    form = _function(_read("note-edit-panels.js"), "renderEditForm")
    assert 'event.key !== "Escape"' in form and "noteFormMayClose()" in form
    assert "A note needs some text" in form
    assert "noteFormMayClose()" in _function(notes, "openNoteEditor")
    # Every edit entry point goes through the guard.
    for name in ("note-cards.js", "menus.js", "chat-agent.js"):
        source = _read(name)
        assert "openNoteEditor(" in source, name
        assert not re.search(r"editingId = (entry|item|copy)\.id;\s*\n\s*renderEntries\(\)", source), name


def test_a_selection_is_of_what_is_on_screen():
    render = _function(_read("notes-list.js"), "renderEntries")
    assert "selectedIds.delete(id)" in render
    assert 'prefs.get("activeTab", null) === "notes"' in render


def test_batch_tag_splits_on_commas_and_can_be_undone():
    # INBOX 447 (4): the bar's Tags button opens the bulk dialog (tag-manager.js,
    # lazy), whose one action is one `POST /tags/bulk` with one Undo.
    assert "openBulkTags(ids)" in _function(_read("skills.js"), "batchTag")
    bulk = _function(_read("tag-manager.js"), "openBulkTags")
    assert '.split(",")' in bulk and '"/tags/bulk"' in bulk
    edit = _function(_read("tag-manager.js"), "runTagEdit")
    assert "pushUndo(" in edit and "settleUndoFromToast" in edit and '"/tags/restore"' in edit


def test_a_to_z_sorts_by_the_name_a_card_shows():
    notes = _read("notes-list.js")
    assert "noteSortName(a).localeCompare(noteSortName(b), undefined, { numeric: true" in _function(notes, "sortEntries")
    wiring = _read("settings-wiring.js")
    assert 'prefs.set("notes-sort", noteSort)' in wiring


def test_the_sidebar_lights_one_row_lists_every_category_and_takes_the_keyboard():
    notes = _read("notes-list.js")
    side = _function(notes, "renderSidebar")
    assert "!draftsOnly && !favouritesOnly" in side
    assert "categoryMeta.keys()" in side
    assert "compareCategoryNames" in side and "].sort()" not in side
    assert side.count("wireSidebarRowKeys(") >= 3
    assert 'setAttribute("aria-current", "true")' in _function(notes, "markSidebarRowCurrent")
    assert "categoryMeta.keys()" in _function(notes, "fillCategoryOptions")
    # The bigger of two same-named categories (two spaces) is the one kept.
    assert "if (!categoryMeta.has(row.name))" in _function(notes, "loadCategories")


def test_tags_filter_from_a_chip_and_from_the_box():
    notes = _read("notes-list.js")
    parse = _function(notes, "parseNoteQuery")
    assert 'lower.startsWith("#")' in parse and "before|after" in parse and 'startsWith("title:")' in parse
    match = _function(notes, "matchesSearch")
    assert 'tag === t || tag.startsWith(`${t}/`)' in match
    assert 'flag === "draft"' in match
    cards = _read("note-cards.js")
    assert "filterNotesByTag(tag)" in cards
    assert "filterNotesByTag(tag)" in _read("dashboard.js")


def test_the_rail_follows_the_note_being_read():
    """INBOX 432 kept the rail shut until a note was opened; INBOX 571 (the
    owner: "what constitutes opening a note if I can see a whole note in the
    notes section") replaced that: a card chosen by hand is the subject, and
    otherwise the card in view as the list scrolls (notes-rail-spy.js)."""
    notes = _read("notes-list.js")
    focus = notes[notes.index('list.addEventListener("focusin", (event) =>'):]
    focus = focus[: focus.index("\n  });\n")]
    assert "if (notesRailId == null) return;" not in focus
    assert 'ensureModule("notesRail")' in notes
    spy = _read("notes-rail-spy.js")
    assert "new IntersectionObserver(" in spy and "NOTES_SPY_SETTLE_MS = 150" in spy
    assert "notesSpyPin" in spy and "window.innerHeight" in spy, "a hand-picked card holds until a viewport out of sight"
    assert 'classList.add("rail-subject")' in spy
    toggle = notes[notes.index("function syncNotesRailToggle("):]
    assert "Connections beside the note you're reading" in toggle[: toggle.index("\n}\n")]
    assert "when you open one" not in notes, "546's toast goes: there is always a subject"


def test_category_rename_and_merge_can_be_undone_and_redraw_the_panel():
    panel = _read("categories-panel.js")
    rename = _function(panel, "renameCategory")
    assert "offerCategoryUndo(" in rename and "refreshAfterCategoryChange()" in rename
    assert 'confirmLabel: "Merge"' in rename
    chooser = _function(panel, "chooseCategorySheet")
    assert 'metas.push({ name: "Uncategorised"' in chooser
    assert ".sheet-close" in _function(panel, "showCategoryNotes")


def test_archive_and_duplicate_behave():
    menus = _read("menus.js")
    archive = menus[menus.index('label: "ph:archive Archive"'):][:1200]
    assert "pushUndo(" in archive
    duplicate = menus[menus.index('label: "ph:copy Duplicate"'):][:1500]
    assert "(copy)" in duplicate and "title:" not in duplicate.split("body: JSON.stringify(")[1][:400]


def test_recently_edited_sort_copy_link_and_list_keys():
    notes = _read("notes-list.js")
    assert "edited: (a, b) => noteEditedTime(b) - noteEditedTime(a)" in _function(notes, "sortEntries")
    assert '<option value="edited">Recently edited</option>' in (ROOT / "frontend" / "index.html").read_text(encoding="utf-8")
    keys = _function(notes, "initEntryListKeyboardNav")
    for key in ('"Home"', '"End"', '"Delete"', '"F2"'):
        assert key in keys, key
    assert "binNoteWithUndo(entry)" in keys
    assert "Copy wiki link" in _read("menus.js") and "appLinkMenuItem(\"note\"" in _read("menus.js")


def test_the_notes_chrome_says_less():
    # The space chip only when the notes in view span spaces.
    cards = _read("note-cards.js")
    assert "spacesCache.length > 1 && notesSpanSpaces()" in cards
    # Housekeeping does not open the activity panel or toast its finish.
    status = _read("status.js")
    assert 'const QUIET_TASK_KINDS = new Set([\n  "job-warm-filing", "job-file-entry", "filing-late",' in status
    # Start-up upkeep too: the search model's load opened the panel on every
    # login (INBOX 653).
    for kind in ("embeddings", "embedding-model", "reindex", "job-caption"):
        assert f'"{kind}"' in status.split("const QUIET_TASK_KINDS", 1)[1].split("]);", 1)[0], kind
    assert "if (!QUIET_TASK_KINDS.has(task.kind)) openPanelForRun(run);" in status
    # The sidebar fold is remembered and its peek icon is a pin.
    sheets = _read("sheets-selects.js")
    assert "sidebarCollapsed:${aside.id}" in sheets and "ph-push-pin icon-peek" in sheets
    css = (ROOT / "frontend" / "css" / "05-sidebars-themes.css").read_text(encoding="utf-8")
    #: C43 moved the scroller: the list no longer scrolls inside the sidebar's
    #: own scroller (two bars, cut mid-row); the sidebar does, head sticky.
    assert "#sidebar #category-list {\n    max-height:" not in css
    assert "#sidebar > .sidebar-head {\n    position: sticky;" in css


def test_a_row_is_one_line_with_the_time_at_its_end():
    """Rows were 74px (the date on a line of its own above the chips); 47px
    after, measured at 1440 in Chromium, thirteen to a screen against nine."""
    css = (ROOT / "frontend" / "css" / "08-consistency.css").read_text(encoding="utf-8")
    assert "padding-top: 1.4em;" not in css
    # No width held back for the hover strip (INBOX 719): it overlays the end.
    assert "padding-inline-end: 6.5rem" not in css
    assert ":not(:has(> .entry-title)) > .entry-content {\n  grid-column: 1 / 3;" in css


def test_the_selection_bar_does_what_one_notes_menu_does():
    skills = _read("skills.js")
    for name in ("batchFavourite", "batchArchive", "batchPublish"):
        assert f"function {name}(" in skills, name
    assert "pushUndo(label, undo, redo)" in _function(skills, "batchEach")
    assert "fillBatchMore();" in _function(skills, "enterSelectMode")
    assert 'id="batch-more-host"' in (ROOT / "frontend" / "index.html").read_text(encoding="utf-8")


def test_note_boxes_are_live_with_a_source_switch_not_a_preview():
    """INBOX 430, the owner: "note forms use the live view with a source
    toggle, no Preview". Measured: Live hides `**` and `[[`, Source shows the
    markdown as typed, the same text and caret either way."""
    docs = _read("documents.js")
    ext = _function(docs, "noteSurfaceExtensions")
    #: INBOX 447: the Source choice only applies where the toggle is.
    assert "host.noteLiveSlot.of(noteSourceWanted() && NOTE_SOURCE_HOSTS.has(host.id) ? [] : live)" in ext
    assert "noteLiveSlot.reconfigure" in _function(docs, "setNoteSurfaceSource")
    wiring = _read("wiring.js")
    assert "function setNoteSource(on)" in wiring and "paintEntryPreview" not in wiring
    html = (ROOT / "frontend" / "index.html").read_text(encoding="utf-8")
    assert 'id="entry-preview"' not in html and "<span class=\"toolbar-word\">Source</span>" in html
    assert "setNoteSource(!noteSourceOn())" in _function(_read("note-edit-panels.js"), "renderEditForm")
    css = (ROOT / "frontend" / "css" / "05-sidebars-themes.css").read_text(encoding="utf-8")
    assert ":not(#entry-preview-toggle):not([data-note-preview])" in css


def test_tags_have_a_place_in_the_notes_sidebar():
    side = _function(_read("notes-list.js"), "renderSidebar")
    assert 'setLabel(tagName, "ph:hash Tags")' in side and "openTagsSheet()" in side
    panel = _read("tag-manager.js")
    for name in ("openTagsSheet", "renameTagEverywhere", "removeTagsEverywhere", "mergeTagsInto"):
        assert f"function {name}(" in panel, name
    assert "pushUndo(" in _function(panel, "runTagEdit")
    assert '"openTagsSheet"' in _read("app.js")


def test_a_filter_still_being_typed_narrows_nothing():
    """`tag:` with nothing after it pushed an empty tag, and every tagged
    note failed it: the list went blank while the filter was being typed."""
    import json
    import shutil
    import subprocess

    import pytest

    node = shutil.which("node")
    if not node:
        pytest.skip("node not installed")
    notes = _read("notes-list.js")
    regex = ""
    for name in ("const TAG_COUNT_RE", "const LIVE_QUERY_RE", "const ENGINE_QUERY_RE"):
        line = notes[notes.index(name):]
        regex += line[: line.index("\n") + 1]
    parse = "function parseNoteQuery(" + _function(notes, "parseNoteQuery") + "}\n"
    script = regex + parse + (
        "const out = {};"
        "for (const q of ['tag:', 'tag:#', '#', 'in:', 'title:', 'is:', 'tag:trip in:home'])"
        " out[q] = parseNoteQuery(q);"
        "console.log(JSON.stringify(out));"
    )
    result = json.loads(subprocess.run([node, "-e", script], capture_output=True, text=True, check=True).stdout)
    for partial in ("tag:", "tag:#", "#", "in:", "title:", "is:"):
        q = result[partial]
        assert not (q["tags"] or q["categories"] or q["titles"] or q["flags"] or q["words"]), partial
    assert result["tag:trip in:home"]["tags"] == ["trip"]
    assert result["tag:trip in:home"]["categories"] == ["home"]


def test_saving_before_the_preferences_arrive_still_saves():
    # Scan 2026-10-11: with `prefsCache` still null (the preferences request
    # refused or slow at boot) Save threw "Cannot read properties of null
    # (reading 'background_filing')" and nothing was saved, with no message.
    save = (FRONTEND / "js" / "capture-ask.js").read_text(encoding="utf-8")
    assert "prefsCache?.background_filing ?? true" in save
    assert "prefsCache.background_filing" not in save


def test_every_note_the_page_creates_is_filed_in_the_background():
    # Scan 2026-10-11: a note created without `defer_filing` is filed before
    # the request returns, so it waits for the model. Against a model that
    # answers in 4 s, a mind map's Tab (a new topic) took 4.7 s and a draft
    # save 4.8 s, against 0.6 s deferred; against one that never answers the
    # request held a database connection until the 180 s wait ended. Capture
    # and the selection popup already deferred; the rest did not. A create
    # that names its category or parent has nothing to wait for either.
    missing = []
    for path in sorted((FRONTEND / "js").glob("*.js")):
        text = path.read_text(encoding="utf-8")
        for match in re.finditer(r'apiJson\(\s*"/entries"\s*,\s*\{', text):
            call = text[match.start() : match.start() + 700]
            call = call[: call.find("});")] if "});" in call else call[:500]
            if "POST" not in call:
                continue
            if any(word in call for word in ("defer_filing", "category", "parent_id", "payload")):
                continue
            missing.append(f"{path.name}:{text[: match.start()].count(chr(10)) + 1}")
    assert not missing, f"POST /entries without defer_filing: {missing}"
