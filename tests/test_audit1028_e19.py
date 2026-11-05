"""Audit 1028 E19: a source list stays whole and keeps its capitals."""

from __future__ import annotations


import pytest

from tessellate.ai import composer_digest as digest
from tessellate.ai import composer_write as write
from tessellate.entry import manager
from tests.test_composer_route_688 import _ask


def _said(client, question):
    return _ask(client, question, use_tools=False)["text"]


# --- E19: a source list stays whole and keeps its capitals ---------------------------


@pytest.mark.parametrize("label", ["Sources", "Reading list", "Books used", "References", "Bibliography", "Further reading"])
def test_a_labelled_list_is_one_bullet_not_split_at_its_semicolons(label):
    text = f"Essay intro. {label}: Clark, The Sleepwalkers; Macmillan, The War That Ended Peace."
    bullets = write.to_bullets(text).splitlines()
    assert f"- {label}: Clark, The Sleepwalkers; Macmillan, The War That Ended Peace" in bullets, bullets
    assert not any(b.startswith("- Macmillan") for b in bullets)


def test_clauses_with_no_label_still_split_into_bullets():
    bullets = write.to_bullets("Germany feared encirclement; Russia mobilised early; Austria declared war on Serbia.").splitlines()
    assert len(bullets) == 3 and bullets[1].startswith("- Russia")


@pytest.mark.parametrize("citation", ["Hunter 1999", "Clark (2012), The Sleepwalkers", "Gray 2004, The Picture", "Bishop, The Chessmen"])
def test_an_author_keeps_its_capital_after_other_words(citation):
    assert digest._fragment(citation, set()) == citation


def test_the_sources_line_of_a_note_is_told_whole_with_its_capitals(client, session):
    manager.create_entry(session, "# History essay\n\nThe causes of the First World War.\n\nSources: Clark, The Sleepwalkers; Macmillan, The War That Ended Peace.", category_name="Uni")
    session.commit()
    for question in ("what are my sources", "what did I note about my history essay", "what do my notes say about the First World War"):
        said = _said(client, question)
        assert "Clark, The Sleepwalkers; Macmillan, The War That Ended Peace" in said, (question, said)
        assert "clark" not in said and "[ ] " not in said, (question, said)


