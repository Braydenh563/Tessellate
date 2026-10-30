"""Composer stress run 2026-10-30: a 60-note notebook and 300 questions.

Each test pins a class of failure the run found, never one phrasing: money
asked about one thing summed every expense, an asking price, a balance still
due and an amount the note denies ("not $320 each way") were counted as paid,
and a refund was dropped instead of taken off."""

from __future__ import annotations

import json
from datetime import datetime

import pytest

from tessellate.api import routes_chat
from tessellate.core import config
from tessellate.entry import manager

NOW = datetime(2026, 10, 30, 12, 0)
NOTES = [
    ("Tap repair", "2026-09-18", ["home", "plumber"], "Paid $42 for the plumber to fix the kitchen tap. AUD. Settled, no reimbursement expected."),
    ("Food shops", "2026-10-03", ["groceries"], "Paid $68 at Fresh Basket and $24 at the market. Both were groceries, both AUD."),
    ("Bookshop receipt", "2026-10-05", ["books"], "Paid AUD $36 for my copy of Piranesi. One book."),
    ("Hobart flight paid", "2026-10-14", ["travel", "hobart"], "Paid AUD $320 for the return Hobart flight. This is the whole return fare, not $320 each way."),
    ("Secondhand desk", "2026-10-10", ["desk", "home"], "Paid AUD $180 for the desk. The listing said $200, but I negotiated."),
    ("Desk partial refund", "2026-10-12", ["desk", "refund"], "Seller refunded AUD $30 because a drawer runner was broken."),
    ("Saturday out", "2026-10-17", ["eating-out"], "Paid AUD $18 for lunch and $6 for coffee."),
    ("Hotel deposit", "2026-10-15", ["travel", "hobart"], "Paid AUD $89 as the Hobart hotel deposit. Another $160 is due on arrival, 14 November; I haven't paid that balance."),
    ("Trip changed to Hobart", "2026-10-12", ["travel", "hobart"], "New plan: Hobart with Jo. Revised overall budget AUD $900; this is a budget, not money spent."),
]


@pytest.fixture
def ask(client, session, monkeypatch):
    monkeypatch.setattr(config, "user_now", lambda _c: NOW)
    monkeypatch.setattr(routes_chat, "user_now", lambda _c: NOW)
    for title, day, tags, body in NOTES:
        entry = manager.create_entry(session, f"# {title}\n\n{body}", category_name="Expenses", tags=tags)
        entry.created_at = entry.updated_at = datetime.fromisoformat(day + "T09:00:00")
    session.commit()

    def go(question: str) -> str:
        text = ""
        with client.stream("POST", "/chat/stream", json={"question": question, "use_tools": True}) as response:
            for line in response.iter_lines():
                if line.strip() and (event := json.loads(line))["type"] == "answer":
                    text += event["delta"]
        return text

    return go


@pytest.mark.parametrize(("question", "lead"), [
    ("How much did I pay the plumber?", "You paid $42 for the plumber, going by Tap repair."),
    ("How much grocery spending have I recorded?", "You spent $92 on grocery, going by Food shops: Fresh Basket $68 and the market $24."),
    ("How much did I spend on eating out?", "You spent $24 on eating out, going by Saturday out: lunch $18 and coffee $6."),
    ("How much book spending is actually recorded?", "You paid $36 for your copy of Piranesi, going by Bookshop receipt."),
])
def test_money_about_one_thing_sums_only_that_thing(ask, question, lead):
    said = ask(question)
    assert said.startswith(lead), said


def test_a_total_leaves_out_asking_prices_denials_budgets_and_balances_and_takes_off_refunds(ask):
    said = ask("How much have I recorded I spent?")
    assert said.startswith("Your notes record $783 spent:"), said
    assert "Less $30 refunded (Desk partial refund), that is $753 net." in said, said
    assert "Not counted: $160 still due (Hotel deposit)." in said, said
    for wrong in ("$200", "$640", "$900"):
        assert wrong not in said, said


@pytest.mark.parametrize("question", [
    "What's the total of all recorded outgoing payments before refunds?",
    "And the net recorded spending after refunds, across the notebook?",
])
def test_total_and_net_phrasings_reach_the_sum(ask, question):
    assert ask(question).startswith("Your notes record $783 spent:")


def test_a_month_is_read_wherever_it_sits(ask):
    said = ask("What do my October payments add up to before refunds?")
    assert said.startswith("Your notes record $741 spent in October:"), said
    assert "$711 net" in said, said


def test_a_subject_with_a_balance_due_says_the_whole_and_what_is_owed(ask):
    said = ask("How much was the hotel altogether?")
    assert said.startswith("You paid $89, going by Hotel deposit."), said
    assert "Another $160 is still due (Hotel deposit), so $249 all up once that is paid." in said, said
    assert ask("How much is left on my hotel bill?").startswith("$160 is still to pay, going by Hotel deposit.")


def test_a_question_about_the_words_is_not_a_sum(ask):
    assert not ask("What did I mean by recorded spending?").startswith("Your notes record")


@pytest.mark.parametrize("message", [
    "That helped, thank you.", "You're a lifesaver lol", "bye for now", "Sorry, wrong chat.",
    "Can you keep things brief?", "Please use normal sentence case.", "Let's leave it there.", "Sweet, that's all.",
])
def test_closers_and_reactions_are_small_talk_not_a_search(message):
    """Each of these was searched for and answered with a note's sentence."""
    from tessellate.ai import intent

    assert intent.classify(message) == intent.SMALLTALK


