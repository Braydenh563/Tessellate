"""One filing decision, read by every surface (INBOX 1583, the owner: "the
filing of this note could have been improved"; "what's the point of having
that whole taxonomy stuff if it isnt properly used with the composer").

The Capture hint offered "File in Hobbies" while the saved note said "Saved
in Uncategorised: it reads as Finance, so it waits for you to choose": the
hint took the words' best guess whatever its margin, the save filed only a
clear lead, and one stray money word held a gym-and-golf note as Finance.
Now `lexical_filing.filing_call` is the one decision: the hint, the draft
chip and the saved status read it, and the model path is handed its
candidates. The corpus is built from the taxonomy pack itself, so the test
says what the pack says, not what one hand-written notebook happens to.
"""

from __future__ import annotations

import json
import re
from datetime import datetime, timezone

import pytest

from tessellate.ai import janitor, lexical_filing, offers, taxonomy
from tessellate.entry import manager

NOW = datetime(2026, 11, 3, 10, 0, tzinfo=timezone.utc)

#: Each category with the pack topic its notes are about.
CATEGORIES = {
    "Hobbies": "Sports",
    "Study": "Education",
    "Finance": "Finance",
    "Cooking": "Cooking",
    "Travel": "Travel",
    "Garden": "Gardening",
}
SEED_NOTES = 6


def _phrases(topic: str) -> list[str]:
    """The pack's strong phrases that name `topic` and nothing else."""
    index = taxonomy._keyword_index()
    weak = taxonomy._weak_terms()
    return [
        p for p in taxonomy.taxonomy_map()[topic]
        if p not in weak and set(index.get(p, ())) <= {topic}
        and taxonomy.topic_hits(f"Today: {p}.").get(topic) == [p]
    ]


def _seed(session) -> None:
    for name, topic in CATEGORIES.items():
        words = _phrases(topic)
        for i in range(SEED_NOTES):
            manager.create_entry(session, f"Notes on {words[2 * i]} and {words[2 * i + 1]} this week.", category_name=name)
    session.commit()


def _mixed() -> list[tuple[str, str]]:
    """(note, expected category): one of a category's phrases its notes
    already said, one they never did, and one stray phrase of the next
    category's, as a real note on a subject repeats some of its words."""
    names = list(CATEGORIES)
    out = []
    for i, name in enumerate(names):
        phrases = _phrases(CATEGORIES[name])
        seen, unseen = phrases[: 2 * SEED_NOTES], phrases[2 * SEED_NOTES:]
        stray = _phrases(CATEGORIES[names[(i + 1) % len(names)]])[-1]
        for j in range(2):
            out.append((f"Spent the afternoon on {seen[3 * j + 1]}, then {unseen[j]}. Also, {stray}.", name))
    return out


def _unseen() -> list[tuple[str, str]]:
    """The hard case: two of a category's phrases its notes never said, so
    only the pack knows them, beside the stray phrase."""
    names = list(CATEGORIES)
    out = []
    for i, name in enumerate(names):
        unseen = _phrases(CATEGORIES[name])[2 * SEED_NOTES:]
        stray = _phrases(CATEGORIES[names[(i + 1) % len(names)]])[-1]
        out.append((f"Spent the afternoon on {unseen[2]}, then {unseen[3]}. Also, {stray}.", name))
    return out


def _hint(session, text: str) -> tuple[str | None, list[str], list[dict]]:
    """(the category the hint says a save files to, every category it offers, the offers)."""
    filing = [o for o in offers.offers(session, text, now=NOW) if o["kind"] == "filing"]
    decided = next((o["value"]["category"] for o in filing if o["value"].get("decided")), None)
    return decided, [o["value"]["category"] for o in filing], filing


class _NoModel:
    def is_running(self) -> bool:
        return False


class _Models:
    def utility_model(self) -> str:
        return "fake"


class _FakeModel:
    """A chat model that answers the first category the words put forward,
    or the first existing one when the prompt names none."""

    def __init__(self) -> None:
        self.prompts: list[str] = []

    def is_running(self) -> bool:
        return True


