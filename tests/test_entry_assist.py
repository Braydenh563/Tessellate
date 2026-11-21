"""The assist service, called directly (decision 55, L-world-class-632)."""

from __future__ import annotations

import pytest

from tessellate.entry import assist, manager


def _note(session, text: str):
    entry = manager.create_entry(session, text, category_name=manager.UNCATEGORISED)
    session.commit()
    return entry


def test_an_empty_draft_offers_no_tags(session):
    assert assist.draft_tags(session, "  ", [], "A title") == {"suggested_tags": [], "suggested_tag_reasons": {}}


def test_a_private_note_is_not_appended_to(session):
    entry = _note(session, "secret")
    entry.is_private = True
    with pytest.raises(assist.NeedsReadable):
        assist.add_context(session, entry, "more")


def test_nothing_to_improve_is_refused_before_any_model_is_asked():
    with pytest.raises(assist.NothingToImprove):
        assist.improve("   ", "proofread", None)
    with pytest.raises(assist.NothingToImprove):
        assist.improve("some text", "custom", " ")
