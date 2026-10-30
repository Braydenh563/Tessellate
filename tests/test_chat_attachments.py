"""Attachments belong to the message, not just to the composer (§ chat).

Reported directly:

    "images and files uploaded into a chat conversation arent rendered with
     the chat messages, the captions arent viewable under the image cards…
     and they arent previewable or quick navigatable to their stored location
     in the library or documents etc or viewable in a better environment"

All of it was true, and the cause was one missing half: the ids were stored
(the model needs them, and `media_gc` needs them) and nothing on the read path
ever turned an id back into a picture. A bubble cannot render what the server
does not send.
"""

from __future__ import annotations

from tests._app_js import app_js_text


def _conversation_with(client, **turn):
    body = {"question": "what is this?", "answer": "a picture", **turn}
    return client.post("/conversations", json=body).json()


def _upload(client, name="pic.png"):
    tiny = (
        b"\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR\x00\x00\x00\x01\x00\x00\x00\x01"
        b"\x08\x06\x00\x00\x00\x1f\x15\xc4\x89\x00\x00\x00\nIDATx\x9cc\x00\x01"
        b"\x00\x00\x05\x00\x01\r\n-\xb4\x00\x00\x00\x00IEND\xaeB`\x82"
    )
    return client.post("/media/upload", files={"file": (name, tiny, "image/png")}).json()


def test_an_attached_image_comes_back_renderable(client):
    """Ids are what gets stored; a url, a name and the readings are what a
    bubble needs. Resolved once for the whole conversation on read rather than
    one request per attachment per reopen."""
    upload = _upload(client)
    conversation = _conversation_with(client, image_media_ids=[upload["id"]])

    full = client.get(f"/conversations/{conversation['id']}").json()
    user = full["messages"][0]
    assert user["image_media_ids"] == [upload["id"]]
    attachment = user["attachments"][0]
    assert attachment["kind"] == "image"
    assert attachment["url"] == upload["url"]
    assert attachment["name"] == "pic.png"
    # Present even when empty, so the renderer never has to null-check.
    assert attachment["caption"] == ""
    assert attachment["text"] == ""


def test_the_caption_and_the_reading_travel_with_the_picture(client):
    """"the captions arent viewable under the image cards", they are the
    reason to show a caption at all, and the same two readings the Library
    tile shows, so one picture reads the same way everywhere."""
    from tessellate.core.database import MediaUpload

    upload = _upload(client)
    from tessellate.core import deps

    with deps.get_db().session() as session:
        row = session.get(MediaUpload, upload["id"])
        row.caption = "A leafy pokemon by a pond"
        row.vision_ocr_text = "24-12-2018"
        session.commit()

    conversation = _conversation_with(client, image_media_ids=[upload["id"]])
    attachment = client.get(f"/conversations/{conversation['id']}").json()["messages"][0][
        "attachments"
    ][0]
    assert attachment["caption"] == "A leafy pokemon by a pond"
    assert attachment["text"] == "24-12-2018"


def test_a_vision_reading_wins_over_the_offline_one(client):
    """Same precedence the Library tile uses, the AI reading is the one the
    app keeps working with, and showing both in one line would read as one
    doubled transcription."""
    from tessellate.core.database import MediaUpload

    upload = _upload(client)
    from tessellate.core import deps

    with deps.get_db().session() as session:
        row = session.get(MediaUpload, upload["id"])
        row.ocr_text = "offline"
        row.vision_ocr_text = "by the model"
        session.commit()
    conversation = _conversation_with(client, image_media_ids=[upload["id"]])
    text = client.get(f"/conversations/{conversation['id']}").json()["messages"][0][
        "attachments"
    ][0]["text"]
    assert text == "by the model"


def test_an_attached_document_comes_back_as_a_way_to_open_it(client):
    """A non-image dropped on the chat is imported into Documents. There is
    nothing to preview inline, its text may be a hundred pages, so the
    navigation *is* the render."""
    document = client.post("/documents", json={"title": "Assignment brief"}).json()
    conversation = _conversation_with(client, document_ids=[document["id"]])

    user = client.get(f"/conversations/{conversation['id']}").json()["messages"][0]
    assert user["attachments"] == [
        {"id": document["id"], "kind": "document", "name": "Assignment brief"}
    ]