def _saved(session, text: str, monkeypatch, model=None) -> str | None:
    """The category a save with no embedder files `text` into (None:
    Uncategorised, waiting)."""
    monkeypatch.setattr(janitor, "_semantic_category", lambda *a, **k: None)
    name, _confidence, method = janitor.categorise(session, text, object(), _Models(), model or _NoModel())
    return None if method == "none" else name


def _answer_first_candidate(model: _FakeModel):
    def chat(_ollama, _model, messages, deadline=None, on_late=None):  # noqa: ANN001, ANN202, ARG001
        prompt = messages[-1]["content"]
        model.prompts.append(prompt)
        found = re.search(r"^The notebook's own words point to[^:]*: ([^;\n(]+?)(?: \(|;|$)", prompt, re.M)
        listed = re.search(r"^Existing categories: ([^,\n]+)", prompt, re.M)
        category = (found or listed).group(1).strip()
        return {"content": json.dumps({"category": category, "confidence": 90})}

    return chat


def test_the_corpus_is_built_from_the_pack() -> None:
    for topic in CATEGORIES.values():
        assert len(_phrases(topic)) >= 2 * SEED_NOTES + 4, topic


#: Of the twelve mixed notes, how many file with no model (measured: 8
#: before INBOX 1583, the two Study notes held as Finance by the stray
#: "refund" as the owner's was by "bonus"; 10 after, the two Finance notes
#: held by decision 6).
FILED_RIGHT_FLOOR = 10


def test_model_off_the_hint_and_the_save_agree_on_every_mixed_note(session, monkeypatch) -> None:
    _seed(session)
    filed = 0
    for text, expected in _mixed():
        decided, offered, _ = _hint(session, text)
        saved = _saved(session, text, monkeypatch)
        call = lexical_filing.filing_call(session, text)
        assert decided == saved == call.category, (text, decided, saved, call)
        #: Never the wrong category: a confident one is right, and a note it
        #: waits on offers the right one first.
        assert (saved or offered[0]) == expected, (text, expected, saved, offered)
        assert (call.held is not None) == taxonomy.sensitive_topics().__contains__(CATEGORIES[expected]), call
        filed += saved is not None
    assert filed >= FILED_RIGHT_FLOOR, filed


def test_a_stray_phrase_never_files_a_note_where_it_points(session, monkeypatch) -> None:
    """Measured before INBOX 1583: three of these six filed in the stray
    phrase's category ("seed sowing, then pruning; also, league table" in
    Hobbies). A note may wait; it is never filed by its stray words."""
    _seed(session)
    for text, expected in _unseen():
        decided, _offered, _ = _hint(session, text)
        saved = _saved(session, text, monkeypatch)
        assert decided == saved and saved in (None, expected), (text, expected, saved)


def test_model_on_gets_the_same_candidates_and_files_at_least_as_well(session, monkeypatch) -> None:
    """Decision 75 parity: the model is handed the words' candidates, so a
    model that takes them files every note the words file, where they file
    it, and settles the close calls on the first choice the hint showed."""
    _seed(session)
    model = _FakeModel()
    monkeypatch.setattr(janitor, "_chat_within_deadline", _answer_first_candidate(model))
    for text, expected in _mixed():
        decided, offered, _ = _hint(session, text)
        saved = _saved(session, text, monkeypatch, model)
        assert f"point to, best first: {expected}" in model.prompts[-1]
        held = lexical_filing.filing_call(session, text).held
        assert saved == (None if held else (decided or offered[0])), (text, decided, offered, saved)
        assert held or saved == expected


OWNER_NOTE = "Uni is done!! :D\n\nHanded in my final assignment today. Gym tomorrow, then golf with the lads, paid for with my bonus."


