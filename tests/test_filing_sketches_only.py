"""Row 1, blind-test round 3 (dog3-1026): text notes were filed under
"Sketches" at 52-54% because a category of caption-plus-drawing notes was the
only category filing by meaning could vote for."""

from __future__ import annotations

from tessellate.ai import janitor
from tests.test_janitor_knn import DeadOllama, DirectedEmbeddings, _note


def test_picture_notes_are_not_examples_for_filing_by_meaning(session, app_state):
    """A caption plus a drawing says nothing about where a text note belongs,
    so a notebook of only sketches leaves a new note Uncategorised."""
    for n in ("a", "b", "c"):
        _note(session, f"Sketch {n}\n\n![Sketch {n}](/media/{n}.png)", "Sketches", [1.0, 0.0, 0.0, 0.0])
    embeddings = DirectedEmbeddings({"lecture": [1.0, 0.0, 0.0, 0.0]})
    name, _c, method = janitor.categorise(
        session, "lecture notes on the estates general", embeddings, model_manager=None, ollama=DeadOllama()
    )
    assert (name, method) == ("Uncategorised", "none")


def test_a_note_with_real_text_beside_its_picture_still_counts(session, app_state):
    text = "Diagram of the water cycle with evaporation, condensation and rainfall labelled for the exam on Friday"
    for n in ("a", "b"):
        _note(session, f"{text} {n}\n\n![fig](/media/{n}.png)", "Biology", [1.0, 0.0, 0.0, 0.0])
    embeddings = DirectedEmbeddings({"lecture": [1.0, 0.0, 0.0, 0.0]})
    name, _c, method = janitor.categorise(
        session, "lecture on rainfall", embeddings, model_manager=None, ollama=DeadOllama()
    )
    assert name == "Biology"
