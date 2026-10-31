"""The Writing room with no model offers only what the composer does well (INBOX 1488).

The owner, 2026-10-31, on thoughts "I am japanese" that came back "I am
japanese." with every chip on offer: "if certain features are useless or not
available with no ai they shouldnt be an option. make the writing room better
and more suitable for the composer when the ai isnt available". Two halves:
no pass hands its input back as if it had worked (here), and the page hides
what needs a model (`tests/test_writing_offline_view_1488.py`).
"""

from __future__ import annotations

from datetime import date

import pytest

from tessellate.ai import composer_tidy as ct
from tessellate.ai import composer_write as cw
from tessellate.ai import drafter

TODAY = date(2026, 10, 31)

INPUTS = [
    "I am japanese",
    "went to the dentist today. teeth fine but need a new filling. then picked up groceries and called mum about sunday",
    "so basically i think we should move the launch to march because the design isnt ready and honestly the team is tired. also need to tell finance",
    "- buy milk\n- call the plumber\n- send invoice to Dana\n- book flights for June",
    "1. Preheat the oven\n2. Mix the flour and eggs\n3. Pour into the tin\n4. Bake for 30 minutes",
    "The quarterly review showed that sales rose in the north region, while the south region stayed flat. Customer complaints dropped by a fifth, mostly because the new returns policy is simpler. We should keep the policy, and investigate why the south is stagnating; perhaps staffing is a factor.",
    "teh meeting is tomorow at 3pm and we need to discus the buget. i recieved the draft yesterday and it looked ok",
    "groceries: eggs, bread, butter, tomatoes and cheese",
    "# Plan\n\nWe're gonna sort the roof. Thanks.",
    "Already a tidy sentence.",
]
KINDS = ["note", "plain", "formal", "tidy", "expand", "bullets"]
REFINES = ["make it shorter", "add a summary", "as bullets", "as a list", "as prose", "formal", "tidy it up", "fix the spelling", "plainer"]


def _run(text: str, **kw) -> cw.Pass:
    return cw.compose(thoughts=text, draft="", today=TODAY, **{"kind": "note", **kw})


@pytest.mark.parametrize("text", INPUTS)
def test_no_pass_hands_its_input_back(text):
    """The class (INBOX 1488): a pass either changes the text or says why not."""
    done = [_run(text, kind=k) for k in KINDS] + [cw.compose(kind="note", thoughts="", draft=text, instruction=i, today=TODAY) for i in REFINES]
    for one in done:
        if one.text.strip():
            assert not ct.same(one.text, text), (one.shape, text)
        else:
            assert one.message and "!" not in one.message and chr(0x2014) not in one.message


def test_the_owners_line_is_tidied_and_the_rest_say_why_not():
    assert _run("I am japanese", kind="tidy").text == "I am Japanese."
    assert _run("I am japanese", kind="note").text == "I am Japanese."
    for kind in ("plain", "formal", "expand", "bullets"):
        assert _run("I am japanese", kind=kind).message


@pytest.mark.parametrize(
    ("text", "made"),
    [
        ("teh meeting is tomorow. i recieved it", "The meeting is tomorrow. I received it."),
        ("i dont know if im free on monday", "I don't know if I'm free on Monday."),
        ("my friend speaks french and german", "My friend speaks French and German."),
        ("we met the the supplier", "We met the supplier."),
        ("- buy milk\n- call mum", "- Buy milk\n- Call mum"),
        ("# Plan\n\nship it\n\n```\nprint('x')\n```", "# Plan\n\nShip it.\n\n```\nprint('x')\n```"),
    ],
)
def test_tidy_puts_spelling_capitals_apostrophes_and_stops_right(text, made):
    assert ct.tidy(text) == made
    assert ct.tidy(made) == made  # nothing left to do the second time


def test_tidy_ends_a_line_but_leaves_a_label_a_question_and_code():
    assert ct.tidy("what time is it?") == "What time is it?"
    assert ct.tidy("Shopping:") == "Shopping:"
    assert ct.tidy("done") == "Done"


@pytest.mark.parametrize(
    ("text", "made"),
    [
        ("we're gonna sort it, thanks", "We are going to sort it, thank you."),
        ("i cant make it, its ok", "I cannot make it, its acceptable."),
        ("The kids dont wanna go", "The children do not want to go."),
        ("It is done.", "It is done."),
    ],
)
def test_formal_spells_out_contractions_and_swaps_slang(text, made):
    assert ct.formally(text) == made


def test_formal_keeps_headings_lists_and_code():
    text = "# Don't panic\n\n- we're ready\n\n```\ndon't touch\n```"
    out = ct.formally(text)
    assert out.startswith("# Don't panic\n\n- We are ready") and out.endswith("```\ndon't touch\n```")


def test_a_refine_command_runs_tidy_and_formal_on_the_draft():
    done = cw.compose(kind="note", thoughts="", draft="teh plan dont change", instruction="fix the spelling", today=TODAY)
    assert done.text == "The plan don't change." and done.shape == "tidy"
    done = cw.compose(kind="note", thoughts="", draft="we cant go", instruction="make it formal", today=TODAY)
    assert done.text == "We cannot go." and done.shape == "formal"


