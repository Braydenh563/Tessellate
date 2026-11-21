"""Everything the agent can do, a person can do by hand (INBOX 431 (e)).

The owner: "the user needs to be able to easily do anything the ai can do".
Every write tool the agent has (`WRITE_TOOLS`, plus the category tools, which
write but were never in that set) names the manual way to do the same thing:
the frontend file and a line of it that proves the path exists. A new write
tool with no entry here fails, and so does an entry whose proof has gone
missing from the file, which is how a manual path would silently disappear.

The audit this was written from (2026-09-27): every tool had a manual path
except moving notes between categories as one act, an explicit merge, a split
and a delete that names where the notes go; those are the Manage categories
panel (notes-list.js, `routes_categories.py`).
"""

from __future__ import annotations

from tests._app_js import frontend_text
from tests._help_text import help_chat_text, help_more_text

import json
import shutil
import subprocess
from pathlib import Path

import pytest

from tessellate.ai.tools import WRITE_TOOLS
from tests._js_scope import unwrapped

FRONTEND = Path(__file__).resolve().parents[1] / "frontend"

#: The category tools, in WRITE_TOOLS since round 9 (they were missing, so
#: the agent's claimed-a-save net and the skill list treated them as reads).
CATEGORY_TOOLS = {"create_category", "rename_category", "merge_categories", "delete_category"}

#: tool -> (file, a line that proves the manual path, where a person finds it)
MANUAL = {
    "create_note": ("capture-ask.js", 'apiJson("/entries", {', "Notes, Capture box"),
    "edit_note": ("note-edit-panels.js", "base_hash: base", "a note's Edit form"),
    "tag_note": ("note-edit-panels.js", 'tagField.className = "tag-field note-edit-tags";', "a note's Edit form, Tags"),
    "pin_note": ("entry-card.js", 'button.classList.add("favourite-btn");', "a note's star"),
    "link_notes": ("graph-canvas.js", 'method: "POST", body: JSON.stringify({ target', "Graph, drag one note to another"),
    "unlink_notes": ("graph.js", '/links/${edge.id}`, { method: "DELETE" })', "Graph, click a link, Remove"),
    "audit_link_reasons": ("entry-card.js", "/reason`", "a note's links, Edit reason"),
    "check_learned": ("settings-controls.js", 'apiJson("/learned/audit/run"', "Settings, What it learned, Check what it learned"),
    "delete_note": ("note-cards.js", "async function binNoteWithUndo(entry)", "a note's menu, Move to bin"),
    "restore_note": ("note-cards.js", '/restore`, { method: "POST"', "the recycle bin, Restore"),
    "set_reminder": ("shell-reminders.js", 'async function addReminder(text, dueValue', "Reminders, New reminder"),
    "complete_reminder": ("shell-reminders.js", "before, { done: checkbox.checked });", "Reminders, the tick box"),
    "rename_tag": ("tag-manager.js", '"/tags/rename",', "Manage tags, Rename"),
    "delete_tag": ("tag-manager.js", '"/tags/delete", { names }', "Manage tags, Remove from all notes"),
    "save_skill": ("skills.js", "async function saveSkillList(skills) {", "Settings, Skills, Save"),
    "delete_skill": ("skills.js", "async function saveSkillList(skills) {", "Settings, Skills, Delete"),
    "create_document": ("documents.js", 'apiJson("/documents", {', "Library, Documents, New"),
    "delete_document": ("documents.js", 'apiJson(`/documents/${doc.id}`, { method: "DELETE" });', "a document's menu, Delete"),
    "add_whiteboard_card": ("whiteboard.js", 'apiJson("/whiteboard/nodes", { method: "POST"', "a board, drag a note in from the sidebar's Notes tab"),
    "add_whiteboard_link": ("whiteboard.js", 'apiJson("/whiteboard/objects", { method: "POST"', "a board, draw a link between cards"),
    "generate_diagram": ("whiteboard.js", 'apiJson("/whiteboard/boards/generate", {', "Library, Boards & maps, Map from notes"),
    "create_mindmap": ("whiteboard.js", 'const board = await apiJson("/whiteboard/boards", {', "Library, Boards & maps, New, Mind map"),
    "map_from_note": ("entry-menu.js", "apiJson(`/whiteboard/maps/from-note/${entry.id}`", "a note's ⋮ menu, Make a mind map"),
    "add_map_node": ("whiteboard-map.js", "const created = await apiJson(`/whiteboard/boards/${boardId}/nodes`, {", "a mind map, Add child"),
    "link_map_nodes": ("whiteboard.js", 'apiJson("/whiteboard/objects", { method: "POST"', "a mind map, draw a cross-link"),
    "move_board_item": ("whiteboard-format.js", "async function wbFmtGeometry(axis, value)", "a board, drag an item, or the Format panel's X and Y"),
    "edit_board_item": ("whiteboard-format.js", 'on("wb-fmt-stroke", "change"', "a board, the context bar or the Format panel"),
    "delete_board_item": ("whiteboard.js", "function deleteWbSelection()", "a board, select an item, Delete"),
    "restore_board_item": ("whiteboard.js", "async function wbUndo()", "a board, Undo (Ctrl+Z)"),
    "add_board_shape": ("whiteboard-library.js", "async function wbLibPlace(entry, at = null", "a board, the Library's shapes and frames"),
    "place_library_item": ("whiteboard-library.js", "async function wbLibPlace(entry, at = null", "a board, the Library, click or drag a tile"),
    "create_category": ("categories-panel.js", "async function createCategoryFromPanel()", "Manage categories, New category"),
    "rename_category": ("categories-panel.js", "async function renameCategory(meta, currentName)", "a category's menu, Rename"),
    "merge_categories": ("categories-panel.js", "async function mergeCategoryFromPanel(meta)", "a category's menu, Merge into"),
    "delete_category": ("categories-panel.js", "async function deleteCategoryFromPanel(meta)", "a category's menu, Delete"),
    "move_notes": ("skills.js", "async function batchMove(category) {", "Select notes, move them to a category or another space"),
}


def test_every_write_tool_names_its_manual_path():
    missing = sorted((WRITE_TOOLS | CATEGORY_TOOLS) - set(MANUAL))
    assert not missing, (
        "These agent write tools have no manual path named in tests/test_manual_parity.py. "
        "Add the UI a person uses to do the same, or build it: " + ", ".join(missing)
    )


def test_every_named_manual_path_still_exists():
    gone = []
    for tool, (name, proof, where) in MANUAL.items():
        text = frontend_text(name)
        if proof not in text:
            gone.append(f"{tool}: {where} ({name} no longer has {proof!r})")
    assert not gone, "Manual paths that went missing:\n  " + "\n  ".join(gone)