def test_both_kinds_ride_on_one_message(client):
    """A person attaching a photo and a spreadsheet in one go is doing one
    thing, and the app must not treat it as two."""
    upload = _upload(client)
    document = client.post("/documents", json={"title": "Notes"}).json()
    conversation = _conversation_with(
        client, image_media_ids=[upload["id"]], document_ids=[document["id"]]
    )
    kinds = [
        a["kind"]
        for a in client.get(f"/conversations/{conversation['id']}").json()["messages"][0][
            "attachments"
        ]
    ]
    assert kinds == ["image", "document"]


def test_a_deleted_attachment_is_absent_rather_than_an_error(client):
    """An upload can be deleted from the Library long after the message that
    carried it. The bubble then shows one fewer thumbnail, which is what
    happened before any of this existed, it must not 404 the conversation."""
    upload = _upload(client)
    conversation = _conversation_with(client, image_media_ids=[upload["id"]])
    client.delete(f"/media/{upload['id']}")

    full = client.get(f"/conversations/{conversation['id']}")
    assert full.status_code == 200
    assert "attachments" not in full.json()["messages"][0]


def test_a_message_with_nothing_attached_gains_no_key(client):
    """Absent, not an empty list: every existing turn in every saved chat
    would otherwise grow a key, and the renderer already treats missing as
    nothing to draw."""
    conversation = _conversation_with(client)
    assert "attachments" not in client.get(f"/conversations/{conversation['id']}").json()[
        "messages"
    ][0]


# --- the frontend half, which no Python test can execute ------------------------


def test_the_bubble_renders_the_strip_on_both_paths():
    """A live send and a reopen have to draw the same thing, and they used to
    draw nothing and nothing. Asserted against the source because there is no
    DOM here: the same reason test_frontend_ids.py exists."""
    source = app_js_text()
    assert "function chatAttachmentStrip(" in source
    # The reopen path.
    assert 'addBubble("user", message.content, message.attachments)' in source
    # The live path, which builds its cards from the composer before it is
    # cleared: after that there is nothing left to build them from.
    assert "sentAttachmentCards" in source
    assert 'addBubble("user", opts.displayText || question, sentAttachmentCards)' in source


def test_the_strip_offers_a_preview_and_a_way_back():
    source = app_js_text()
    strip = source.split("function chatAttachmentStrip(")[1].split("\nfunction addBubble(")[0]
    assert "openLightbox(" in strip, "the thumbnail must open the full-size view"
    assert "figcaption" in strip, "the caption has to be visible under the card"
    # `focusLibraryFile`, not a literal `switchTab("library")`, since the
    # Library's media view became two sub-tabs (Images and Files) and which
    # one to open depends on the file. The property this line is really
    # asserting, that the card offers a way back to the Library, is
    # unchanged; the helper is where the three steps now live, and it is
    # tested by being the only route any of the three call sites take.
    assert "focusLibraryFile(" in strip, "the card must offer a way back to the Library"
    assert 'switchTab("documents")' in strip and "openDocument(" in strip


def test_the_ids_are_persisted_by_the_send_path():
    source = app_js_text()
    assert source.count("document_ids: sentDocuments") == 2, (
        "both save paths: the partial written mid-stream and the final one"
    )


# --- notes clipped to a question (reported after images and documents) -----------
#
# "if the user attaches a note to a chat message how does it show that that
# note is atatched to that message??", it did not, anywhere. The ids went to
# /chat/stream, built one prompt and were thrown away, so both the live bubble
# and the reopened conversation showed plain text with no sign of what the
# answer had been given to read.


def test_a_turn_remembers_which_notes_were_clipped_to_it(ai_client, session):
    from tessellate.core.database import Entry

    note = Entry(content="The wifi password is on the router")
    session.add(note)
    session.commit()

    made = ai_client.post(
        "/conversations",
        json={"question": "what is it?", "answer": "It's on the router.",
              "note_ids": [note.id]},
    )
    assert made.status_code == 201, made.text

    body = ai_client.get(f"/conversations/{made.json()['id']}").json()
    user_message = body["messages"][0]
    assert user_message["note_ids"] == [note.id]
    assert user_message["attachments"] == [
        {"id": note.id, "kind": "note", "name": "The wifi password is on the router"}
    ]


