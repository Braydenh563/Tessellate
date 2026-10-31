"""The composer audit of 2026-10-31 (docs/roadmap/agent-remaining/audit-1031-composer.md),
one class per test group, each over many phrasings. Notebook and fixed clock:
`tests/_seed_1031c.py` (Saturday 31 October 2026, 11:30)."""

from __future__ import annotations

import pytest

import tests._seed_1031c as seed_c


@pytest.fixture
def notebook(client, session, monkeypatch):
    seed_c.seed(session)
    return seed_c.asker(client, monkeypatch)


@pytest.fixture
def big_notebook(client, session, monkeypatch):
    seed_c.seed(session, filler=150)
    return seed_c.asker(client, monkeypatch)


# C1. A note titled with the name is a member of "who is X", whatever its body says.

@pytest.mark.parametrize("question", [
    "who is Tom", "who's Tom", "tell me about Tom", "what do I know about Tom", "what have I written about Tom",
    "what do my notes say about Tom", "who is tom?", "WHO IS TOM",
])
def test_the_note_titled_with_the_name_is_said_for_a_who_ask(notebook, question):
    said, _ = notebook(question)
    assert "data team at Vireo" in said, said
    assert "three notes" in said, said


@pytest.mark.parametrize("question", ["where does Tom work", "what does Tom do", "what does Tom do for work", "where does Tom work again"])
def test_a_pronoun_line_in_the_note_titled_with_the_name_answers_a_slot(notebook, question):
    said, _ = notebook(question)
    assert "data team at Vireo" in said, said


# C2. A list item is not a newer value of a relation.

@pytest.mark.parametrize("question", [
    "who is Sara", "what have I written about Sara", "what is in the Sara note", "what does Sara want for her birthday",
    "what should I get Sara", "tell me about Sara", "when is Sara's birthday",
])
def test_a_gift_list_does_not_replace_the_sara_note(notebook, question):
    said, _ = notebook(question)
    assert "used to be" not in said and "my sister" not in said, said
    assert "an older note" not in said.lower() and "earlier, on" not in said.lower(), said


def test_a_real_replacement_is_still_reported_in_the_second_person():
    from tessellate.ai import supersede

    notes = [
        {"content": "Uni days this semester: Tuesday and Thursday", "created_at": "2026-02-20T10:00:00"},
        {"content": "Uni days this semester are Monday and Wednesday", "created_at": "2026-07-20T10:00:00"},
    ]
    kept, replaced = supersede.current("what are my uni days", notes)
    assert len(kept) == 1 and replaced
    first_person = [{"content": "My favourite colour is blue", "created_at": "2026-01-01"}, {"content": "My favourite colour is now green", "created_at": "2026-06-01"}]
    kept, replaced = supersede.current("what is my favourite colour", first_person)
    assert len(kept) == 1
    assert "your" not in supersede.older_line(replaced) or "my" not in supersede.older_line(replaced)


@pytest.mark.parametrize("old, new", [("Sara is my sister", "Sara: a jazz record"), ("Tom is my brother", "Tom: coffee beans"), ("Sara is my sister", "Sara is a runner")])
def test_a_relation_is_never_a_stale_value(old, new):
    from tessellate.ai import supersede

    notes = [{"content": old, "created_at": "2026-01-01"}, {"content": new, "created_at": "2026-06-01"}]
    kept, replaced = supersede.current("who is " + old.split()[0], notes)
    assert len(kept) == 2 and not replaced