def test_the_categories_panel_is_reachable_from_the_sidebar_the_menu_and_settings():
    html = (FRONTEND / "index.html").read_text(encoding="utf-8")
    #: The Settings button's listener is in settings-controls.js now.
    wiring = "\n".join((FRONTEND / "js" / name).read_text(encoding="utf-8") for name in ("wiring.js", "settings-controls.js"))
    # The panel moved to its own lazy piece (categories-panel.js).
    notes = "\n".join((FRONTEND / "js" / name).read_text(encoding="utf-8") for name in ("notes-list.js", "categories-panel.js"))
    assert 'id="manage-categories-btn"' in html and 'id="settings-manage-categories"' in html
    assert '$("manage-categories-btn").addEventListener("click", () => openManageCategories());' in wiring
    assert '$("settings-manage-categories").addEventListener("click", () => openManageCategories());' in wiring
    assert "kebabMenu(categoryMenuItems(meta), `Actions for ${category}`, { vertical: true })" in notes
    assert 'data-help-for", "manage-cat-help"' in notes
    # Every change offers undo.
    assert notes.count("offerCategoryUndo(") >= 5


def test_the_category_tools_count_as_writes():
    assert CATEGORY_TOOLS <= WRITE_TOOLS


def test_the_categories_panel_is_a_managed_list_with_the_reference_head():
    # The owner: "needs some ui redesign ... like the ai assistant panel".
    # The panel moved to its own lazy piece (categories-panel.js).
    notes = "\n".join((FRONTEND / "js" / name).read_text(encoding="utf-8") for name in ("notes-list.js", "categories-panel.js"))
    assert 'head.classList.add("dialog-head");' in notes
    # A grid since INBOX 433 (an option may not hold its ⋯; a grid cell may).
    assert 'list.setAttribute("role", "grid");' in notes and 'list.setAttribute("aria-multiselectable", "true");' in notes
    assert "function wireManageCategoryKeys(list, state, redraw)" in notes
    assert "function drawManageCategoryFooter(footer, state, redraw)" in notes
    assert 'filter.placeholder = "Filter categories";' in notes


#: The person's small tools (UI_MODERNISATION utilities row 5, Brief 89):
#: utility -> (file, a line that proves it, where a person finds it, its
#: Guide topic). Each has a way in, a line of help where it is offered, and
#: a Guide topic that says how to use it.
UTILITIES = {
    "statistics": ("statistics.js", 'helpBody.id = "stats-help";', "the heatmap's Statistics, the palette's Statistics", "statistics"),
    "timer": ("utility-tools.js", "function startUtilityTimer(minutes = 25)", "the palette's Start a timer, or timer 10 minutes", "timer"),
    "stopwatch": ("utility-tools.js", "function startStopwatch()", "the palette's Start a stopwatch", "timer"),
    #: INBOX 1551: the rows and the chip open one Clock panel (Timer, Stopwatch, Alarm).
    "open the clock": ("utility-tools.js", '$("status-timer").addEventListener("click", () => openClockPanel(utilityShown()?.kind', "the status bar's timer chip", "timer"),
    "clock panel": ("utility-tools.js", 'function openClockPanel(tab = "timer")', "the palette's Start a timer, Start a stopwatch and Set an alarm", "timer"),
    "alarm": ("settings-panes.js", 'id: "alarm", name: "Set an alarm"', "the palette's Set an alarm", "timer"),
    "no-model badge": ("reply-kit.js", "function replyByHelpPanel(kind)", "the From your notes badge", "ask-chat"),
    "calculator": ("reply-kit.js", 'function openCalculator(input = "", mode = "work", { target = null } = {})', "the palette's Calculator and equations, or /calc", "calculator"),
    "convert units": ("settings-panes.js", 'id: "convert", name: "Convert units"', "the palette's Convert units", "calculator"),
    "equation": ("math-editor.js", "function mathEditorMount({", "Calculator and equations, Equation tab, Alt+=, or /equation", "equation-editor"),
    "count words": ("utility-tools.js", "function countSelection(caught)", "the palette's Count words", "count-words"),
    "audio overview": ("studio.js", "function openStudio()", "the palette's Make an audio overview", "audio-overview"),
    "sync between computers": ("sync-folder.js", "async function openFolderSync()", "Settings, Import & export, Sync between computers, Sync through a folder", "folder-sync"),
    "live captions": ("captions.js", "async function startLiveCaptions(opts = {})", "the palette's Live captions", "live-captions"),
    "translate this": ("translate.js", "async function translateCaught(caught)", "the palette's Translate this", "translate-offline"),
    "check this computer": ("settings-controls.js", "async function runMaintenanceDoctor()", "Settings, About, Maintenance, Check this computer", "maintenance"),
    "reinstall on next start": ("settings-controls.js", "async function setMaintenanceReinstall(enabled)", "Settings, About, Maintenance, Reinstall on next start", "maintenance"),
    "launcher logs": ("settings-controls.js", 'apiJson("/system/open-logs-folder"', "Settings, About, Maintenance, Open the launcher logs", "maintenance"),
    "desktop shortcut": ("settings-controls.js", 'apiJson("/system/desktop-shortcut"', "Settings, About, Maintenance, Make a desktop shortcut", "maintenance"),
    "uninstall steps": ("settings-controls.js", "function openUninstallSteps()", "Settings, About, Maintenance, Uninstall", "maintenance"),
    "private chat": ("chat-private.js", "function chatPrivateToggle()", "Chat, the gear under the message box, Private chat", "chat-private"),
    "insert template": ("app-palette.js", "label: `ph:note-blank Insert template: ${template.name}`,", "the palette's insert template", "insert-template"),
}


def test_every_utility_has_its_way_in_and_a_guide_topic():
    from tessellate.ai import help_chat

    topics = {topic["id"] for topic in help_chat.HELP_TOPICS}
    gone = [
        f"{name}: {where}"
        for name, (file, proof, where, topic) in UTILITIES.items()
        if proof not in (FRONTEND / "js" / file).read_text(encoding="utf-8") or topic not in topics
    ]
    assert not gone, "Small tools that lost their way in or their Guide topic:\n  " + "\n  ".join(gone)
    #: Each palette row carries its one line of help (`about`), the palette's
    #: in-place help; the Statistics page and Settings, Templates also have a
    #: '?' popover (`data-help-for`).
    panes = (FRONTEND / "js" / "settings-panes.js").read_text(encoding="utf-8") + (FRONTEND / "js" / "app-features.js").read_text(encoding="utf-8")
    for label in ("Statistics", "Count words", "Live captions"):
        row = next((line for line in panes.splitlines() if 'label: "ph:' in line and f' {label}"' in line), "")
        assert "about:" in row, f"the palette's {label} row has no line of help"
    #: The timer and stopwatch rows come from `POPUP_TOOLS` (INBOX K27), whose
    #: entries carry the same `about`.
    tools = panes.split("const POPUP_TOOLS = [", 1)[1].split("\n];", 1)[0]
    for label in ("Start a timer", "Start a stopwatch"):
        entry = next((block for block in tools.split("\n  },") if f'name: "{label}"' in block), "")
        assert "about:" in entry, f"the palette's {label} row has no line of help"
    html = (FRONTEND / "index.html").read_text(encoding="utf-8")
    assert 'data-help-for="templates-help"' in html and "insert template" in html.split('id="templates-help"', 1)[1][:1200]