def test_the_one_pass_kinds_work_from_the_thoughts_or_the_draft():
    assert cw.compose(kind="tidy", thoughts="teh end", draft="", today=TODAY).text == "The end."
    assert cw.compose(kind="plain", thoughts="", draft="We utilised it today.", today=TODAY).text == "We used it today."
    assert cw.compose(kind="rewrite", tone="formal", thoughts="", draft="we cant go", today=TODAY).text == "We cannot go."


def test_a_formal_tone_applies_to_a_written_up_note():
    done = cw.compose(kind="note", tone="formal", thoughts="we cant go. thanks", draft="", today=TODAY)
    assert "cannot" in done.text and "Thank you" in done.text


def test_bullets_to_prose_on_prose_says_so_rather_than_echoing():
    done = cw.compose(kind="expand", thoughts="This is prose. It has two sentences.", draft="", today=TODAY)
    assert done.text == "" and done.message == cw.NOTHING_TO_DO["expand"]


def test_a_summary_needs_three_sentences_and_key_words_five():
    short = "The roof leaks. We should fix it soon."
    assert cw.compose(kind="note", thoughts="", draft=short, instruction="add a summary", today=TODAY).message == cw.NOTHING_TO_DO["summary"]
    three = "The roof leaks badly in the rain. We should fix the roof before winter. The roofer quoted a fair price."
    out = cw.compose(kind="note", thoughts="", draft=three, instruction="add a summary", today=TODAY).text
    assert out.startswith("**Summary:**") and "Key words" not in out


# --- Write up my notes, by date --------------------------------------------------------


NOTES = [
    {"content": "Dentist visit. Teeth fine, one filling needed. Booked follow-up for 12 Nov.", "written": "2026-10-29"},
    {"content": "Standup. Shipped the login fix. Blocked on the API key from Priya.", "written": "2026-09-14"},
    {"content": "Ran 5k in 28 minutes. Knee felt fine.", "written": "2026-10-31"},
    {"content": "Call with Dana. She will pay by Friday.", "written": "2026-10-31"},
]


def test_write_up_groups_by_day_with_key_points_oldest_first():
    out = cw.write_up("", NOTES, TODAY)
    heads = [line for line in out.splitlines() if line.startswith("## ")]
    assert heads == ["## Monday 14 September", "## Thursday 29 October", "## Saturday 31 October"]
    # Two notes on one day share its heading; a note's first sentence names it
    # and the rest are its points (not the whole note pasted as its name).
    assert out.count("## Saturday 31 October") == 1
    assert "**Standup**:\n- Shipped the login fix\n- Blocked on the API key from Priya" in out
    assert "**Dentist visit**:\n- Teeth fine, one filling needed" in out
    assert "**Call with Dana**:\n- She will pay by Friday" in out


def test_write_up_never_leaves_a_dangling_stop_after_a_bare_name():
    out = cw.write_up("", [{"content": "Buy stamps", "written": "2026-10-31"}], TODAY)
    assert "**Buy stamps**, written today\n" in out + "\n" and "**." not in out and "**Buy stamps**." not in out


def test_write_up_spells_and_capitalises_the_thoughts():
    assert cw.write_up("i am japanese", None, TODAY) == "I am Japanese."


def test_write_up_from_one_year_back_names_the_year():
    out = cw.write_up("", [{"content": "Old note here. Some detail.", "written": "2025-03-02"}, {"content": "New one. A detail.", "written": "2026-10-31"}], TODAY)
    assert "## Sunday 2 March 2025" in out and "## Saturday 31 October\n" in out


# --- through the route -----------------------------------------------------------------


@pytest.mark.parametrize(
    ("body", "has"),
    [
        ({"thoughts": "i am japanese", "kind": "tidy"}, "I am Japanese."),
        ({"thoughts": "we cant go, thanks", "kind": "formal"}, "We cannot go, thank you."),
        ({"thoughts": "we utilised it today", "kind": "plain"}, "We used it today"),
        ({"draft": "teh plan", "kind": "note", "instruction": "proofread it"}, "The plan."),
    ],
)
def test_the_new_kinds_run_with_no_model(ai_client, fake_ollama, body, has):
    fake_ollama.running = False
    done = ai_client.post("/drafts/compose", json=body).json()
    assert done["draft"] == has and done["by"] == "composer" and done["said"] and not done["message"]
    assert not fake_ollama.chat_calls


def test_a_pass_with_nothing_to_do_keeps_the_draft_and_says_why(ai_client, fake_ollama):
    fake_ollama.running = False
    done = ai_client.post("/drafts/compose", json={"draft": "I am Japanese.", "kind": "tidy"}).json()
    assert done["draft"] == "I am Japanese." and done["message"] == cw.NOTHING_TO_DO["tidy"] and "by" not in done


def test_the_drafter_says_the_same_through_composed():
    done = drafter.composed("", "teh end", kind="tidy")
    assert done["draft"] == "The end." and done["by"] == "composer"