def test_a_private_or_binned_note_loses_its_chip(ai_client, session):
    """Same treatment as a deleted upload, the chip disappears. Listing a
    private note's first line in a conversation would put it back on screen in
    the one place the private-notebook rule cannot reach."""
    from tessellate.core.database import Entry

    private = Entry(content="Therapy notes", is_private=True)
    binned = Entry(content="Old shopping list", is_deleted=True)
    session.add_all([private, binned])
    session.commit()

    made = ai_client.post(
        "/conversations",
        json={"question": "q", "answer": "a", "note_ids": [private.id, binned.id]},
    )
    body = ai_client.get(f"/conversations/{made.json()['id']}").json()
    assert "attachments" not in body["messages"][0]


def test_the_model_is_told_what_the_pictures_in_an_attached_note_say(session):
    """"if there is an image/sketch/file in that note, can the ai read the
    captions or ocr in those attachments if they already exist??", it could
    not. A note's content carries `/media/<filename>` and nothing else, so a
    note whose whole point was a photographed whiteboard reached the model as a
    sentence and a link."""
    from tessellate.api.routes_chat import _media_readings
    from tessellate.core.database import MediaUpload

    session.add(
        MediaUpload(
            filename="abc123.png",
            original_name="whiteboard.png",
            caption="a sprint board with three columns",
            vision_ocr_text="TODO / DOING / DONE",
        )
    )
    session.commit()

    reading = _media_readings(session, "Standup photo:\n![](/media/abc123.png)")
    assert "whiteboard.png" in reading
    assert "a sprint board with three columns" in reading
    assert "TODO / DOING / DONE" in reading


def test_a_picture_with_no_reading_yet_contributes_nothing(session):
    """"If they already exist" is the operative half: nothing here generates a
    caption or runs vision OCR. Captioning may not have run, may be off, or may
    have no model: and a chat turn is the worst place to start one."""
    from tessellate.api.routes_chat import _media_readings
    from tessellate.core.database import MediaUpload

    session.add(MediaUpload(filename="blank.png", original_name="blank.png"))
    session.commit()
    assert _media_readings(session, "![](/media/blank.png)") == ""
    assert _media_readings(session, "no pictures here") == ""


def test_the_model_is_told_whats_inside_a_notes_own_attached_file(client, session):
    """`_media_readings`' own sibling gap: a note's non-image *file*
    attachments (a PDF, a .docx, a code file) never reached the model at
    all: content only ever carried `/media/<filename>` references, and a
    file attachment (Attachment table) isn't a content reference, it's a
    separate list on the note. Round-tripped through the real upload route
    so this exercises the same stored_name/uploads_dir path the reader
    uses, not a hand-built row."""
    from tessellate.api.routes_chat import _attachment_readings
    from tessellate.core.database import Entry

    entry = Entry(content="See the attached notes.")
    session.add(entry)
    session.commit()

    uploaded = client.post(
        f"/entries/{entry.id}/files",
        files={"file": ("agenda.txt", b"Standup at 10am. Ship the release.", "text/plain")},
    )
    assert uploaded.status_code == 201, uploaded.text

    reading = _attachment_readings(session, entry.id)
    assert "agenda.txt" in reading
    assert "Standup at 10am" in reading


def test_a_note_with_no_attachments_gets_no_attachment_reading(session):
    from tessellate.api.routes_chat import _attachment_readings
    from tessellate.core.database import Entry

    entry = Entry(content="Nothing attached here.")
    session.add(entry)
    session.commit()
    assert _attachment_readings(session, entry.id) == ""


def _prompt_text(fake_ollama) -> str:
    return "\n".join(str(m.get("content", "")) for m in fake_ollama.chat_calls[-1])


