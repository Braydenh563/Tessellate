"""One attachment card for every attached file (INBOX 440 (2)).

The owner: "all of the attachment cards ui and ux and utility need a massive
redesign and upgrade." The screenshot was a note's picture in the edit form: a
white thumbnail, a bold name cut to "Gary The Moss Mons...", and three bare
glyphs under it (a sparkle, a pencil, an x) floating in empty space. Nothing
said what kind of file it was, how big, or when it came; there was no open,
no download and no rename.

Measured before the change (scratchpad/ui-sweeps/attachcards.js), one note
holding a picture and a PDF in its text and a picture, a PDF and a text file
attached to it drew **five different shapes**: an inline thumbnail with a
round x, a file card with a save button, a bare thumbnail with an x in its
corner, and two chips stretched to the thumbnail's height. The Capture box
drew the PDF twice (once as an icon-less chip, once as a file card), and the
edit form's PDF chip had no glyph at all, because its class was set without
`ph `.

So: one builder, `attachmentCard` (notes-list.js), one stylesheet block
(`.att-card`), one menu (`kebabMenu`), and the work behind the menu in a lazy
piece (attachment-actions.js), because the boot scripts were 79 bytes under
their gzip total when this started. These tests hold that shape.
"""

from __future__ import annotations

import io
import re
from pathlib import Path

from tests._app_js import LAZY_PIECES, app_js_files

from tessellate.entry import manager

ROOT = Path(__file__).resolve().parent.parent
FRONTEND = ROOT / "frontend"
CSS = sorted((FRONTEND / "css").glob("*.css"))
APP_JS = (FRONTEND / "js" / "app.js").read_text(encoding="utf-8")
NOTES_LIST = (FRONTEND / "js" / "notes-list.js").read_text(encoding="utf-8")
NOTE_CARDS = (FRONTEND / "js" / "note-cards.js").read_text(encoding="utf-8")
SETTINGS_WIRING = (FRONTEND / "js" / "settings-wiring.js").read_text(encoding="utf-8")
ACTIONS = FRONTEND / "js" / "attachment-actions.js"
DESIGN = (ROOT / "docs" / "DESIGN.md").read_text(encoding="utf-8")


def _all_js() -> str:
    return "\n".join(p.read_text(encoding="utf-8") for p in sorted((FRONTEND / "js").glob("*.js")))


def _boot_js() -> str:
    return "\n".join(p.read_text(encoding="utf-8") for p in app_js_files())


def _css() -> str:
    return "\n".join(p.read_text(encoding="utf-8") for p in CSS)


def _function_body(text: str, name: str) -> str:
    start = re.search(rf"^(?:async )?function {name}\(", text, re.M)
    assert start, f"{name} is not defined"
    end = re.search(r"^}", text[start.end():], re.M)
    return text[start.start(): start.end() + end.end()]


# --- the backend facts the card states ----------------------------------------


def _note_with_file(client, session, name="lecture.pdf", body=b"%PDF-1.4 fake"):
    entry = manager.create_entry(session, "a note that carries a file")
    session.commit()
    response = client.post(
        f"/entries/{entry.id}/files",
        files={"file": (name, io.BytesIO(body), "application/pdf")},
    )
    assert response.status_code in (200, 201), response.text
    return entry


def test_an_attachment_says_when_it_was_added(ai_client, session):
    """The card's facts line is kind, size and the day it came. The note's
    payload carried the first two and not the third, though the row has
    always had a `created_at`."""
    entry = _note_with_file(ai_client, session)
    attachment = ai_client.get(f"/entries/{entry.id}").json()["attachments"][0]
    assert attachment["size"] == len(b"%PDF-1.4 fake")
    assert re.match(r"\d{4}-\d{2}-\d{2}T", attachment["created_at"]), attachment


def test_an_upload_says_how_big_it_is(ai_client):
    """A file in a note's text is a `/media` upload, which the card asks
    about by its stored name (`GET /media/meta/{filename}`, the lightbox's
    own lookup). It said when, and not how big."""
    uploaded = ai_client.post(
        "/media/upload", files={"file": ("shot.png", b"\x89PNG\r\n\x1a\n1234", "image/png")}
    ).json()
    stored = uploaded["url"].rsplit("/", 1)[-1]
    body = ai_client.get(f"/media/meta/{stored}").json()
    assert body["size"] == len(b"\x89PNG\r\n\x1a\n1234")
    assert body["created_at"]


# --- one builder, used everywhere ------------------------------------------------


def test_there_is_one_card_builder_and_every_surface_uses_it():
    assert len(re.findall(r"^function attachmentCard\(", _all_js(), re.M)) == 1
    assert "function attachmentCard(" in NOTES_LIST
    # fileCard is kept as the name the read-only surfaces call (documents,
    # the graph's panel, the timeline), and it is the card.
    assert "return attachmentCard(" in _function_body(NOTES_LIST, "fileCard")
    # The note card's attached files, the edit form and Capture.
    assert "attachmentCard(" in _function_body(NOTE_CARDS, "renderAttachmentCards")
    assert "attachmentCard(" in _function_body(SETTINGS_WIRING, "renderEntryAttachmentChips")


