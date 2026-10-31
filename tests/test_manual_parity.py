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

import json
import shutil
import subprocess
from pathlib import Path

import pytest

from tessellate.ai.tools import WRITE_TOOLS

FRONTEND = Path(__file__).resolve().parents[1] / "frontend"

#: The category tools, in WRITE_TOOLS since round 9 (they were missing, so
#: the agent's claimed-a-save net and the skill list treated them as reads).
CATEGORY_TOOLS = {"create_category", "rename_category", "merge_categories", "delete_category"}

#: tool -> (file, a line that proves the manual path, where a person finds it)
MANUAL = {
    "create_note": ("capture-ask.js", 'apiJson("/entries", {', "Notes, Capture box"),
    "edit_note": ("note-edit-panels.js", "base_hash: base", "a note's Edit form"),
    "tag_note": ("note-edit-panels.js", 'tagField.className = "tag-field note-edit-tags";', "a note's Edit form, Tags"),
    "pin_note": ("note-cards.js", 'button.classList.add("favourite-btn");', "a note's star"),
    "link_notes": ("graph-canvas.js", 'method: "POST", body: JSON.stringify({ target', "Graph, drag one note to another"),
    "unlink_notes": ("graph.js", '/links/${edge.id}`, { method: "DELETE" })', "Graph, click a link, Remove"),
    "audit_link_reasons": ("note-cards.js", "/reason`", "a note's links, Edit reason"),
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
    "map_from_note": ("menus.js", "apiJson(`/whiteboard/maps/from-note/${entry.id}`", "a note's ⋮ menu, Make a mind map"),
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
        text = (FRONTEND / "js" / name).read_text(encoding="utf-8")
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
    "stop the clock": ("utility-tools.js", '$("status-timer").addEventListener("click", stopUtilityClock);', "the status bar's timer chip", "timer"),
    "no-model badge": ("reply-kit.js", "function replyByHelpPanel(kind)", "the From your notes badge", "ask-chat"),
    "calculator": ("reply-kit.js", 'function openCalculator(input = "", mode = "work")', "the palette's Calculator, or /calc", "calculator"),
    "convert units": ("settings-panes.js", 'id: "convert", name: "Convert units"', "the palette's Convert units", "calculator"),
    "equation": ("settings-panes.js", 'id: "equation", name: "Equation"', "the palette's Equation, Alt+=, or /equation", "equation-editor"),
    "count words": ("utility-tools.js", "function countSelection(caught)", "the palette's Count words", "count-words"),
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
    panes = (FRONTEND / "js" / "settings-panes.js").read_text(encoding="utf-8")
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
const ctx = {}; vm.createContext(ctx);
vm.runInContext(fs.readFileSync(process.argv[2], "utf8"), ctx);
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
    find = (FRONTEND / "js" / "settings-find.js").read_text(encoding="utf-8")
    assert '$("help-open-manual")?.addEventListener("click", () => lazyScript("/js/manual.js")' in find
    guide = (FRONTEND / "js" / "help-chat.js").read_text(encoding="utf-8")
    assert '"ph:book-open-text Open the manual"' in guide
    css = (FRONTEND / "css" / "manual-lazy.css").read_text(encoding="utf-8")
    assert "@media print" in css and "body.manual-print > :not(.manual-overlay)" in css


def test_the_open_packages_button_and_the_transcript_and_strip_controls_are_in_the_help():
    """Standing order 13: the Open Packages button on package notices (fixes1),
    the transcript's copy controls (C40) and the strip's dates switch (C36) are
    named in the Guide and in Settings or the Timeline's own help."""
    from tessellate.ai import help_chat, help_topics_more

    text = Path(help_chat.__file__).read_text(encoding="utf-8") + Path(help_topics_more.__file__).read_text(encoding="utf-8")
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
