"""The no-model composer's voice (22-10 bug doc): warmer, varied, shorter, and a
closing line that points at what to do next from what the notebook shows.

The answer length follows the Length picker already in the chat dock (quick,
normal, detailed): quick keeps the lead, detailed keeps everything. The
closing line is the app's own wording around two measured things: the title of
a note and whether it is the note the answer came from."""

from __future__ import annotations

import pytest

from tessellate.ai import composer_tone
from tessellate.entry import manager
from tests.test_composer_suggest_2210 import _ask

ANSWER = (
    "Ship the mobile app on 14 November, from your note of 25 October.\n\n"
    "**Three gates first:** beta feedback, onboarding, pricing.\n\n"
    "**Also:** owner is Ana.\n\n"
    "It's your only note on that so far."
)


@pytest.mark.parametrize(("mode", "length"), [("quick", "short"), ("normal", "normal"), ("detailed", "long"), ("", "normal"), ("weird", "normal"), (None, "normal")])
def test_length_follows_the_pickers_modes(mode, length):
    assert composer_tone.length(mode) == length


def test_short_keeps_the_lead_only():
    out = composer_tone.fit(ANSWER, "short")
    assert out == "Ship the mobile app on 14 November, from your note of 25 October."


def test_normal_and_long_keep_everything():
    assert composer_tone.fit(ANSWER, "normal") == ANSWER
    assert composer_tone.fit(ANSWER, "long") == ANSWER


def test_short_keeps_a_one_paragraph_answer_whole():
    assert composer_tone.fit("Only this.", "short") == "Only this."


def test_closing_names_the_recent_work():
    line = composer_tone.closing(recent=["Harbor launch plan", "Dentist"], seed="s")
    assert "Harbor launch plan" in line
    assert "!" not in line and chr(0x2014) not in line
    #: A line may open on the quoted title ("“Harbor launch plan” is your newest note."):
    #: the frame set has always held those, and the seed's pick once avoided them by luck.
    assert line.lstrip("\u201c\"")[0].isupper()


def test_closing_varies_with_the_seed():
    lines = {composer_tone.closing(recent=["Harbor launch plan"], seed=f"seed{n}") for n in range(12)}
    assert len(lines) >= 3


def test_closing_is_stable_for_one_seed():
    a = composer_tone.closing(recent=["Harbor launch plan"], seed="same")
    b = composer_tone.closing(recent=["Harbor launch plan"], seed="same")
    assert a == b


def test_no_notes_no_closing():
    assert composer_tone.closing(recent=[], seed="s") == ""


def _seed(session) -> None:
    manager.create_entry(session, "# Dentist\n\nCheck-up booked for the 21st. Ask about the night guard.")
    manager.create_entry(
        session, "# Harbor launch plan\n\nShip the mobile app on 14 November. Three gates first: beta feedback, onboarding, pricing. Owner is Ana."
    )
    session.commit()


def test_a_composed_answer_ends_with_a_next_step_from_recent_work(client, session):
    _seed(session)
    from tests.test_composer_route_688 import _ask as streamed

    out = streamed(client, "when is the dentist")
    text = out["text"]
    assert "Check-up booked for the 21st" in text
    #: The next step names a note the answer used, never the newest note when
    #: that is about something else (composer5, item 1).
    assert "Harbor launch plan" not in text
    #: The next step is the follow-up chips (INBOX 1466), not a last line.
    assert any("Dentist" in chip for chip in out["grounding"][0]["next"])
    assert "Next, I can" not in text


def test_quick_mode_is_shorter_than_detailed(client, session):
    _seed(session)
    quick = _ask(client, "What is the Harbor launch plan?", mode="quick")["text"]
    detailed = _ask(client, "What is the Harbor launch plan?", mode="detailed")["text"]
    assert len(quick) < len(detailed)
    assert "Three gates" not in quick and "Three gates" in detailed
    assert "Ship the mobile app" in quick


def test_the_help_says_a_persona_needs_a_model():
    from tessellate.ai import help_chat

    text = " ".join(str(t.get("body", "")) for t in help_chat.HELP_TOPICS if t.get("id") == "notebook-questions")
    assert "persona" in text.lower() and "no model" in text.lower()
