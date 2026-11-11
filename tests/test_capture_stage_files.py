"""Quick capture takes every file the chat takes, in the app and in the desktop companion.

The owner: "can images be uploaded to the desktop companion quick notes?? and are they staged
temporarily until actually filed like they are in the app?? ... make sure that any staged
attachment file or image can be deleted as a chip", then "check if it can take all the accepted
files and possible attachments as well not just images".

One list (`ATTACH_ACCEPT`, attach-accept.js), one staging file (capture-stage.js) loaded by both
windows, one chip (`attachmentChip`), one attachment path (`POST /entries/{id}/files`).
"""

from __future__ import annotations

import io
import re
from pathlib import Path

from tessellate.api.routes_files import ATTACHMENT_SUFFIXES
from tessellate.core import docview
from tessellate.entry import manager

ROOT = Path(__file__).resolve().parent.parent
JS = ROOT / "frontend" / "js"


def _js(name: str) -> str:
    return (JS / name).read_text(encoding="utf-8")


def _body(source: str, name: str) -> str:
    start = source.index(f"function {name}(")
    nxt = re.search(r"\n\s*(?:async )?function \w+\(", source[start + 10 :])
    return source[start : start + 10 + nxt.start()] if nxt else source[start:]


STAGE = _js("capture-stage.js")
CARD = _js("capture-card.js")
DESK = _js("desk-companion.js")
ENV = _js("desk-env.js")


def _accept() -> list[str]:
    return re.search(r'const ATTACH_ACCEPT = "([^"]+)"', _js("attach-accept.js")).group(1).split(",")


def test_there_is_one_accept_list_and_chat_and_capture_both_read_it():
    assert len(re.findall(r"ATTACH_ACCEPT = ", "".join(p.read_text(encoding="utf-8") for p in JS.glob("*.js")))) == 1
    assert '$("chat-image-input").accept = ATTACH_ACCEPT' in _js("wiring.js")
    assert "/js/attach-accept.js" in _body(CARD, "openCaptureCard")
    html = (ROOT / "frontend" / "index.html").read_text(encoding="utf-8")
    assert not re.search(r'id="chat-image-input"[^>]*accept=', html), "a second copy of the list"
    assert "accept: ATTACH_ACCEPT" in _body(STAGE, "mountCaptureStage")
    assert "image/*" in _accept()


def test_every_type_the_picker_offers_is_one_a_note_will_attach():
    suffixes = {token for token in _accept() if token.startswith(".")}
    assert suffixes <= set(ATTACHMENT_SUFFIXES), sorted(suffixes - set(ATTACHMENT_SUFFIXES))
    assert set(docview.VIEWABLE_SUFFIXES) <= set(ATTACHMENT_SUFFIXES)


def test_a_note_takes_the_files_the_chat_picker_added_to_the_allowlist(ai_client, session):
    entry = manager.create_entry(session, "a note with code and notes")
    session.commit()
    for name in ("tool.py", "config.toml", "book.epub", "run.log", "page.mk"):
        response = ai_client.post(f"/entries/{entry.id}/files", files={"file": (name, io.BytesIO(b"x = 1\n"), "text/plain")})
        assert response.status_code in (200, 201), (name, response.text)


def test_nothing_is_sent_before_save():
    add = _body(STAGE, "addCaptureFiles")
    for sending in ("apiJson(", "fetch(", "FormData"):
        assert sending not in add, sending
    assert "URL.createObjectURL" in add
    # the two sends are the two functions Save calls, and nothing else in the file sends
    sends = [m.start() for m in re.finditer(r"apiJson\(", STAGE)]
    assert len(sends) == 2
    assert all(
        "uploadCapturePictures" in _owner(STAGE, at) or "attachCaptureFiles" in _owner(STAGE, at) for at in sends
    )


def _owner(source: str, at: int) -> str:
    return re.findall(r"function (\w+)\(", source[:at])[-1]