def test_a_retrieved_note_that_is_mostly_a_picture_brings_its_reading(
    ai_client, fake_ollama, session
):
    """INBOX 491: "I asked what the contents were in the note where the stuff
    was mostly in the image and the ai didnt read that." Only hand-attached
    notes carried their pictures' readings, so a retrieved note that was one
    screenshot of typed ideas reached the model as a link."""
    from tessellate.core.database import MediaUpload

    session.add(
        MediaUpload(
            filename="ideas123.png",
            original_name="image.png",
            ocr_text="Offline banner in the status bar. Note spaces like Apple Notes folders.",
        )
    )
    session.commit()
    ai_client.post(
        "/entries", json={"content": "Some feature ideas I had:\n\n![image.png](/media/ideas123.png)"}
    )
    ai_client.post("/chat", json={"question": "what are my feature ideas?"})
    assert "Note spaces like Apple Notes folders" in _prompt_text(fake_ollama)


def test_a_retrieved_note_with_words_of_its_own_does_not(ai_client, fake_ollama, session):
    """The budget half: a note that says plenty itself keeps its allowance for
    its own words, not for an incidental picture."""
    from tessellate.core.database import MediaUpload

    session.add(MediaUpload(filename="side123.png", original_name="side.png", ocr_text="SIDEBAR READING"))
    session.commit()
    words = "Feature ideas for the timeline, written out in full. " * 8
    ai_client.post("/entries", json={"content": f"{words}\n\n![](/media/side123.png)"})
    ai_client.post("/chat", json={"question": "what are my feature ideas for the timeline?"})
    assert "SIDEBAR READING" not in _prompt_text(fake_ollama)


# --- maps, and a note's name, on reload (INBOX 1460) ---------------------------
#
# "Restored chats (reload) render the same." A mind map rides `board_ids`, a
# field of its own, and the turn dropped it, so a reloaded chat lost the card.
# A note's name was the server's first line cut at 60; the page now makes the
# name (`noteNamePlain`) from the same line it was given at send time.


def test_the_page_saves_the_maps_with_both_turn_paths():
    assert app_js_text().count("board_ids: sentBoards") == 2


def test_a_reloaded_turn_brings_its_mind_map_back_as_a_card(client):
    from tests.test_mindmap import _map

    board = _map(client, name="Thesis")
    made = client.post(
        "/conversations",
        json={"question": "what is on it?", "answer": "An argument.", "board_ids": [board["id"]]},
    )
    assert made.status_code == 201, made.text
    user = client.get(f"/conversations/{made.json()['id']}").json()["messages"][0]
    assert user["board_ids"] == [board["id"]]
    assert user["attachments"] == [{"id": board["id"], "kind": "map", "name": "Thesis"}]


def test_a_binned_map_loses_its_card_on_reload(client):
    from tests.test_mindmap import _map

    board = _map(client, name="Gone")
    made = client.post(
        "/conversations", json={"question": "q", "answer": "a", "board_ids": [board["id"]]}
    )
    client.delete(f"/entries/{board['id']}")
    full = client.get(f"/conversations/{made.json()['id']}").json()
    assert "attachments" not in full["messages"][0]


def test_a_reloaded_note_is_named_by_the_line_the_page_names_it_from(ai_client, session):
    """Titled or not, the server hands back the whole first line after the
    properties block, not a 60-character cut, so `noteNamePlain` draws the same
    words it drew at send time; a note with no words comes back unnamed and
    the page says "Untitled note"."""
    from tessellate.core.database import Entry

    long_title = "# " + "A heading that runs well past sixty characters " * 2
    titled = Entry(content=f"---\ntags: x\n---\n\n{long_title}\nbody line")
    plain = Entry(content="no heading just words that also run on past the old sixty character cut")
    blank = Entry(content="  \n \n")
    session.add_all([titled, plain, blank])
    session.commit()

    made = ai_client.post(
        "/conversations",
        json={"question": "q", "answer": "a", "note_ids": [titled.id, plain.id, blank.id]},
    )
    cards = ai_client.get(f"/conversations/{made.json()['id']}").json()["messages"][0]["attachments"]
    names = {c["id"]: c["name"] for c in cards}
    assert names[titled.id] == long_title.strip()
    assert names[plain.id] == plain.content
    assert names[blank.id] == ""
