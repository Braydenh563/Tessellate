"""Meeting decisions and actions read with no model, beyond English cue words (L665):
one minute per language the app tells apart (French, Spanish, German, Italian, Portuguese, Dutch)."""

from __future__ import annotations

from datetime import datetime

import pytest

from tessellate.entry import meetings, meetings_cues

NOW = datetime(2026, 11, 12, 10, 0)

#: language, a decision line, an undecided line (not a decision), an action line under a mark,
#: a named attendee taking a task on with the language's modal.
MINUTES = {
    "spanish": ("Decidimos lanzar el producto en marzo.", "Todavía no se ha decidido el presupuesto.", "Acción: enviar el informe a Marta.", "Marta va a enviar el informe"),
    "french": ("Nous avons décidé de lancer en mars.", "Le budget n'est pas encore décidé.", "À faire: envoyer le rapport à Marc.", "Marc doit envoyer le rapport"),
    "german": ("Wir haben beschlossen, im März zu starten.", "Das Budget ist noch nicht entschieden.", "Aufgabe: den Bericht an Anna schicken.", "Anna wird den Bericht senden"),
    "italian": ("Abbiamo deciso di partire a marzo.", "Il budget non è ancora deciso.", "Azione: inviare il rapporto a Luca.", "Luca deve inviare il rapporto"),
    "portuguese": ("Decidimos lançar em março.", "O orçamento ainda não foi decidido.", "Tarefa: enviar o relatório à Rita.", "Rita vai enviar o relatório"),
    "dutch": ("We hebben besloten in maart te starten.", "Het budget is nog niet besloten.", "Actie: het rapport naar Joris sturen.", "Joris moet het rapport sturen"),
}
ATTENDEE = {"spanish": "Marta", "french": "Marc", "german": "Anna", "italian": "Luca", "portuguese": "Rita", "dutch": "Joris"}


def test_a_cue_table_exists_for_each_language_the_app_tells_apart():
    from tessellate.ai import note_language

    assert set(meetings_cues.CUES) == {n for n in note_language._WORDS if n != "english"}


@pytest.mark.parametrize("language", sorted(MINUTES))
def test_a_decision_is_found_and_an_open_question_is_not(language):
    decision, undecided, _mark, _commit = MINUTES[language]
    found = meetings.find_items(f"{decision}\n{undecided}", now=NOW)
    assert [d["text"] for d in found["decisions"]] == [decision.rstrip(".")], (language, found)
    assert found["actions"] == []


@pytest.mark.parametrize("language", sorted(MINUTES))
def test_a_marked_line_is_an_action_and_a_named_attendee_taking_a_task_is_too(language):
    _decision, _undecided, mark, commit = MINUTES[language]
    who = ATTENDEE[language]
    marked = meetings.find_items(mark, people=[who], now=NOW)
    assert len(marked["actions"]) == 1 and marked["actions"][0]["owner"] == who, (language, marked)
    said = meetings.find_items(commit + ".", people=[who], now=NOW)
    assert len(said["actions"]) == 1 and said["actions"][0]["owner"] == who, (language, said)


def test_a_capitalised_noun_before_a_modal_is_not_an_owner_unless_it_is_an_attendee():
    line = "Wetter wird morgen schlechter."
    assert meetings.find_items(line, now=NOW)["actions"] == []
    assert meetings.find_items(line, people=["Wetter"], now=NOW)["actions"]


def test_the_english_rules_are_unchanged():
    found = meetings.find_items("We decided to ship on Friday.\nSam will send the deck.\nNobody agreed on the budget.", now=NOW)
    assert [d["text"] for d in found["decisions"]] == ["We decided to ship on Friday"]
    assert [a["owner"] for a in found["actions"]] == ["Sam"]
