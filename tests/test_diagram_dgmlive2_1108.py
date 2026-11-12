"""What the second real-browser run of the diagram surfaces (dgmlive2 1108) found; these read the source for what has to stay true."""

from __future__ import annotations

from pathlib import Path

from tests import _js_scope

ROOT = Path(__file__).resolve().parents[1]
JS = ROOT / "frontend" / "js"
LIBRARY = (JS / "library.js").read_text(encoding="utf-8")
DOCUMENTS = (JS / "documents.js").read_text(encoding="utf-8")


def test_a_library_reload_hands_focus_back_to_the_grid_when_the_row_it_held_is_redrawn():
    """Measured in Chromium: rename, archive or delete from a row's ⋯ by keyboard left document.activeElement on BODY."""
    body = LIBRARY.split("async function loadLibrary(")[1].split("\n}\n")[0]
    assert "const held = grid.contains(document.activeElement);" in body
    assert "if (held && !grid.contains(document.activeElement)) {" in body
    assert "ensureLibraryGridStop(grid);" in body


def test_undoing_a_document_act_redraws_the_library_it_was_made_from():
    """Measured in Chromium: Undo on 'Moved to the bin' restored the diagram on the server and the Library grid kept the row gone until the tab was left and re-entered."""
    assert 'document.addEventListener("documents-undone"' in LIBRARY
    for name in ("deleteDocumentWithUndo", "renameDocumentWithUndo", "archiveDocumentWithUndo"):
        body = DOCUMENTS.split(f"async function {name}(")[1].split("\n}\n")[0]
        assert 'new Event("documents-undone")' in body, name


def test_an_archived_diagram_is_listed_by_the_library_once_as_shelved(client, session):
    """Measured in Chromium: Archive on a diagram's row toasted and shelved it, and the row stayed in Everything because /library listed it as a diagram as well as shelved."""
    from tessellate.core.database import Document

    kept = Document(title="Kept flow", content="flowchart TD\n A-->B\n", file_type="mmd")
    gone = Document(title="Shelved flow", content="flowchart TD\n A-->B\n", file_type="mmd")
    session.add_all([kept, gone])
    session.commit()
    archived = client.put(f"/documents/{gone.id}/archive")
    assert archived.status_code == 200

    items = client.get("/library").json()["items"]
    titles = [(i["kind"], i["title"]) for i in items if i["title"] in ("Kept flow", "Shelved flow")]
    assert ("diagram", "Kept flow") in titles
    assert ("shelved", "Shelved flow") in titles
    assert ("diagram", "Shelved flow") not in titles


def test_a_row_pressed_in_the_embed_dialogs_more_menu_leaves_focus_on_its_new_opener():
    """Measured in Chromium: 'Hand-drawn look' remounted the pane and document.activeElement went to BODY inside a modal dialog."""
    embed = (JS / "diagram-embed.js").read_text(encoding="utf-8")
    body = embed.split("const show = () => {")[1].split("\n    const view = ")[0]
    assert 'document.activeElement?.closest?.(".dgm-more")' in body
    assert 'host.querySelector(".dgm-more button")?.focus(' in body


def test_the_second_press_of_a_double_click_on_an_embed_does_not_select_or_press_the_page_it_opened():
    """Measured in Chromium: a double click on the embed opened the diagram once, and the second press landed on the new page and left a 297-character selection."""
    draw = _js_scope.unwrapped((JS / "mermaid-draw.js").read_text(encoding="utf-8"))
    body = draw.split("mermaidFill.embed = async")[1].split("\n};\n")[0]
    assert "const calm = () =>" in body
    assert 'for (const name of ["mousedown", "click"]) document.addEventListener(name, stop, true);' in body
    assert "event.detail > 1" in body
    assert "calm();\n      openDocument(doc.id);\n    });\n    box.append(open);" in body


def test_the_purpose_line_keeps_room_for_the_three_lines_it_wraps_to_so_the_first_hover_moves_nothing():
    """Measured in Chromium: the purpose wrapped to 3 lines (50.4px) and a hovered control's words to 2 (33.6px); the list rose 17px between a first press going down and coming up, and that click missed its button."""
    css = (ROOT / "frontend" / "css" / "diagram-lazy.css").read_text(encoding="utf-8")
    rule = css[css.index(".dgm-purpose {") :].split("}")[0]
    assert "min-block-size: calc(3 * 1.4em);" in rule


def test_the_apps_undo_and_redo_chords_wait_while_a_dialog_is_in_front():
    """Measured in Chromium: with 'Switch to mind map?' open, Ctrl+Z undid the last rename behind it (F 'Done' back to 'Step') and the dialog stayed."""
    wiring = (JS / "settings-wiring.js").read_text(encoding="utf-8")
    assert 'const behindModal = () => [...document.querySelectorAll(".modal-overlay:not(#settings-modal), dialog[open]")].some((m) => m.getClientRects().length);' in wiring
    assert 'if ((id === "undo" || id === "redo") && behindModal()) continue;' in wiring
    assert '=== "y" && !behindModal()' in wiring