#: **The manual finds every control named here** (WORLD_CLASS_PLAN 25c, its
#: gate in 25.4). The manual (manual.js) is the Guide's topics as one page with
#: a search; every manual path above and every small tool's way in must be
#: found by that search, run as manual.js runs it (`manualWords`,
#: `manualMatches`) over what `GET /help/topics` serves. Six were not when
#: this was written (New category, Merge into, the timer chip, and three board
#: controls): their topics now name them.
_PROBE = """
const fs = require("fs"), vm = require("vm");
const ctx = {}; ctx.window = ctx; vm.createContext(ctx);
// manual.js is one closure (row 37a): this probe reads two private names by adding them to its export foot.
vm.runInContext(fs.readFileSync(process.argv[2], "utf8").replace("Object.assign(window, {", "Object.assign(window, { manualMatches, manualWords,"), ctx);
const topics = JSON.parse(fs.readFileSync(process.argv[3], "utf8")).groups.flatMap((g) => g.topics);
const out = {};
for (const q of JSON.parse(fs.readFileSync(process.argv[4], "utf8"))) {
  out[q] = topics.filter((t) => ctx.manualMatches(t, ctx.manualWords(q))).map((t) => t.id);
}
console.log(JSON.stringify(out));
"""


def test_the_manual_search_finds_every_named_control(tmp_path):
    from tessellate.ai import help_chat

    node = shutil.which("node")
    if not node:  # pragma: no cover - node is in the sandbox and in CI
        pytest.skip("node is not available")
    names = sorted({where for (_, _, where) in MANUAL.values()} | {row[2] for row in UTILITIES.values()})
    (tmp_path / "probe.js").write_text(_PROBE, encoding="utf-8")
    (tmp_path / "listing.json").write_text(json.dumps(help_chat.help_listing()), encoding="utf-8")
    (tmp_path / "names.json").write_text(json.dumps(names), encoding="utf-8")
    run = subprocess.run(
        [node, str(tmp_path / "probe.js"), str(FRONTEND / "js" / "manual.js"), str(tmp_path / "listing.json"), str(tmp_path / "names.json")],
        capture_output=True, text=True, timeout=60, check=False,
    )
    assert run.returncode == 0, run.stderr
    found = json.loads(run.stdout)
    missing = [name for name in names if not found.get(name)]
    assert not missing, "The manual's search finds nothing for: " + "; ".join(missing)


def test_the_manual_is_the_guides_topics_with_a_door_from_help_and_the_guide():
    manual = (FRONTEND / "js" / "manual.js").read_text(encoding="utf-8")
    #: One source: the Guide's own table, never a copy.
    assert 'apiJson("/help/topics")' in manual
    assert "window.print()" in manual and 'search.placeholder = "Search the manual";' in manual
    html = (FRONTEND / "index.html").read_text(encoding="utf-8")
    assert 'id="help-open-manual"' in html
    find = unwrapped((FRONTEND / "js" / "settings-find.js").read_text(encoding="utf-8"))
    assert '$("help-open-manual")?.addEventListener("click", () => lazyScript("/js/manual.js")' in find
    guide = (FRONTEND / "js" / "help-chat.js").read_text(encoding="utf-8")
    assert '"ph:book-open-text Open the manual"' in guide
    css = (FRONTEND / "css" / "manual-lazy.css").read_text(encoding="utf-8")
    assert "@media print" in css and "body.manual-print > :not(.manual-overlay)" in css


def test_the_open_packages_button_and_the_transcript_and_strip_controls_are_in_the_help():
    """Standing order 13: the Open Packages button on package notices (fixes1),
    the transcript's copy controls (C40) and the strip's dates switch (C36) are
    named in the Guide and in Settings or the Timeline's own help."""

    text = help_chat_text() + help_more_text()
    html = (FRONTEND / "index.html").read_text(encoding="utf-8")
    assert "Open Packages button" in text and "Open Packages button" in html
    assert "Shift-click picks a run of" in text
    assert "Dates beside the strip" in text and "Dates beside the strip" in html


def test_every_graph_options_section_has_a_question_mark_and_the_guide_says_so() -> None:
    """INBOX 1400: Physics, Show, Display, Filter, Time, Groups and Minimap each
    carry a '?' (`data-help-for`) in their head, and the Guide's graph topic
    tells a reader that the sections have one."""
    from tessellate.ai.help_chat import HELP_TOPICS

    html = (FRONTEND / "index.html").read_text(encoding="utf-8")
    for help_id in ("physics", "show", "display", "filter", "time", "groups", "minimap"):
        assert f'data-help-for="graph-{help_id}-help"' in html, f"Options has no '?' for {help_id}"
    body = str(next(t["body"] for t in HELP_TOPICS if t["id"] == "graph-options-help"))
    assert "beside its name" in body and "Minimap" in body


def test_the_graph_search_count_and_keys_are_in_the_guide() -> None:
    """Audit 1029 G11: the dock says "N matches", Enter and Shift+Enter walk
    them and Esc clears; the Guide's graph topic says so, and a reader can find
    it by asking."""
    from tessellate.ai.help_chat import HELP_TOPICS

    body = str(next(t["body"] for t in HELP_TOPICS if t["id"] == "graph"))
    assert "how many notes match" in body
    assert "Enter jumps to the next match" in body and "Shift and Enter" in body and "Esc clears the search" in body
    html = (FRONTEND / "index.html").read_text(encoding="utf-8")
    assert 'id="graph-search-count"' in html