def test_a_staged_file_is_the_chats_chip_with_a_remove_that_drops_it():
    chip = _body(STAGE, "captureFileChip")
    assert "attachmentChip(" in chip and "onRemove" in chip and "removeTitle" in chip
    remove = _body(STAGE, "removeCaptureFile")
    assert "captureCard.files.filter" in remove and "renderCaptureStage()" in remove
    assert "captureCard.files.map(captureFileChip)" in _body(STAGE, "renderCaptureStage")
    # pictures keep their thumbnails and their own x
    assert "captureCard.pictures.map(captureThumb)" in _body(STAGE, "renderCaptureStage")


def test_paste_and_drop_stage_files():
    mount = _body(STAGE, "mountCaptureStage")
    assert 'addEventListener("paste"' in mount and 'addEventListener("drop"' in mount
    assert 'includes("Files")' in mount  # dragover must allow the drop
    accepts = _body(STAGE, "captureAccepts")
    assert "isImageFile(file)" in accepts and "ATTACH_ACCEPT.split" in accepts


def test_files_attach_through_the_notes_own_path_after_the_note_has_an_id():
    attach = _body(STAGE, "attachCaptureFiles")
    assert "`/entries/${entryId}/files`" in attach
    # one that went is no longer staged, so a retry sends only the rest
    assert "captureCard.files = captureCard.files.filter" in attach and "failed.push(" in attach
    save = _body(CARD, "saveCaptureCard")
    assert "online: captureCard.files.length > 0" in save
    assert "retryCaptureFiles()" in save and "captureCard.made = { result, draft }" in save
    assert "if (captureCard.made) return retryCaptureFiles();" in save
    # a note of files alone is named by them: the server refuses an empty note
    assert "file.name" in save


def test_a_failed_save_keeps_everything_staged_and_offers_try_again():
    save = _body(CARD, "saveCaptureCard")
    assert "Press Save to try again." in save and 'button.textContent = "Try again"' in save
    # the catch never resets the card; reset is only reached by a finished save
    assert "resetCaptureCard" not in save[save.index("catch (error)") : save.index("finally")]
    retry = _body(CARD, "retryCaptureFiles")
    assert "Press Save to try again." in retry and "attach" in retry
    assert 'captureCardField("save").textContent = "Save"' in _body(CARD, "resetCaptureCard")
    note = _js("quick-note.js")
    assert "online || !noteServerGone(error)" in note, "a note that needs its id is never held for later"


def test_a_finished_save_and_a_reset_revoke_every_object_url():
    discard = _body(STAGE, "discardCaptureStage")
    assert "URL.revokeObjectURL(picture.preview)" in discard
    assert "captureCard.files = []" in discard and "captureCard.made = null" in discard
    assert "discardCaptureStage()" in _body(CARD, "resetCaptureCard")


def test_the_desk_window_loads_the_staging_and_not_the_apps_pickers():
    assert '"/js/att-chip.js", "/js/capture-card.js"' in ENV
    assert 'file === "/js/capture-card-more.js" ? Promise.resolve(false)' in ENV
    assert "/js/capture-stage.js" in _body(CARD, "openCaptureCard") or "capture-stage.js" in CARD
    # the stage's three needs, answered by this window
    for name in ("apiJson: deskApiJson", "authHeaders:"):
        assert name in DESK, name
    assert "window.setLabel" in ENV
    html = (ROOT / "frontend" / "desktop-companion.html").read_text(encoding="utf-8")
    assert "capture-stage" not in html and "att-chip" not in html, "the desk page boot stays light"


def test_closing_the_desk_note_discards_what_it_held_back():
    assert "captureCard.discardOnClose = true" in DESK
    close = _body(CARD, "closeCaptureCard")
    assert "captureCard.discardOnClose" in close and "discardCaptureStage()" in close
    show = _body(DESK, "show")
    assert 'state === "note" && next !== "note"' in show and "discardCaptureStage" in show
