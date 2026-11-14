"""Chat recount rows L-chat-155 to 175, second batch: no-model paths on fake data."""

from __future__ import annotations

from datetime import datetime, timedelta
from pathlib import Path
from types import SimpleNamespace

from tessellate.core import reminder_notifier as rn

NOW = datetime(2026, 10, 11, 9, 0)


def test_notification_says_what_the_reminder_is_about_l172():
    row = SimpleNamespace(id=1, due_at=NOW - timedelta(seconds=5), done=False, alert_minutes=None, text="Call back", entry_id=7)
    fresh, _ = rn.due_now([row], set(), NOW, titles={7: "Dentist plan"})
    assert fresh[0].about == "Dentist plan"
    posted = []
    n = rn.ReminderNotifier.__new__(rn.ReminderNotifier)
    n.post = lambda title, body, rid: posted.append((title, body, rid))
    n.announce(fresh)
    assert posted == [("Reminder", "Call back, from your note \u201cDentist plan\u201d.", 1)]


def test_a_private_reminder_never_names_its_note_l172():
    row = SimpleNamespace(id=1, due_at=NOW - timedelta(seconds=5), done=False, alert_minutes=None, text="x", entry_id=7, workspace_id="p")
    fresh, _ = rn.due_now([row], set(), NOW, frozenset({"p"}), {7: "Secret"})
    assert fresh[0].about == "" and fresh[0].text == rn.PRIVATE_REMINDER


def test_light_rewrite_spells_out_shorthand_l175():
    from tessellate.ai import composer_tidy

    assert composer_tidy.tidy("see you b4 monday") == "See you before Monday."
    assert "with" in composer_tidy.tidy("coffee w/ sam").lower()
    assert "b4" not in composer_tidy.tidy("b4 lunch")


def test_light_rewrite_keeps_the_original_one_tap_away_l175():
    from tests._app_js import app_js_text

    js = app_js_text()
    # the composed pass takes its undo point before it replaces the draft
    assert "A composed pass (no model) has no delta to take the undo point at." in js
    assert "pushDraftUndo();" in js and "Undo puts it back." in js


def test_reasons_share_one_voice_l173(session):
    from tessellate.ai import composer_threads, lexical_filing, relations

    reasons = [
        relations._reason("similarity", []),
        relations._reason("entities", ["Sam"]),
        relations._reason("neighbours", ["Trip", "Plan"]),
        relations._reason("tags", ["gym"]),
        composer_threads.reason_said("They both describe the gym routine."),
    ]
    call = lexical_filing.filing_call(session, "pasta recipe with garlic and basil")
    if call.why:  # an empty notebook has no words to file by
        reasons.append(call.why)
    for text in reasons:
        assert text and text == text.strip()
        assert "!" not in text and "—" not in text
        assert not text.rstrip().endswith("."), text
        assert not text.lower().startswith(("i ", "i'", "we ")), text


def test_settings_are_explained_in_sentences_l161():
    from tessellate.ai import help_chat

    for question in (
        "what does the theme setting do",
        "what does auto backup do",
        "what does auto lock do",
        "what does the density setting do",
        "what does the notifications setting do",
    ):
        reply = help_chat.offline_answer(question, None)
        assert reply["sources"], question
        assert "I don't have help on that" not in reply["content"], question


def test_find_anything_answers_a_question_with_one_line_l170(client, session):
    from tessellate.core.database import Entry

    note = Entry(content="Passport renewal\nThe passport expires on 4 March 2027 and the renewal form is in the blue folder.")
    session.add(note)
    session.commit()
    got = client.get("/read/answer", params={"q": "when does my passport expire?", "now": "2026-11-14T09:00:00+00:00"}).json()
    assert got["answer"] and "passport" in got["answer"]["text"].lower() and note.id in got["answer"]["sources"]
    assert client.get("/read/answer", params={"q": "passport"}).json() == {"answer": None}