def test_the_board_zoom_keys_are_in_the_keys_sheet_and_the_guide() -> None:
    """INBOX 1509: Ctrl or Cmd with + or - zooms the board about the selection
    (else the view's centre), Ctrl+0 fits and Ctrl+1 is 100%, as InDesign
    has it. The command table (the Keys sheet's rows), the menus and the
    Guide's keys topic all say the same keys."""
    from tessellate.ai.help_chat import HELP_TOPICS

    commands = (FRONTEND / "js" / "whiteboard-commands.js").read_text(encoding="utf-8")
    assert 'label: "Zoom to 100%", keys: "Ctrl+1"' in commands
    assert 'label: "Fit everything", keys: "Ctrl+0"' in commands
    assert '{ cmd: "zoom-fit", also: ["Shift+1"] }' in commands
    html = (FRONTEND / "index.html").read_text(encoding="utf-8")
    assert "<span>Zoom to 100%</span><kbd>Ctrl+1</kbd>" in html
    assert "<span>Fit everything</span><kbd>Ctrl+0</kbd>" in html
    body = str(next(t["body"] for t in HELP_TOPICS if t["id"] == "whiteboard-controls"))
    assert "Ctrl+0 fits all" in body and "Ctrl+1 is 100%" in body
    assert "zoom the board about the selection's centre" in body


def test_check_what_it_learned_is_in_the_guide_the_panel_help_and_the_skill():
    """Decision 68: the bar's button, the Guide's learned topic, the panel's own
    help and the skill say the same thing and use the button's own words."""
    from tessellate.ai import help_chat, skills

    topic = next(t for t in help_chat.HELP_TOPICS if t["id"] == "learned")
    for words in ("Check what it learned", "retires", "Undo", "flags", "Background tasks", "joke, quote, fiction, test or draft"):
        assert words in topic["body"] or words.lower() in topic["body"].lower(), words
    html = (FRONTEND / "index.html").read_text(encoding="utf-8")
    help_body = html[html.index('id="learned-help"') :][:3000]
    assert '"Check what it learned"' in help_body and "Undo" in help_body
    assert "Check what it learned</button>" in html
    assert any(item["name"] == "Check what it learned" for item in skills.BUILTIN_SKILLS)


def test_the_desktop_companion_row_is_named_as_a_this_computer_setting():
    """INBOX 1631 (the owner: "the atlas desktop comnpanion toggle is gone??"), which
    moves 1530 (b): the row shows on the computer Tessellate runs on, in the desktop
    window or a browser tab, and takes effect while the desktop app runs; another device
    has none. Every place that names it says so."""
    from tessellate.ai import help_chat

    named = [t for t in help_chat.HELP_TOPICS if "Show the companion on the desktop" in t["body"]]
    assert named, "no Guide topic names the row any more"
    for topic in named:
        meta = help_chat.TOPIC_META.get(topic["id"], {})
        body = topic["body"].lower()
        assert "on the computer tessellate runs on" in body and "while the desktop app runs" in body, topic["id"]
        assert meta.get("path", "").startswith("On the computer Tessellate runs on"), topic["id"]
    html = (FRONTEND / "index.html").read_text(encoding="utf-8")
    popover = html.split('id="desktop-companion-help"', 1)[1].split("</div>", 1)[0]
    assert "While the desktop app runs" in popover
    # BACKLOG 16 O4: the see-through figure that walks, and the words for it, in both places.
    # Windows' own setting is named ("animation effects"): "reduce motion" was the app's old
    # switch, which test_motion_resolved keeps out of the pages.
    # The owner's report of 2026-11-04 moved this: Atlas floats (others walk), can be thrown,
    # hangs from the top and peeks from behind the taskbar, in both places.
    # The roam request of the same day: window tops, the switch and a reminder's card.
    # Intent moved (INBOX 1670, 15:40Z): "sits still for minutes at a time" became "alive in place" (it stays put but
    # breathes, blinks and sways its tail); both places still say how long it stays and that it is not bobbing.
    # Intent moved (INBOX 1683 u, 2026-11-05): the wander mix is now walk, run, edge wrap and portal with a rare puff
    # (was 90% walk), so both places name those modes instead of "mostly on foot or gliding".
    for words in ("floats like a wind spirit", "sleeps", "thrown", "hangs from the top", "peeks up from behind the taskbar", "animation effects",
                  "climbs onto the top of a window", "Roam over windows", "a card when a reminder falls due",
                  "alive in place", "walking, running", "out at one edge and in at the other", "through a portal", "swings down or lets go with a start",
                  "right-click for Companion (Atlas masculine or feminine, your own or a saved one, summoned once)"):
        assert words in " ".join(popover.split()), words
    for topic in named:
        flat = " ".join(topic["body"].split())
        for words in ("floats like a wind spirit", "thrown", "hangs from the top", "peeks up from behind the taskbar", "animation effects",
                      "climbs onto the top of a window", "Roam over windows", "a card to click",
                      "alive in place", "walking, running", "out at one edge and in at the other", "through a portal", "swings down or lets go with a start",
                      #: Changed on purpose (INBOX 1684): every companion shows on the desk, so "the rest show in the app only" is gone.
                      "Right-click it for Companion (Atlas masculine or feminine, your own or a saved one, summoned once)"):
            assert words in flat, (topic["id"], words)
            assert len(topic["body"]) < 1900, topic["id"]
    settings = (FRONTEND / "js" / "settings.js").read_text(encoding="utf-8")
    assert 'const onThisComputer = isDesktop || (await healthFacts())?.this_computer !== false;' in settings
    assert '$("desktop-companion-row")?.classList.toggle("hidden", !onThisComputer);' in settings
    note = settings.split('let companionNote = document.getElementById("desktop-companion-note");', 1)[1][:600]
    assert "while the desktop app runs" in note


def test_the_diagram_blocks_keys_menu_and_views_are_in_the_guide() -> None:
    """1546 P2: what the block pane does by pointer it does by keys and a menu, and the
    Guide's `diagram-blocks` topic says each of them in the words the controls use. The
    topic is in the Documents group, the pane's keys are the ones it names, and the Read
    button reads Blocks for a diagram."""
    from tessellate.ai.help_chat import HELP_TOPICS
    from tessellate.ai.help_topics_more import HELP_GROUPS, TOPIC_META

    # Intent moved (INBOX 1661 i): the views Canvas and Blocks are now named Picture and List, so the words checked are theirs.
    body = str(next(t["body"] for t in HELP_TOPICS if t["id"] == "diagram-blocks"))
    for words in ("List gives", "Source and Split", "Ctrl+Z", "press its arrow", "joins them", "inside",
                  "Enter renames", "N adds", "G adds a group", "J joins", "Delete removes", "Alt+Up and Alt+Down",
                  "Alt+Right nests", "Alt+Left lifts", "long press", "shape swatch"):
        assert words in body, words
    assert "diagram-blocks" in TOPIC_META
    assert "diagram-blocks" in dict(HELP_GROUPS)["Documents and code"]
    # The toolbar's Expand and Collapse (the owner, 2026-11-11), said in the controls' words in the Guide and the dock's popover.
    from tessellate.ai.help_chat import HELP_TOPICS as TOPICS

    builder = str(next(t["body"] for t in TOPICS if t["id"] == "diagram-lines"))
    assert "Expand, at the end of the toolbar of a diagram in a document" in builder and "Collapse or Escape returns to the document" in builder
    index = (Path(__file__).resolve().parents[1] / "frontend" / "index.html").read_text(encoding="utf-8")
    assert "Expand, at the end of the diagram's toolbar" in index and "Collapse or Escape returns to the document" in index
    builder = (FRONTEND / "js" / "diagram-builder.js").read_text(encoding="utf-8")
    for key in ("Insert", "Delete", "Backspace", "ContextMenu"):
        assert key in builder, key
    docs = (FRONTEND / "js" / "documents.js").read_text(encoding="utf-8")
    assert "Picture" in docs and "A diagram has Picture, List, Split and Source." in docs


