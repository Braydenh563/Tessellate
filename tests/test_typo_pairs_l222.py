"""L222: a slip is read by the notebook's own word pairs too: "oat diary" is "oat dairy" when the
notes write "oat dairy" and never "oat diary"; a pair the notes never write moves nothing."""

from tessellate.ai import typo_context


def _read(notes, before, typed, readings, after=""):
    token = typo_context.CTX.set(typo_context.of_notes(notes))
    try:
        return typo_context.lean(typed, readings, before, after, [before, typed, after], True)
    finally:
        typo_context.CTX.reset(token)


def test_a_pair_the_notebook_writes_settles_a_slip():
    notes = [{"title": "Shopping", "content": "Buy oat dairy and rice."}]
    assert _read(notes, "oat", "diary", ["dairy"])[0] == "dairy"


def test_a_pair_the_notebook_never_writes_changes_nothing():
    notes = [{"title": "Shopping", "content": "Buy oat milk and rice."}]
    assert _read(notes, "oat", "diary", ["dairy"])[0] == "diary"


def test_the_word_after_counts_too():
    notes = [{"title": "Shopping", "content": "Dairy free cheese."}]
    assert _read(notes, "", "diary", ["dairy"], "free")[0] == "dairy"
