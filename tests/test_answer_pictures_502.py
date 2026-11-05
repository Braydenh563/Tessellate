"""An answer grounded in a note with pictures shows them beside its citation
(INBOX 502).

The owner: "should the ai chats be able to pull images and sketches and render
them in chat responses?? with accompanying references and hyperlinks??"
Decision, taken: yes. The citation chip still opens the note; up to three
lazy, sized thumbnails beside it open the picture in the lightbox; their alt
text is the caption or the text read off the picture; the model is told which
notes have pictures so it can point at one by the note's number. Driven in
Chromium by the session's `pictures502.js`; this is the server half and the
cheap half of the client.
"""

from __future__ import annotations

import json
import shutil
import subprocess
from pathlib import Path

import pytest
from tests._app_js import with_pieces

JS = Path(__file__).resolve().parent.parent / "frontend" / "js"


def test_picture_alts_come_from_the_caption_then_the_reading(session):
    from tessellate.api.chat_attach import _picture_alts
    from tessellate.core.database import Entry, MediaUpload

    session.add_all(
        [
            MediaUpload(filename="cap.png", original_name="board.png", caption="a sprint board", ocr_text="TODO"),
            MediaUpload(filename="ocr.png", original_name="page.png", vision_ocr_text="  Offline\nbanner  ideas "),
            MediaUpload(filename="none.png", original_name="none.png"),
        ]
    )
    session.commit()
    entries = [
        Entry(content="![](/media/cap.png) and ![x](/media/ocr.png)"),
        Entry(content="![](/media/none.png) ![](/media/cap.png)"),
        Entry(content="no pictures"),
    ]
    alts = _picture_alts(session, entries)
    assert alts == {"/media/cap.png": "a sprint board", "/media/ocr.png": "Offline banner ideas"}
    assert _picture_alts(session, [Entry(content="words only")]) == {}


def test_the_chat_answer_carries_the_alts_and_the_prompt_names_the_pictures(ai_client, fake_ollama, session):
    from tessellate.core.database import MediaUpload

    session.add(MediaUpload(filename="moss123.png", original_name="moss.png", caption="moss on a wall"))
    session.commit()
    ai_client.post("/entries", json={"content": "Moss photo from the walk:\n\n![moss.png](/media/moss123.png)"})
    body = ai_client.post("/chat", json={"question": "what did I photograph on the walk? moss"}).json()
    assert body["picture_alts"] == {"/media/moss123.png": "moss on a wall"}
    prompt = "\n".join(str(m.get("content", "")) for m in fake_ollama.chat_calls[-1])
    assert "(has 1 picture: write [picture 1] only if seeing it answers or shows the point, never as decoration)" in prompt


def test_the_turn_keeps_the_alts_for_a_reopened_chat(client):
    created = client.post(
        "/conversations",
        json={
            "question": "q",
            "answer": "a",
            "picture_alts": {"/media/a.png": "a cat", "javascript:alert(1)": "no"},
        },
    ).json()
    messages = client.get(f"/conversations/{created['id']}").json()["messages"]
    assert messages[1]["picture_alts"] == {"/media/a.png": "a cat"}


def test_the_client_draws_thumbnails_beside_the_chip():
    ask = with_pieces("capture-ask.js")
    start = ask.index("function groundingThumbs(pictures, n, alts)")
    thumbs = ask[start : ask.index("\n}\n", start)]
    for needle in ('img.loading = "lazy"', "img.width = 32", "img.height = 32", "img.alt = words ||", "openLightbox(items, i)"):
        assert needle in thumbs
    grounding = ask[ask.index("function renderAnswerGrounding(") :][:6000]
    assert "support = null, pictureAlts = null" in grounding
    assert "groundingThumbs(pictures, n, pictureAlts)" in grounding
    # Every caller hands the alts on: live Chat, live Ask, a reopened chat.
    assert "meta?.picture_alts || null" in with_pieces("chat-attach.js")
    assert "answerMeta?.picture_alts || null" in ask
    assert "message.picture_alts || null" in (JS / "sheets-selects.js").read_text(encoding="utf-8")


# INBOX 526: the picture inside the bubble itself, by a `[picture N]` token.


def test_image_size_reads_the_headers(tmp_path):
    import struct
    import zlib

    from tessellate.core.imagesize import image_size

    def png(w, h):
        def chunk(kind, data):
            return struct.pack(">I", len(data)) + kind + data + struct.pack(">I", zlib.crc32(kind + data))

        return b"\x89PNG\r\n\x1a\n" + chunk(b"IHDR", struct.pack(">IIBBBBB", w, h, 8, 2, 0, 0, 0))

    (tmp_path / "a.png").write_bytes(png(800, 600))
    jpeg = b"\xff\xd8\xff\xe0\x00\x04ab\xff\xc0\x00\x0b\x08\x01\x2c\x01\x90\x01\x01\x11\x00"
    (tmp_path / "b.jpg").write_bytes(jpeg)
    (tmp_path / "c.gif").write_bytes(b"GIF89a" + struct.pack("<HH", 40, 30) + b"\0" * 8)
    (tmp_path / "d.png").write_bytes(b"not an image")
    assert image_size(tmp_path / "a.png") == (800, 600)
    assert image_size(tmp_path / "b.jpg") == (400, 300)
    assert image_size(tmp_path / "c.gif") == (40, 30)
    assert image_size(tmp_path / "d.png") is None
    assert image_size(tmp_path / "missing.png") is None