def test_the_diagram_add_library_and_connect_to_are_in_the_guide_in_the_controls_words() -> None:
    """INBOX 1594: the Add library's four groups, its hints, the sheet on a phone, Connect to... on a
    block (pick one, or type a new name), a connector's row and the C key, said in the Guide's
    `diagram-blocks` topic in the words the pane carries."""
    from tessellate.ai.help_chat import HELP_TOPICS

    body = str(next(t["body"] for t in HELP_TOPICS if t["id"] == "diagram-blocks"))
    # 1661 D2: the tile strip became one Add split (the last shape, and a menu of every shape with its key).
    for words in ("Add shows the last shape you used", "press its arrow", "for every shape and its key", "Connect to... on a block", "type a new name to make it",
                  "Start to Next and its label", "C or J joins"):
        assert words in body, words
    js = FRONTEND / "js"
    builder = (js / "diagram-builder.js").read_text(encoding="utf-8")
    library = (js / "diagram-library.js").read_text(encoding="utf-8")
    joins = (js / "diagram-joins.js").read_text(encoding="utf-8")
    for label in ("Steps", "Decisions", "Start and end", "Notes and groups"):
        assert f'["{label}", [' in library, label
    # 1679 slice 6: the row shows "to Next" under its block; the full "from to" sentence is its aria-label.
    assert "Connect to…" in builder and "Connector from ${from} to ${to}" in builder and "A new block" in joins
    assert 'c: () => key[0] !== "k" && joinPick(S, key)' in builder


def test_the_diagram_suggestions_are_in_the_guide_in_the_controls_words() -> None:
    """1546 P3: Suggest and its three ways in, the ghosts and their keys, and the dimmed
    Describe it, each said in the words the controls carry."""
    from tessellate.ai.help_chat import HELP_TOPICS

    body = str(next(t["body"] for t in HELP_TOPICS if t["id"] == "diagram-blocks"))
    for words in ("Suggest", "Templates", "From my notes", "Describe it", "Use this template", "dimmed",
                  "ghosts", "Tab takes", "Shift+Tab lets it go", "Enter adds", "Escape drops", "Ctrl+Z undoes the whole addition"):
        assert words in body, words
    builder = (FRONTEND / "js" / "diagram-builder.js").read_text(encoding="utf-8")
    suggest = (FRONTEND / "js" / "diagram-suggest.js").read_text(encoding="utf-8")
    for label in ("Templates", "From my notes", "Describe it", "Suggest"):
        assert label in builder + suggest, label
    assert "Use this template" in suggest


def test_the_diagram_kinds_are_in_the_guide_in_the_controls_words() -> None:
    """1546 P4: the mind map, timeline and sequence panes, the letter on each bar button, the
    two things a suggestion of another kind does, and a source the blocks cannot read, each
    said in the Guide's `diagram-kinds` topic (its own, so `diagram-blocks` keeps its room) in
    the words the pane carries."""
    from tessellate.ai.help_chat import HELP_TOPICS
    from tessellate.ai.help_topics_more import HELP_GROUPS, TOPIC_META

    body = str(next(t["body"] for t in HELP_TOPICS if t["id"] == "diagram-kinds"))
    for words in ("flowcharts, mind maps, timelines and sequence diagrams", "a branch and a leaf (B and N)",
                  "a section, a period and an event (S, P and E)",
                  # 1679 m: the tiles grew by Parallel, Critical and Break (U, C, B); the sentence still lists every tile with its key.
                  "actor, participant, message, reply, async, lost, note, loop, alt, opt, parallel, critical and break (A, P, M, R, Y, X, T, L, G, O, U, C and B)",
                  "opens in Source with its picture", "of another kind says so and is left out", "replaces a blank one",
                  # 1661 k: the four kind buttons became one Kind menu in the Title row.
                  "Kind, in the Title row (first in the toolbar elsewhere), is a menu",
                  # 1661 l: a sequence diagram is edited on its picture (diagram-seq-canvas.js); dgpic-1109: a mind map and a timeline too.
                  "On a sequence, mind map or timeline picture a press picks a part, a double press, Enter or F2 renames it"):
        assert words in body, words
    assert "diagram-kinds" in TOPIC_META and "diagram-kinds" in dict(HELP_GROUPS)["Documents and code"]
    assert "next topic" in str(next(t["body"] for t in HELP_TOPICS if t["id"] == "diagram-blocks"))
    kinds = (FRONTEND / "js" / "diagram-kinds.js").read_text(encoding="utf-8")
    for label in ("Branch", "Leaf", "Section", "Period", "Event", "Actor", "Participant", "Message", "Reply", "Async", "Lost", "Note", "Loop", "Alt", "Opt"):
        assert f'name: "{label}"' in kinds, label
    for letters in ('key: "b"', 'key: "n"', 'key: "s"', 'key: "p"', 'key: "e"', 'key: "m"', 'key: "r"', 'key: "y"', 'key: "x"', 'key: "t"', 'key: "l"', 'key: "g"', 'key: "o"', 'key: "a"'):
        assert letters in kinds, letters