def test_finder_draws_the_answer_line_above_the_results_l170():
    from tests._app_js import app_js_text

    js = app_js_text()
    body = js[js.index("async function finderAnswerLine") : js.index("async function finderSearch")]
    assert "/read/answer?q=" in body and "run !== finderState.run" in body and "FINDER_OPEN.note" in body
    assert "finderAnswerLine(query, run);" in js


def test_a_long_note_has_a_gist_under_ninety_characters_l158():
    from tessellate.ai import composer_gist

    long = (
        "# Garden plan\n\nThe raised beds need new soil before the first frost arrives in October, "
        "and the compost bin should be turned twice a week until then. " + "More detail follows here. " * 12
    )
    line = composer_gist.gist(long)
    assert line and len(line) < 90 and line.startswith("The raised beds need new soil")
    assert "Garden plan" not in line
    assert composer_gist.gist("A short note about milk.") == ""
    assert composer_gist.gist("- one\n- two\n" * 40) == ""


def test_the_list_sends_the_gist_and_the_card_draws_it_l158(client, session):
    from tessellate.core.database import Entry
    from tests._app_js import app_js_text

    session.add(Entry(content="Plan the trip to the coast with the whole family this summer, booking the cottage early. " + "Details go here. " * 30))
    session.commit()
    rows = client.get("/entries", params={"preview": 120}).json()
    assert any(r["gist"].startswith("Plan the trip to the coast") for r in rows)
    assert "entry.gist && isLong" in app_js_text()


def test_an_answer_becomes_flashcards_and_a_reminder_with_undo_l155(client):
    from tests._app_js import app_js_text

    text = "Photosynthesis is the process plants use to turn light into sugar.\n\nQ: What do plants need?\nA: Light, water and carbon dioxide."
    got = client.get("/read/flashcards", params={"title": "Plants", "text": text}).json()
    assert got["count"] >= 1 and got["text"].startswith("# Flashcards: Plants") and "**Q:**" in got["text"]
    assert client.get("/read/flashcards", params={"text": "Hello."}).json() == {"count": 0, "text": ""}
    js = app_js_text()
    flash = js[js.index("async function askKeepAsFlashcards") : js.index("async function askKeepAsMap")]
    assert "pushUndo(" in flash and "reminderMadeUndo(made)" in flash and "/read/flashcards?" in flash


def test_note_toasts_name_the_note_l169():
    from tests._app_js import app_js_text

    js = app_js_text()
    for said in (
        "Moved “${noteNamePlain(entry.content, 40) || \"a note\"}” to the bin.",
        "Restored “${noteNamePlain(entry.content, 40) || \"a note\"}”.",
        "Duplicated “${noteNamePlain(content, 40) || \"a note\"}”.",
    ):
        assert said in js, said
    assert 'toastAction("Moved to the bin."' not in js
    library = (Path(__file__).resolve().parents[1] / "frontend" / "js" / "library.js").read_text(encoding="utf-8")
    assert "Archived \u201c${item.title}\u201d." in library and "Deleted \u201c${item.title}\u201d." in library


def test_autofill_is_composed_before_any_model_l174():
    from tessellate.ai import no_model_text, reminder_parser, tagging

    title = no_model_text.draft_title("Book the dentist for next week and ask about the crown.")
    assert title and len(title.split()) <= 7
    parsed = reminder_parser.read_by_rule("remind me friday 9am to ring the dentist", datetime(2026, 11, 14, 9, 0))
    assert parsed and "dentist" in parsed["text"].lower() and parsed["due_at"].hour == 9
    assert tagging.grounded("Leg day at the gym, squats and deadlifts", ["gym", "cooking"]) == ["gym"]
    #: The route reads by rule and only then asks a model.
    route = (Path(__file__).resolve().parents[1] / "src" / "tessellate" / "api" / "routes_reminders.py").read_text(encoding="utf-8")
    assert route.index("reminder_parser.read_by_rule(body.text") < route.index("reminder_parser.parse_reminder(")