def test_picture_sizes_ride_the_answer_and_the_saved_turn(ai_client, fake_ollama, session, tmp_path):
    from tessellate.core import deps

    media = deps.get_config().data_dir / "media"
    media.mkdir(parents=True, exist_ok=True)
    import struct
    import zlib

    def chunk(kind, data):
        return struct.pack(">I", len(data)) + kind + data + struct.pack(">I", zlib.crc32(kind + data))

    (media / "sz123.png").write_bytes(
        b"\x89PNG\r\n\x1a\n" + chunk(b"IHDR", struct.pack(">IIBBBBB", 800, 600, 8, 2, 0, 0, 0))
    )
    ai_client.post("/entries", json={"content": "Whiteboard from the sprint:\n\n![](/media/sz123.png)"})
    body = ai_client.post("/chat", json={"question": "what is on the sprint whiteboard?"}).json()
    assert body["picture_sizes"] == {"/media/sz123.png": [800, 600]}
    prompt = "\n".join(str(m.get("content", "")) for m in fake_ollama.chat_calls[-1])
    assert "write [picture 1]" in prompt
    created = ai_client.post(
        "/conversations",
        json={
            "question": "q",
            "answer": "a [picture 1]",
            "picture_sizes": {"/media/sz123.png": [800, 600], "https://x/y.png": [1, 1]},
        },
    ).json()
    messages = ai_client.get(f"/conversations/{created['id']}").json()["messages"]
    assert messages[1]["picture_sizes"] == {"/media/sz123.png": [800, 600]}


def test_the_agent_prompt_names_the_pictures_too():
    """INBOX 527, the owner: "does the ai know that it can have images in its
    response??" The tools-on prompt (the default) said nothing about them, so
    only a no-tools chat could place one. Numbered as `raw_results` is."""
    from tessellate.ai import agent_turn

    messages = agent_turn.build_agent_messages(
        "what is on the whiteboard?",
        [
            {"id": 4, "content": "words", "category": "Work"},
            {"id": 9, "content": "![](/media/a.png) ![](/media/b.png)", "category": "Work", "pictures": 2},
        ],
    )
    prompt = messages[-1]["content"]
    assert "(note id 9) [Work] (has 2 pictures: write [picture 2] or [picture 2.2]" in prompt
    assert "(note id 4) [Work] <<<data" in prompt, "a note without pictures says nothing about them"


def test_a_note_with_two_pictures_offers_the_second_token():
    from tessellate.ai.librarian import _pictures_hint

    assert "[picture 3] or [picture 3.2]" in _pictures_hint({"pictures": 2}, 3)
    assert _pictures_hint({"pictures": 0}, 3) == ""


def test_the_client_places_figures_from_tokens():
    ask = with_pieces("capture-ask.js")
    start = ask.index("function placeAnswerFigures(")
    body = ask[start : ask.index("\n}\n", start)]
    # The token is always removed; a figure needs a note with pictures; three at most.
    for needle in ("PICTURE_TOKEN", "FIGURES_MAX", "notePictures(", "PICTURE_ASK", "if (wrote || !asked) return;", "if (asked) for (const m of found)"):
        assert needle in body
    assert "FIGURES_MAX = 3" in ask
    assert 'querySelector(".answer-figure")' in body
    figure = ask[ask.index("function answerFigure(") :][:2500]
    for needle in ('img.loading = "lazy"', "img.width", "img.height", "openLightbox(pictureItems", "flashEntry(", "From note"):
        assert needle in figure
    # A half-written token never reaches the page while the answer streams.
    assert "holdPictureTokens(latest)" in ask
    # Every surface that shows an answer places them: live Ask, live Chat, a reopened chat, a reopened Ask.
    assert "placeAnswerFigures(answerBox, answerMeta, question)" in ask
    assert "placeAnswerFigures(" in with_pieces("chat-attach.js")
    assert "placeAnswerFigures(" in (JS / "sheets-selects.js").read_text(encoding="utf-8")
    assert "placeAnswerFigures(" in (JS / "ask-history.js").read_text(encoding="utf-8")


@pytest.mark.skipif(not shutil.which("node"), reason="needs node")
def test_a_half_written_token_is_held_back_and_a_whole_one_removed():
    ask = with_pieces("capture-ask.js")
    token = ask[ask.index("const PICTURE_TOKEN") : ask.index("\n", ask.index("const PICTURE_TOKEN"))]
    hold = ask[ask.index("function holdPictureTokens") :]
    hold = hold[: hold.index("\n}\n") + 2]
    script = token + "\n" + hold + """
const cases = ["See [picture 1] now", "See [picture 2.1] and [Picture 3]", "See [pic", "See [picture 1", "See [picture 12.",
  "A [link", "A [link](x) and [", "Done."];
console.log(JSON.stringify(cases.map(holdPictureTokens)));"""
    out = subprocess.run(["node", "-e", script], capture_output=True, text=True, check=True).stdout
    assert json.loads(out) == [
        "See  now", "See  and ", "See ", "See ", "See ", "A [link", "A [link](x) and ", "Done.",
    ]


def test_the_model_hears_of_pictures_only_when_asked_about_one():
    """INBOX 533: "it just puts images for the sake of images". A 2B model told
    a note had pictures wrote `[picture N]` into "test notes"."""
    from tessellate.ai import librarian

    note = {"category": "X", "content": "a to-do list", "pictures": 1, "id": 1}
    plain = librarian.build_messages("test notes", [note])
    asked = librarian.build_messages("show me the sketch of my to-do list", [note])
    assert "[picture 1]" not in str(plain)
    assert "[picture 1]" in str(asked)