def test_the_diagram_dialog_the_reply_action_and_the_exports_are_in_the_guide_in_the_controls_words() -> None:
    """1546 P5: Edit as blocks on a Live figure, the board's double-click, Open as a diagram under a reply,
    `![[name]]`, the ... menu's four rows and Source beside Cancel, each said in the `diagram-elsewhere`
    topic in the words the controls carry."""
    from tessellate.ai.help_chat import HELP_TOPICS
    from tessellate.ai.help_topics_more import HELP_GROUPS, TOPIC_META

    body = str(next(t["body"] for t in HELP_TOPICS if t["id"] == "diagram-elsewhere"))
    for words in ("Edit as blocks", "double-click a diagram object", "Open as a diagram", "![[name]]", "Done", "Cancel, Escape and the X",
                  "SVG", "PNG", "Copy as Mermaid", "Copy as SVG", "Source"):
        assert words in body, words
    assert "diagram-elsewhere" in TOPIC_META and "diagram-elsewhere" in dict(HELP_GROUPS)["Documents and code"]
    embed = (FRONTEND / "js" / "diagram-embed.js").read_text(encoding="utf-8")
    builder = (FRONTEND / "js" / "diagram-builder.js").read_text(encoding="utf-8")
    draw = (FRONTEND / "js" / "mermaid-draw.js").read_text(encoding="utf-8")
    mermaid = (FRONTEND / "js" / "documents-mermaid.js").read_text(encoding="utf-8")
    for label in ("Save as SVG", "Save as PNG", "Copy as Mermaid", "Copy as SVG"):
        assert label in builder, label
    assert '"Edit as blocks"' in mermaid and '"Open as a diagram"' in draw
    #: R9c (1621 D4, D7): Save to Library on a fence and in the menu, the swap offer, and the chat card.
    for words in ("Save to Library", "replace the fence with a link", "link a board's diagram", "Attach a Library diagram to Chat"):
        assert words in body, words
    assert 'smallButton("ph:books", "Save to Library"' in mermaid and "Save to Library" in embed
    for label in ('"Done"', '"Cancel"', '"Source"', '"List"'):
        assert label in embed, label


def test_the_diagram_picture_zoom_is_in_the_guide_in_the_controls_words() -> None:
    """INBOX 1614: the corner bar's four buttons, Ctrl+wheel, the pinch and the arrow keys, said in the
    `diagram-blocks` topic in the words diagram-view.js carries."""
    from tessellate.ai.help_chat import HELP_TOPICS

    body = str(next(t["body"] for t in HELP_TOPICS if t["id"] == "diagram-blocks"))
    for words in ("corner bar zooms (Zoom in, Zoom out, Fit)", "percentage is typeable", "100% is the drawing's own size", "Ctrl+wheel", "a pinch", "arrow keys pan"):
        assert words in body, words
    view = (FRONTEND / "js" / "diagram-view.js").read_text(encoding="utf-8")
    for label in ('"Zoom in"', '"Zoom out"', '"Fit"', 'label: "Zoom percent"', "event.ctrlKey", "ArrowLeft"):
        assert label in view, label


def test_the_diagram_divider_direction_caption_and_walkthrough_are_in_the_guide_in_the_controls_words() -> None:
    """DOCUMENTS_PLAN 22.4 R3 and R4: the divider, the Direction caption and the three empty-state steps."""
    from tessellate.ai.help_chat import HELP_TOPICS

    body = str(next(t["body"] for t in HELP_TOPICS if t["id"] == "diagram-blocks"))
    assert len(body) < 1900
    for words in ("A divider sizes the blocks and the picture", "Shift for more", "Direction (a menu) turns the flow", "Add a shape, Name it, Connect it"):
        assert words in body, words
    js = FRONTEND / "js"
    # 1661 D2: the caption over four arrows became one button that says "Direction: Down" (diagram-bar.js).
    assert "Direction: ${WORD[dir]}" in (js / "diagram-bar.js").read_text(encoding="utf-8")
    steps = (js / "diagram-steps.js").read_text(encoding="utf-8")
    for label in ('"Add a shape"', '"Name it"', '"Connect it"'):
        assert label in steps, label
    assert "Resize the blocks list" in (js / "diagram-split.js").read_text(encoding="utf-8")


def test_the_diagram_multiselect_is_in_the_guide_in_the_controls_words() -> None:
    """DOCUMENTS_PLAN 22.4 R5: Shift and Ctrl click, the bar's actions and the grip that carries the picked blocks."""
    from tessellate.ai.help_chat import HELP_TOPICS

    body = str(next(t["body"] for t in HELP_TOPICS if t["id"] == "diagram-blocks"))
    assert len(body) < 1900
    for words in ("Shift+click picks a range", "Ctrl+click adds one", "Duplicate", "Box them", "any picked grip moves all"):
        assert words in body, words
    multi = (FRONTEND / "js" / "diagram-multi.js").read_text(encoding="utf-8")
    for label in ('tool("trash", "Delete"', 'tool("copy", "Duplicate"', 'tool("diamond", "Shape"', 'tool("stack", "Box them"', '"Select all"', '"Clear"'):
        assert label in multi, label


def test_confirmed_patterns_are_managed_where_the_guide_and_the_help_say():
    """B9 (the owner: "also is there a way to edit or managed confirmed
    patterns??"): the Patterns topic, the memory topic and What it remembers'
    own help name the group and its three actions in the controls' words."""
    from tessellate.ai import help_chat

    topics = {t["id"]: t["body"] for t in help_chat.HELP_TOPICS}
    for words in ("Edit", "Not right", "Remove", "Undo", "Settings, What it remembers", "its tag still reaches it"):
        assert words in topics["patterns"], words
    assert "patterns you confirmed" in topics["memory"]
    html = (FRONTEND / "index.html").read_text(encoding="utf-8")
    help_body = html[html.index('id="memory-help"') :][:2400]
    for words in ("Confirmed patterns", "Edit", "Remove", "Not right", "Undo", "its tag still"):
        assert words in help_body, words
    menu = (FRONTEND / "js" / "confirmed-patterns.js").read_text(encoding="utf-8")
    for label in ('"ph:pencil-simple Edit"', 'item.verdict === "dismiss").label', '"ph:trash Remove"'):
        assert label in menu, label


