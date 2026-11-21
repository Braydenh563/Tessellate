"""The Guide's "From the help" side says how a misspelt question was read (ledger L53), as the composed side does."""

from __future__ import annotations

from tessellate.ai import help_chat


def test_the_system_answer_opens_with_the_line_that_says_how_it_was_read():
    reply = help_chat.offline_answer("how do i set a remnder")
    assert reply["content"].startswith(reply["system"]["content"].split("\n\n")[0])
    assert "how do i set a reminder" in reply["system"]["content"].split("\n\n")[0]
    assert reply["system"]["content"].split("\n\n")[1].startswith("### Reminders")


def test_a_question_spelt_right_has_no_reading_line():
    reply = help_chat.offline_answer("how do I set a reminder")
    assert reply["system"]["content"].startswith("### Reminders")


def test_how_do_i_set_a_reminder_starts_with_the_step():
    """Ledger L108: the first line is step 1, not how the tab is laid out."""
    content = help_chat.offline_answer("how do I set a reminder")["content"]
    assert content.startswith("1. Open the Reminders tab")


def test_a_path_leads_then_one_sentence_from_the_help():
    """Ledger L725 (owner, 2026-11-12): the click path first, still offline."""
    content = help_chat.offline_answer("where do I find the logs")["content"]
    assert content.startswith("**Where:** ") or content.startswith("It's in Settings, Logs.")
