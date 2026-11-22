"""L102: notes joined by neither link nor tag are themed by their category, but never by a
category on every note or one the question names ("all filed under Fun" for a Fun question)."""

from tessellate.ai import composer_frame


def _n(i, cat, tags=()):
    return {"id": i, "category": cat, "tags": list(tags), "content": f"note {i}"}


def test_loose_notes_in_one_category_are_a_theme():
    groups = composer_frame.themes([_n(1, "Travel"), _n(2, "Travel"), _n(3, "Work"), _n(4, "Health")])
    multi = [g for g in groups if len(g.ids) > 1]
    assert [sorted(g.ids) for g in multi] == [[1, 2]]
    assert multi[0].joined_by == "all filed under Travel"


def test_a_category_on_every_note_is_no_theme():
    assert all(len(g.ids) == 1 for g in composer_frame.themes([_n(1, "Fun"), _n(2, "Fun"), _n(3, "Fun")]))


def test_the_category_the_question_names_is_no_theme():
    notes = [_n(1, "Fun"), _n(2, "Fun"), _n(3, "Work"), _n(4, "Work")]
    named = composer_frame.themes(notes, {"fun"})
    assert [sorted(g.ids) for g in named if len(g.ids) > 1] == [[3, 4]]