def _owner_notebook(session) -> None:
    rows = [("Hobbies", f"Gym session then {sport}") for sport in ("golf", "tennis", "a swim", "squash", "cricket")]
    rows += [("Hobbies", f"Golf with Sam, {what}") for what in ("two birdies", "the back nine", "a new driver", "range work", "putting")]
    rows += [("Study", f"Lecture notes on {what} for the semester") for what in ("databases", "ethics", "statistics", "networks")]
    rows += [("Finance", f"Monthly budget: rent, {what} and savings") for what in ("groceries", "bills", "the loan", "the mortgage")]
    for name, content in rows:
        manager.create_entry(session, content, category_name=name)
    session.commit()


def test_one_stray_money_word_does_not_hold_a_gym_and_golf_note(session, monkeypatch) -> None:
    """The owner's note: no Finance in the hint, the save or the hold."""
    _owner_notebook(session)
    call = lexical_filing.filing_call(session, OWNER_NOTE)
    assert call.held is None and lexical_filing.holds_sensitive(OWNER_NOTE, "Hobbies") is None
    decided, offered, filing = _hint(session, OWNER_NOTE)
    assert "Finance" not in offered and offered[0] == "Hobbies"
    assert decided == _saved(session, OWNER_NOTE, monkeypatch) == call.category
    assert "gym" in filing[0]["reason"] and "golf" in filing[0]["reason"]


def test_a_close_call_offers_two_or_three_and_files_nothing(session, monkeypatch) -> None:
    _owner_notebook(session)
    text = "Uni is done, final assignment handed in. Gym later."
    call = lexical_filing.filing_call(session, text)
    decided, offered, filing = _hint(session, text)
    if call.category is None:
        assert 2 <= len(call.choices) <= 3 and offered == [name for name, _ in call.choices]
        assert decided is None and _saved(session, text, monkeypatch) is None
        #: Each choice names the words that put it forward.
        assert all(o["reason"] for o in filing)
    else:
        assert decided == _saved(session, text, monkeypatch) == call.category


def test_a_note_about_a_sensitive_topic_still_waits_and_the_hint_says_so(session, monkeypatch) -> None:
    """Decision 6 kept: a note that is about health waits, in the hint too."""
    for content in ("Dentist check-up booked for the 21st", "GP says blood pressure is fine", "Physio for the shoulder"):
        manager.create_entry(session, content, category_name="Health")
    _owner_notebook(session)
    text = "Dentist appointment moved to Friday"
    call = lexical_filing.filing_call(session, text)
    assert call.category is None and call.held == "Health" and call.choices[0][0] == "Health"
    decided, offered, filing = _hint(session, text)
    assert decided is None and offered[0] == "Health" and "waits for you" in filing[0]["reason"]
    assert _saved(session, text, monkeypatch) is None


def test_the_saved_status_offers_what_the_hint_offered(client) -> None:
    for name, content in [("Hobbies", f"Gym session then {s}") for s in ("golf", "tennis", "a swim", "squash")] + [
        ("Study", f"Lecture notes on {w} for the semester") for w in ("databases", "ethics", "statistics")
    ]:
        client.post("/entries", json={"content": content, "category": name})
    text = "Uni is done, final assignment handed in. Gym later, then golf."
    hint = client.post("/read/offers", json={"content": text, "now": NOW.isoformat()}).json()["offers"]
    filing = [o for o in hint if o["kind"] == "filing"]
    made = client.post("/entries", json={"content": text}).json()
    status = client.get(f"/entries/{made['id']}/filing").json()
    for _ in range(200):
        if status["filing_state"] != "pending":
            break
        status = client.get(f"/entries/{made['id']}/filing").json()
    decided = next((o["value"]["category"] for o in filing if o["value"].get("decided")), None)
    assert (status["category"] if status["filed_by"] == "words" else None) == decided
    if decided is None:
        assert status["suggestions"][: len(filing)] == [o["value"]["category"] for o in filing]


@pytest.mark.parametrize("name, topic", [("Leisure", "Cycling & Bike Touring"), ("Practical life", "Vehicle Maintenance")])
def test_a_category_named_for_a_parent_reaches_its_children(name: str, topic: str) -> None:
    assert topic in taxonomy.name_topics(name)
    #: A name the pack already reads keeps its own topics, not its group's.
    assert "Employment Rights" not in taxonomy.name_topics("Work")
