"""Brief 89 (the owner: "also should \"add tags\" show for notes with 0-2/3 tags
on them?? with suggested tags as well?? and also an option for \"dont suggest
tags\" for this note or smth."): a note with fewer than three tags carries a
quiet "+ Tag" chip, it opens up to three suggestions as one-click chips above
the field, and its menu turns suggestions off for that note (and back on).
"""

from __future__ import annotations

import json
import shutil
import subprocess
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
CARDS = ((ROOT / "frontend/js/note-cards.js").read_text(encoding="utf-8") + (ROOT / "frontend/js/entry-card.js").read_text(encoding="utf-8"))
SUGGEST = (ROOT / "frontend/js/tag-suggest.js").read_text(encoding="utf-8")


def _function(source: str, name: str) -> str:
    start = source.index(f"function {name}(")
    depth, i = 0, source.index("{", start)
    for j in range(i, len(source)):
        depth += source[j] == "{"
        depth -= source[j] == "}"
        if depth == 0:
            return source[start : j + 1]
    raise AssertionError(name)


def _kind(tags: int, **entry) -> str | None:
    node = shutil.which("node")
    if not node:
        pytest.skip("node is not installed")
    script = (
        "const TAG_ADD_BELOW = 3;\n"
        f"{_function(CARDS, 'tagAddChipKind')}\n"
        f"const entry = Object.assign({{ tags: {json.dumps(['t'] * tags)}, suggested_tags: [] }}, {json.dumps(entry)});\n"
        "console.log(JSON.stringify(tagAddChipKind(entry, { actions: true })));"
    )
    out = subprocess.run([node, "-e", script], capture_output=True, text=True, check=True, timeout=30)
    return json.loads(out.stdout)


def test_the_chip_shows_below_three_tags_and_not_at_three() -> None:
    assert _kind(0) == "add"
    assert _kind(1) == "more"
    assert _kind(2) == "more"
    assert _kind(3) is None
    assert _kind(5) is None


def test_the_chip_is_left_off_boards_and_drafts_and_read_only_rows() -> None:
    assert _kind(1, is_board=True) is None
    assert _kind(1, is_draft=True) is None
    assert "tagAddChipKind(entry, options)" in CARDS
    assert "const TAG_ADD_BELOW = 3;" in CARDS


def test_no_tags_but_suggestions_gets_the_quiet_chip_not_the_empty_state() -> None:
    assert _kind(0, suggested_tags=["a"]) == "more"


def _note(client, tags=()):
    return client.post("/entries", json={"content": "Enzymes and the cell cycle", "tags": list(tags)}).json()["id"]


def test_the_flag_defaults_off_and_round_trips(client) -> None:
    entry_id = _note(client, ["bio"])
    assert client.get(f"/entries/{entry_id}").json()["tag_suggest_off"] is False
    out = client.post(f"/entries/{entry_id}/suggested-tags", json={"mute": True}).json()
    assert out["tag_suggest_off"] is True
    assert client.get(f"/entries/{entry_id}").json()["tag_suggest_off"] is True
    out = client.post(f"/entries/{entry_id}/suggested-tags", json={"mute": False}).json()
    assert out["tag_suggest_off"] is False


def test_a_muted_note_offers_nothing_and_unmuting_brings_them_back(client) -> None:
    entry_id = _note(client, ["bio"])
    client.post(f"/entries/{entry_id}/suggested-tags", json={"restore": ["cells", "enzymes"]})
    assert client.get(f"/entries/{entry_id}").json()["suggested_tags"] == ["cells", "enzymes"]
    out = client.post(f"/entries/{entry_id}/suggested-tags", json={"mute": True}).json()
    assert out["suggested_tags"] == [] and out["suggested_tag_reasons"] == {}
    back = client.post(f"/entries/{entry_id}/suggested-tags", json={"mute": False}).json()
    assert back["suggested_tags"] == ["cells", "enzymes"]


def test_a_muted_note_is_not_given_new_suggestions_when_filed(client, session) -> None:
    from tessellate.api import routes_entries
    from tessellate.core.database import Entry

    for text in ("Biology lecture: mitosis", "Biology: the Krebs cycle"):
        client.post("/entries", json={"content": text, "tags": ["biology"]})
    entry_id = _note(client)
    client.post(f"/entries/{entry_id}/suggested-tags", json={"mute": True})
    entry = session.get(Entry, entry_id)
    session.refresh(entry)
    entry.suggested_tags = "[]"
    routes_entries._keep_suggestions(session, entry, None)
    assert entry.suggested_tags == "[]"


def test_the_menu_item_exists_and_says_both_ways() -> None:
    assert "Don't suggest tags for this note" in SUGGEST
    assert "Suggest tags for this note again" in SUGGEST
    assert "openNoteTagPopover" in SUGGEST and "openNoteTagPopover" in CARDS
    assert "kebabMenu(" in _function(SUGGEST, "openNoteTagPopover")


def test_turning_it_off_is_undoable() -> None:
    body = _function(SUGGEST, "answerSuggestedTags")
    assert "body.mute" in body and "offerUndo(" in body and "{ mute: false }" in body
    assert 'record: false' in body


def test_the_guide_and_the_popover_say_so() -> None:
    source = (ROOT / "src/tessellate/ai/help_topics_more.py").read_text(encoding="utf-8")
    assert "Don't suggest tags for this note" in source
    assert 'data-help-for", "note-tag-pop-help"' in SUGGEST
    assert "Don't suggest tags for this note" in SUGGEST