def test_a_manner_word_is_never_reported_missing():
    """"What did I personally think of Piranesi" ended "It looks like these
    notes omit “personally”"; "my manager's preferred update style", "style"."""
    from tessellate.ai import composer

    notes = [{"id": 1, "content": "# Piranesi finished\n\nFinished Piranesi by Susanna Clarke. Loved the strange setting.", "created_at": NOW, "updated_at": NOW}]
    for question in ("What did I personally think of Piranesi?", "What is my preferred Piranesi style?"):
        said = composer.compose(question, notes)["text"]
        assert "personally" not in said.split("[")[-1] and "“style”" not in said, said


def _note(i, content, day):
    return {"id": i, "content": content, "created_at": day, "updated_at": day, "category": "Personal"}


def test_a_bare_checkbox_is_a_task_and_a_later_note_that_did_it_is_the_record():
    """"Did I renew my library membership?" answered "Yes" from the open
    "[ ] Renew library membership" (no bullet, so read as prose), and never
    saw the later "Renewed my library membership today"."""
    from tessellate.ai import composer_digest

    day = datetime(2026, 10, 20, 9)
    later = datetime(2026, 10, 29, 9)
    open_only = [_note(1, "# Errands\n\n[ ] Renew library membership\n[x] Buy stamps", day)]
    said = composer_digest.answer("did I renew my library membership", open_only, today=later.date())["text"]
    assert said.startswith("Not yet"), said
    done = [*open_only, _note(2, "# Membership sorted\n\nRenewed my library membership today.", later)]
    said = composer_digest.answer("did I renew my library membership", done, today=later.date())["text"]
    assert said.startswith("Yes, your note of 29 October says so: Renewed my library membership today"), said


_BALCONY = [
    _note(1, "# Balcony jobs\n\n[x] Repot basil.\n[ ] Buy mint.\n[ ] Patch the cracked blue pot.", datetime(2026, 10, 18, 9)),
    _note(2, "# Garden recap\n\nForgot to water the mint and it died. Didn't buy replacement mint in September.", datetime(2026, 9, 30, 9)),
]


@pytest.mark.parametrize(("question", "lead"), [
    ("Is buying mint still on my list?", "Yes, “Buy mint.” is still open in Balcony jobs."),
    ("Is the blue pot still outstanding?", "Yes, “Patch the cracked blue pot.” is still open in Balcony jobs."),
    ("Is repotting the basil done?", "Yes, “Repot basil.” is ticked off in Balcony jobs."),
    ("Has buying mint been finished?", "Not yet: “Buy mint.” is still open in Balcony jobs."),
    #: A line that says it did not happen is a no, never "Yes, says so".
    ("did I water the mint", "No, your note of 30 September says: Forgot to water the mint"),
])
def test_is_it_still_open_answers_from_the_checklist_line(question, lead):
    """Stress run 2026-10-30: "Is buying mint still on my list?" quoted the
    garden journal; "still outstanding" dumped the whole list."""
    from tessellate.ai import composer_digest

    said = composer_digest.answer(question, _BALCONY, today=datetime(2026, 10, 30).date())["text"]
    assert said.startswith(lead), said


def test_a_list_with_no_title_is_named_by_its_filing_not_its_first_item():
    """"What's still unchecked on my grocery list?" answered from a note
    called "[x] Milk"; "still unchecked" was not read as "still on"."""
    from tessellate.ai import composer_digest

    groceries = {**_note(1, "[x] Milk.\n[ ] Oats.\n[x] Red lentils.", datetime(2026, 10, 30, 9)), "tags": ["groceries", "checklist"]}
    said = composer_digest.answer("What's still unchecked on my grocery list?", [groceries], today=datetime(2026, 10, 30).date())["text"]
    assert said.startswith("1 still to do on your groceries list:"), said
    assert "Oats" in said and "[x]" not in said, said


_MOVED = [
    _note(1, "# Dentist booking\n\nDentist appointment booked for 3 November at 9 am. Routine check-up.", datetime(2026, 10, 13, 9)),
    _note(2, "# Dentist rescheduled\n\nMoved the dentist appointment from 3 November at 9 am to 4 November at 10:30 am. Old slot cancelled.", datetime(2026, 10, 27, 9)),
    _note(3, "# App planning\n\nLaunch target: 20 November. My export work due 6 November.", datetime(2026, 10, 6, 9)),
    _note(4, "# Revised app dates\n\nSam moved the launch to 27 November. My export deadline is now 9 November.", datetime(2026, 10, 23, 9)),
]


@pytest.mark.parametrize(("question", "lead"), [
    ("When's my dentist appointment now?", "You moved the dentist appointment from 3 November at 9 am to 4 November at 10:30 am"),
    ("When is the launch?", "Sam moved the launch to 27 November"),
    ("When is my export deadline?", "Your export deadline is now 9 November"),
])
def test_a_newer_note_that_corrects_the_subject_leads(question, lead):
    """Stress run 2026-10-30: "When's my dentist appointment now?" gave the
    first booking; the note that moved it came nowhere."""
    from tessellate.ai import composer_digest

    said = composer_digest.answer(question, _MOVED, today=datetime(2026, 10, 30).date())["text"]
    assert said.startswith(lead), said