def test_the_diagram_tab_chain_the_starter_and_the_keys_chip_are_in_the_guide() -> None:
    """1107 DD-3 and DD-7: Tab and Shift+Tab on a box, the New diagram window's starter and Clear, the Keys button and `?`,
    each said in the Guide in the words the controls carry (standing order 13)."""
    from tessellate.ai.help_chat import HELP_TOPICS

    elsewhere = str(next(t["body"] for t in HELP_TOPICS if t["id"] == "diagram-elsewhere"))
    for words in ("Tab adds a joined box", "Shift+Tab selects its source", "F6 leaves the blocks", "Ctrl+Enter keeps the diagram", "three-box starter", "Clear, in the ... menu", "The Keys button", "? outside a text field", "one Add button"):
        assert words in elsewhere, words
    embed = (FRONTEND / "js" / "diagram-embed.js").read_text(encoding="utf-8")
    style = (FRONTEND / "js" / "diagram-style.js").read_text(encoding="utf-8")
    assert '"ph:keyboard Keys"' in embed and '"ph:eraser Clear"' in embed and 'data-help-for", "dgm-dialog-help"' in embed
    assert '["Tab", "Add a box after the last one, joined to it"]' in style
    # 1107 DD-8a: the picture's arrows pick a box, the Keys sheet and the Guide say so.
    assert '["Arrows on the picture", "Pick the box in that direction"]' in style
    diagram = str(next(t["body"] for t in HELP_TOPICS if t["id"] == "diagram-blocks"))
    assert "Shift+arrow keys pan" in diagram
    # 1107 DD-5: the Source pane's keys, in the Keys sheet and the Guide.
    assert '["Tab, Shift + Tab in Source", "Indent, take the indent back"]' in style and '["Esc in Source", "Leave the text for the views"]' in style
    reading = str(next(t["body"] for t in HELP_TOPICS if t["id"] == "diagram-reading"))
    kinds = str(next(t["body"] for t in HELP_TOPICS if t["id"] == "diagram-kinds"))
    assert "Hand-drawn look, in the ... menu" in kinds and "Clean look takes it back" in kinds
    assert '"ph:pencil-line Hand-drawn look"' in embed and '"ph:rectangle Clean look"' in embed
    for words in ("In Source, Tab indents and Shift+Tab takes it back", "Escape leaves the text", "a red line number", "Title names the document Done makes (blank dates it)"):
        assert words in reading, words
    assert "In the picture an arrow key picks the box that way, reading aloud its name and arrows, and Shift with an arrow moves the picture" in reading


def test_the_diagram_panel_folds_are_in_the_guide_in_the_controls_words() -> None:
    """1661 m: `[` and `]` fold the list and the picture to a rail (diagram-split.js), and a kind's list is the phone's sheet."""
    from tessellate.ai.help_chat import HELP_TOPICS

    body = str(next(t["body"] for t in HELP_TOPICS if t["id"] == "diagram-reading"))
    assert "[ and ] fold the list and the picture to a rail" in body and "Blocks list opens the list as a sheet" in body
    split = (FRONTEND / "js" / "diagram-split.js").read_text(encoding="utf-8")
    assert 'right: ["picture", "]"' in split and 'left: ["list", "["' in split


# --- the one-line lead on every topic (INBOX 1612) ----------------------------
#: The owner's decision: "yes to a one-line summary at the top of every topic
#: (the copy rule's one line, the rest under it)". Each lead is one sentence
#: saying what the feature is for, drawn first in Settings, Help and the
#: manual, and kept out of the prompt (help_leads.py says why).

_LEAD_MAX = 90


def _listed_topics() -> list[dict]:
    from tessellate.ai.help_chat import help_listing

    return [topic for group in help_listing()["groups"] for topic in group["topics"]]


def _lead_faults(lead: str, title: str) -> list[str]:
    import re

    words = lead.split()
    return [
        reason
        for reason, bad in (
            ("over 90 characters", len(lead) > _LEAD_MAX),
            ("no full stop at the end", not lead.endswith(".")),
            ("more than one sentence", bool(re.search(r"[.!?;]\s", lead))),
            ("an em-dash or en-dash", "\u2014" in lead or "\u2013" in lead),
            ("an exclamation mark", "!" in lead),
            ("not starting with a capital", not lead[:1].isupper()),
            ("title case", sum(w[:1].isupper() for w in words[1:]) * 2 > len(words)),
            ("the title again", lead.rstrip(".").casefold() == title.casefold()),
        )
        if bad
    ]


def test_every_listed_topic_has_a_one_sentence_lead():
    faults = {}
    for topic in _listed_topics():
        lead = topic.get("lead", "")
        found = ["no lead"] if not lead else _lead_faults(lead, topic["title"])
        if found:
            faults[topic["id"]] = found
    assert not faults, faults


def test_no_two_leads_are_the_same_and_none_is_left_over():
    from tessellate.ai.help_leads import TOPIC_LEADS

    listed = {topic["id"] for topic in _listed_topics()}
    assert set(TOPIC_LEADS) <= listed, sorted(set(TOPIC_LEADS) - listed)
    leads = [lead.casefold() for lead in TOPIC_LEADS.values()]
    assert len(leads) == len(set(leads)), sorted({lead for lead in leads if leads.count(lead) > 1})


def test_the_lead_is_never_prompt_text(monkeypatch):
    from tessellate.ai import help_chat
    from tessellate.ai.help_leads import TOPIC_LEADS

    assert not any("lead" in topic for topic in help_chat.HELP_TOPICS)
    #: Every topic grounds this one turn, so no lead can hide behind retrieval.
    monkeypatch.setattr(help_chat, "topics_for", lambda question, tab: list(help_chat.HELP_TOPICS))
    messages, topics = help_chat._prompt_for("how do I sort my notes", None, None, None)
    sent = "\n".join(message["content"] for message in messages)
    assert len(topics) == len(help_chat.HELP_TOPICS)
    assert [lead for lead in TOPIC_LEADS.values() if lead in sent] == []
    #: A body no longer opens on its label ("Graph keys and controls."), so the
    #: title names the surface for the model, as `help_block_for` does.
    assert [t["id"] for t in help_chat.HELP_TOPICS if f"- {help_chat.topic_title(t)}: " not in sent] == []


def test_settings_help_and_the_manual_draw_and_search_the_lead():
    # Both scripts are lazy, so they are read as files, not from app_js_text.
    find = unwrapped((FRONTEND / "js" / "settings-find.js").read_text(encoding="utf-8"))
    manual = (FRONTEND / "js" / "manual.js").read_text(encoding="utf-8")
    assert 'lead.className = "help-topic-lead"' in find
    assert "details.append(summary, lead," in find
    assert "[topic.title, topic.lead," in find
    assert 'lead.className = "manual-lead"' in manual
    assert "${topic.lead}" in manual


def test_the_sequence_picture_drags_are_in_the_guide_and_the_dialog_help() -> None:
    """INBOX 1661 (l): a head dragged sideways, a drag between lifelines and the + at a gap, said in the Guide's
    `diagram-kinds` topic and the New diagram window's About this editor."""
    from tessellate.ai.help_chat import HELP_TOPICS

    body = str(next(t["body"] for t in HELP_TOPICS if t["id"] == "diagram-kinds"))
    # Review finding 4: the + is pointer-only, so the Guide names the keyboard way to the same gap (the block list's Insert key).
    for words in ("a head dragged sideways reorders", "a drag from one lifeline to another adds a message", "the + at a gap opens the Add menu",
                  "from the keyboard, Insert in the blocks list adds a step under the selected one"):
        assert words in body, words
    embed = (FRONTEND / "js" / "diagram-embed.js").read_text(encoding="utf-8")
    assert "double press a part to name it, drag a head to reorder and drag from one lifeline to another to add a message. The shelf in the picture's corner adds a block by a press or a drag" in embed
    blocks = str(next(t["body"] for t in HELP_TOPICS if t["id"] == "diagram-blocks"))
    assert "Press or drag a block from the shelf onto the picture" in blocks
    # dgmleft-1108: the drop joins the nearest box and Kind asks first, in the Guide and in the dialog's help, under the 1900 limit.
    assert "onto the picture to join the nearest box" in blocks and "Kind asks before it clears blocks" in blocks and len(blocks) < 1900
    assert "Kind asks before it clears a diagram that has blocks." in embed


