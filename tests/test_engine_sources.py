"""Sources of every kind and captions as content (CHAT_PLAN Phase 6 step 5,
decision 37)."""

from __future__ import annotations

from datetime import date

from tessellate.ai import composer
from tessellate.ai import composer_read
from tessellate.core.database import MediaUpload
from tessellate.entry import manager
from tests.test_composer_route_688 import _ask

TODAY = date(2026, 10, 6)


def _ask_composer(question, notes):
    return composer.compose(question, notes, today=TODAY)


def test_a_board_is_cited_as_a_board_and_its_row_says_so():
    notes = [{"id": 8, "content": "# Harbor board\n\nHarbor risks: offline mode is hard to find.", "created_at": "2026-09-28", "kind": "board"}]
    result = _ask_composer("what are the Harbor risks", notes)
    assert "[board **Harbor board**]" in result["text"]
    assert result["grounding"][0]["kind"] == "board"


def test_a_document_the_route_attaches_is_a_document_by_its_category():
    notes = [{"id": 3, "content": "Pricing memo\n\nThe price stays at nine dollars a month for the first year.", "category": "Document"}]
    result = _ask_composer("what is the price", notes)
    assert result["grounding"][0]["kind"] == "document"
    assert "[document **Pricing memo**]" in result["text"]


def test_a_note_and_a_document_with_one_id_are_both_cited_by_their_own_ids():
    notes = [
        {"id": 3, "content": "# Pricing call\n\nSam wants the price at nine dollars.", "created_at": "2026-10-01"},
        {"id": 3, "content": "Pricing memo\n\nThe price stays at nine dollars a month.", "category": "Document"},
    ]
    result = _ask_composer("what is the price", notes)
    kinds = {(g["note_id"], g["kind"]) for g in result["grounding"]}
    assert kinds == {(3, "note"), (3, "document")}


def test_a_picture_listed_in_a_note_is_read_as_the_picture():
    notes = [{"id": 15, "content": "# Photos\n\n- shed.jpg: shows a wet wooden roof with a dark stain", "created_at": "2026-10-04"}]
    result = _ask_composer("what does the shed roof look like", notes)
    assert any(p[0] == "picture" and "wet wooden roof" in p[1] for p in result["parts"])
    assert result["grounding"][0]["said"] == "picture"


def test_the_source_kinds():
    assert composer_read.source_kind({"kind": "board"}) == "board"
    assert composer_read.source_kind({"category": "Mind map"}) == "map"
    assert composer_read.source_kind({"category": "File"}) == "file"
    assert composer_read.source_kind({"category": "Work"}) == "note"


def test_a_caption_is_content_on_the_route_for_any_note_with_a_picture(client, session):
    """The owner: "Note captions arent counted as note content". A note with
    a few lines and a picture (not "mostly pictures") brings its picture's
    caption; the answer quotes it as the picture's."""
    session.add(MediaUpload(filename="shed.png", original_name="shed.png", caption="a wet wooden roof with a dark stain", ocr_text="PRIVATE OCR"))
    manager.create_entry(
        session,
        "# Garden shed\n\nThe garden shed needs work before winter. The door sticks in damp weather and the "
        "gutter on the north side is loose. Ask the neighbour about a ladder. Photo from Saturday:\n\n"
        "![](/media/shed.png)",
    )
    session.commit()
    out = _ask(client, "what does the shed roof look like", notes_only=True, use_tools=False, answer_from="notes")
    assert "wet wooden roof with a dark stain" in out["text"], out["text"]
    #: The text read in a picture stays out of a note that is not mostly pictures.
    assert "PRIVATE OCR" not in out["text"]