def test_the_old_shapes_are_gone():
    """The five shapes the before measurement found, by the names that drew
    them. The chat composer's own `.attachment-chip` is a different thing
    (a file waiting to be sent, not one attached to a note) and stays."""
    js = _all_js()
    for gone in (
        "entry-attachment-caption-btn",
        "entry-attachment-caption-edit-btn",
        "entry-attachment-chip-actions",
        '"file-card"',
        "file-card-open",
        "file-card-save",
        "file-card-remove",
        "file-strip",
    ):
        assert gone not in js, f"{gone} is still drawn somewhere"
    assert "entry-file-strip" not in (FRONTEND / "index.html").read_text(encoding="utf-8")
    css = _css()
    for gone in (".file-card", ".file-strip", ".entry-attachment-chip-actions"):
        assert gone not in css, f"{gone} is still styled"


def test_the_card_is_one_button_then_one_menu():
    body = _function_body(NOTES_LIST, "attachmentCard")
    # The primary action is a real button that opens the file.
    assert 'createElement("button")' in body
    assert '"att-card-open"' in body
    # The secondary actions are the app's menu, never a row of glyphs.
    assert "kebabMenu(" in body
    assert body.count("icon-only") == 0, "a bare glyph button crept back onto the card"
    # Grouped, because the menu runs past five rows (DESIGN.md).
    assert "group" in body
    # The name is the full name, with a tooltip.
    assert '"att-card-name"' in body
    assert ".title = label" in body
    # The facts line is the shared one (DESIGN.md, one line of facts).
    assert '"library-file-meta att-card-meta"' in body


def test_the_menu_offers_what_the_owner_listed():
    body = _function_body(NOTES_LIST, "attachmentCard")
    for label in ("Open", "Download", "Rename", "Describe with AI", "Annotate", "Copy as a link", "Remove"):
        assert label in body, f"the menu has no {label}"
    # Describe is disabled with a reason when the AI is off, never hidden.
    assert "aiIsOff()" in body
    assert "AI_OFFLINE_HINT" in body


def test_the_work_behind_the_menu_is_a_lazy_piece():
    """The boot scripts were 79 bytes under their gzip total. Everything a
    click does (the player, rename, describe, annotate, copy, remove with
    undo) loads on the first click instead."""
    assert ACTIONS.exists()
    assert "attachment-actions.js" in LAZY_PIECES
    assert re.search(r'attachments:\s*\["/js/attachment-actions\.js"\]', APP_JS)
    entry_points = re.search(r"const LAZY_ENTRY_POINTS = \{(.*?)\n\};", APP_JS, re.S).group(1)
    assert re.search(r'attachments:\s*\["attachmentAction"\]', entry_points)
    actions = ACTIONS.read_text(encoding="utf-8")
    #: Indented once the file is wrapped in one closure (ranked row 37a).
    assert re.search(r"^\s*async function attachmentAction\(", actions, re.M)
    assert "function attachmentAction(" not in _boot_js()


def test_every_action_the_menu_names_is_handled():
    body = _function_body(NOTES_LIST, "attachmentCard")
    named = set(re.findall(r'add\("([a-z]+)"', body))
    assert named >= {"open", "download", "rename", "describe", "caption", "annotate", "copy", "remove"}
    actions = ACTIONS.read_text(encoding="utf-8")
    for name in named:
        assert re.search(rf"\b{name}: ", actions) or f'"{name}"' in actions, f"{name} has no handler"


def test_removing_from_the_text_can_be_undone_and_never_deletes_a_file_in_use():
    """The old remove deleted the upload the moment the x was pressed, in the
    edit form too, where cancelling the edit left the saved note pointing at a
    file that was gone, and in Capture for a picture taken from the Library,
    which other notes may also show. Now: the text goes, an Undo is offered,
    and the bytes go only once the undo has lapsed and nothing uses them."""
    actions = ACTIONS.read_text(encoding="utf-8")
    #: `offerUndo` (status.js) is the undo contract's one toast: an Undo button
    #: and a step on the undo stack (INBOX 898), where this once called
    #: `toastAction` by hand.
    assert "offerUndo(" in actions
    assert "used_by" in actions and "usage_incomplete" in actions


def test_audio_and_video_open_in_a_player():
    actions = ACTIONS.read_text(encoding="utf-8")
    assert 'createElement(kind === "video" ? "video" : "audio")' in actions
    assert ".controls = true" in actions


# --- the stylesheet ---------------------------------------------------------------


def _rule(css: str, selector: str) -> str:
    match = re.search(rf"(?:^|\}})\s*{re.escape(selector)}\s*\{{([^}}]*)\}}", css, re.M)
    assert match, f"no rule for {selector}"
    return match.group(1)


def test_the_name_wraps_to_two_lines_rather_than_cutting_mid_word():
    css = _css()
    name = _rule(css, ".att-card-name")
    assert "-webkit-line-clamp: 2" in name
    assert "white-space: nowrap" not in name


def test_the_menu_button_meets_the_touch_floor():
    css = _css()
    more = _rule(css, ".att-card-more")
    assert "min-width: var(--target-min)" in more
    assert "min-height: var(--target-min)" in more


def test_the_card_keeps_the_list_conventions():
    """A right-click or a long-press on a card opens its own menu, F2 renames
    (DESIGN.md: the keys and clicks a list is expected to keep)."""
    hosts = re.search(r"const ROW_MENU_HOSTS = \[(.*?)\]", (FRONTEND / "js" / "navigation.js").read_text(encoding="utf-8"), re.S)
    assert '".att-card"' in hosts.group(1)


def test_the_recipe_is_written_down():
    assert "attachmentCard(" in DESIGN
    assert "tests/test_attachment_cards.py" in DESIGN