def test_the_diagram_ask_suggestions_and_versions_are_in_the_guide_in_the_controls_words() -> None:
    """dgai-1110: what the model can do to a diagram (the ops) a person asks for by hand in the Ask box, and the Guide's
    `diagram-ai` topic names each control as diagram-ai.js labels it, in the Documents group, under the 1,900 limit."""
    from tessellate.ai.help_chat import HELP_TOPICS
    from tessellate.ai.help_topics_more import HELP_GROUPS, TOPIC_META

    body = str(next(t["body"] for t in HELP_TOPICS if t["id"] == "diagram-ai"))
    ai = (FRONTEND / "js" / "diagram-ai.js").read_text(encoding="utf-8")
    for words, control in (("Apply", "ph:check Apply"), ("Discard", "ph:x Discard"), ("Suggestions", "Suggestions ("),
                           ("Versions...", "ph:clock-counter-clockwise Versions…"), ("Compare", "ph:git-diff Compare"),
                           ("Restore", 'label: "Restore"'), ("add Refund after In stock? No", "add Refund after In stock? No")):
        assert words in body and control in ai, words
    assert "no model a rule" in body and "Ctrl+Z" in body and len(body) < 1900
    assert "diagram-ai" in TOPIC_META and "diagram-ai" in dict(HELP_GROUPS)["Documents and code"]


def test_the_viewer_page_number_is_a_typeable_field_in_the_guide() -> None:
    """INBOX 1694 (b): the lightbox's 'Page 3 of 12' is a value field; the `image-viewer` topic says so in the words the
    control carries (its name, its text, the jump)."""
    from tessellate.ai.help_chat import HELP_TOPICS

    body = str(next(t["body"] for t in HELP_TOPICS if t["id"] == "image-viewer"))
    for words in ("'Page 3 of 12' is a field too", "type 7 and Enter", "pinch to zoom"):
        assert words in body, words
    view = (FRONTEND / "js" / "lightbox-view.js").read_text(encoding="utf-8")
    for label in ('label: "Page number"', "Page ${v} of ${docPageCount}", "setDocPage(n - 1)"):
        assert label in view, label


def test_the_answer_offers_and_the_pool_count_line_are_in_the_guide() -> None:
    """Standing order 13 (composer batch 2): the offer link at the end of an answer, a typed yes taking
    it up in Chat, and the story's "That tells N of the M" line are named in the Ask and Chat topic."""
    from tessellate.ai.help_chat import HELP_TOPICS

    body = " ".join(str(t["body"]) for t in HELP_TOPICS if "Save it as a checklist note" in str(t["body"]))
    for phrase in ("Save it as a checklist note", "Start a list of", "typing yes", "no thanks drops it", "That tells five of the twelve"):
        assert phrase in body, phrase


def test_the_connector_row_and_the_suggestions_fold_are_in_the_guide_in_the_controls_words() -> None:
    """INBOX 1771: a connector row's words go to the block it points at and its ... opens the menu; Suggestions turns its arrow
    and numbers blocks that share a name in one row. Said in the Guide, in the words the pane carries."""
    from tessellate.ai.help_chat import HELP_TOPICS

    builder_help = str(next(t["body"] for t in HELP_TOPICS if t["id"] == "diagram-builder"))
    ai_help = str(next(t["body"] for t in HELP_TOPICS if t["id"] == "diagram-ai"))
    assert "A connector row's words (or Enter) go to its block; its ... opens the menu." in builder_help
    assert "opens like a fold (its arrow turns)" in ai_help and "one row numbers them" in ai_help
    js = FRONTEND / "js"
    assert "Go to ${to}" in (js / "diagram-builder.js").read_text(encoding="utf-8")
    assert "blocks say ${group[0].text}." in (js / "diagram-ai.js").read_text(encoding="utf-8")


def test_map_build_up_and_level_stepping_are_in_the_keys_sheet_the_menus_and_the_guide() -> None:
    """INBOX 1774: Alt+= and Alt+- step the levels (the Keys sheet, the palette and
    the map menus), and Build up branch by branch presents the map from the
    centre out; the Guide says both in the controls' words."""
    commands = (FRONTEND / "js" / "whiteboard-commands.js").read_text(encoding="utf-8")
    assert 'keys: ["Alt+=", "Alt+-"]' in commands
    html = (FRONTEND / "index.html").read_text(encoding="utf-8")
    assert "<span>Build up branch by branch</span>" in html
    text = help_chat_text() + help_more_text()
    assert "Alt+= and Alt+- show one more or one less level" in text
    assert "Build up branch by branch shows the centre, then each branch a level at a time" in text
    assert "End shows the whole map to take it apart" in text


def test_the_format_panels_connection_point_rows_are_in_the_guide_in_the_controls_words() -> None:
    """L-whiteboard-13: Format, Position and size lists a shape's connection points (pick, On outline, nudge, add, remove); the
    Guide says so in the words the rows carry, and the rows are in the page."""
    from tessellate.ai.help_chat import HELP_TOPICS

    body = " ".join(str(t["body"]) for t in HELP_TOPICS if "Format, Position and size lists a shape's connection points" in str(t["body"]))
    for words in ("On outline", "nudge it by pixels", "add one or remove the chosen one", "one Undo step", "draw.io file's points"):
        assert words in body, words
    html = (FRONTEND / "index.html").read_text(encoding="utf-8")
    for words in ("Connection point", "On outline", "Add a connection point", "Remove the chosen connection point", "Nudge"):
        assert words in html, words


def test_the_csv_grid_is_in_the_guide_in_the_controls_words() -> None:
    """L328: Grid, its keys and the four row and column buttons are named where the Run help lives."""
    from tessellate.ai import help_topics_more_mid as topics

    text = " ".join(str(topic) for topic in vars(topics).values() if isinstance(topic, (list, dict, str)))
    for word in ("Grid edits a CSV or TSV as cells", "Add and Delete row and column", "Ctrl+Z undoes"):
        assert word in text, word
    js = (Path(__file__).resolve().parents[1] / "frontend" / "js" / "documents-csvgrid.js").read_text(encoding="utf-8")
    for label in ("Add row", "Add column", "Delete row", "Delete column"):
        assert f'"{label}"' in js, label
