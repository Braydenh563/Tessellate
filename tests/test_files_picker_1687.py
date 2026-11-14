"""INBOX 1687: the chat Attach panel and the Library picker list the Library's
own uploads (MediaUpload) beside a note's attachments, and a thing staged by a
tray drop is the panel's ticked row (one staged list, not a second set)."""

from __future__ import annotations

from tests._app_js import frontend_text
import re

from tests._objmove_node import JS, needs_node, run


def _rows_source() -> str:
    """The shared list's source, `pickLibraryItemDialog.fileRows = async ... };`."""
    text = (JS / "library-pick.js").read_text(encoding="utf-8")
    match = re.search(r"^ *pickLibraryItemDialog\.fileRows = .*?^ *\};\n", text, re.S | re.M)
    assert match
    return "var pickLibraryItemDialog = {};\n" + match.group(0)


def _function(file: str, name: str) -> str:
    """Source of one top-level function, up to its closing brace at column 0."""
    text = (JS / file).read_text(encoding="utf-8")
    match = re.search(rf"^( *)(?:async )?function {name}\b.*?^\1\}}\n", text, re.S | re.M)
    assert match, name
    return match.group(0)


@needs_node
def test_the_files_list_holds_uploads_and_attachments_without_pictures() -> None:
    body = _rows_source() + """
    var apiPagedList = async (path) => path === "/media"
      ? [{ id: 5, original_name: "report.pdf", url: "/media/a.pdf", used_by: [] },
         { id: 6, original_name: "photo.png", url: "/media/b.png" },
         { id: 7, original_name: "sealed.pdf", url: "/media/c.pdf", usage_incomplete: true, used_by: [] }]
      : [{ id: 5, original_name: "note.docx", mime: "application/x" }, { id: 8, original_name: "pic", mime: "image/png" }];
    pickLibraryItemDialog.fileRows().then((rows) => __out(rows.map((r) => [r.store, r.id, r.mediaId || null])));
    """
    # The same id 5 in both tables stays two rows (an upload's row id is m5); the picture and the sealed upload are left out.
    assert run([], body) == [["file", 5, None], ["media", "m5", 5]]


@needs_node
def test_a_failed_read_of_both_tables_is_null_not_empty() -> None:
    body = _rows_source() + """
    var apiPagedList = async () => { throw new Error("down"); };
    pickLibraryItemDialog.fileRows().then((rows) => __out(rows));
    """
    assert run([], body) is None


def test_the_library_picker_and_the_chat_panel_share_that_list() -> None:
    pick = (JS / "library-pick.js").read_text(encoding="utf-8")
    attach = (JS / "attach-to.js").read_text(encoding="utf-8")
    assert "pickLibraryItemDialog.fileRows(" in pick and "pickLibraryItemDialog.fileRows(" in attach
    assert "Files you upload or attach to notes show up here." in (JS / "selection.js").read_text(encoding="utf-8")
    # A map's reference names a note's attachment only: it asks for no uploads.
    assert "noUploads: true" in frontend_text("whiteboard-map.js")


@needs_node
def test_a_tray_drop_is_the_ticked_row_and_ids_never_cross_tables() -> None:
    staged = _function("chat-attach.js", "attachLibraryFile")
    body = f"""
    var attachedFiles = [], MAX_CHAT_FILES = 4, renderFileAttachments = () => {{}}, announce = () => {{}};
    {staged}
    // What a tray drop of a Library upload does (obj-ref.js), then the panel's own test (`isOn`) for each row.
    OBJ_STAGE.upload({{ id: 5, title: "report.pdf" }});
    const ticked = (row) => attachedFiles.some((f) => f.id === row.id);
    __out([ticked({{ id: "m5" }}), ticked({{ id: 5 }}), OBJ_STAGED.upload({{ id: 5 }}), OBJ_STAGED.file({{ id: 5 }})]);
    """
    # The tray-staged upload lights its own row only, and "already attached" is true for it alone.
    assert run(["obj-ref.js"], body) == [True, False, True, False]
