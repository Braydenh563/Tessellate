"""The Writing room with no model (INBOX 1466, CHAT_PLAN decision 75).

The owner: "can the writing room be made more useful with the composer?? can
the composer be able to do some of it reasonably well?" Each pass the
composer does by rule is tested on several phrasings and shapes of text; the
passes that need a model say so in one line and leave the draft as it was.
"""

from __future__ import annotations

import json
import re
from datetime import date

import pytest

from tessellate.ai import composer_write as cw

TODAY = date(2026, 10, 30)

PROSE = [
    (
        "We met with the supplier on Monday. Basically, they said the price will go up by 5 percent. "
        "In order to keep costs down, we should use the old stock first. I think we should also ask for a discount."
    ),
    "The garden needs work. Actually the fence is broken; the shed roof leaks. We should fix the fence first.",
    "# Trip\n\nFlights are booked for May. The hotel is near the station. We still need travel insurance.",
    "Dr. Lee moved the appointment to Friday. I need to bring the scan. Parking is behind the clinic.",
    "So the launch slipped a week. The designs are done. Just the copy is left, and the copy is late.",
]


def _bullets(text: str) -> list[str]:
    return [line[2:] for line in text.splitlines() if line.startswith("- ")]


@pytest.mark.parametrize("prose", PROSE)
def test_prose_to_bullets_is_one_idea_a_bullet_with_the_fillers_trimmed(prose):
    out = cw.to_bullets(prose)
    items = _bullets(out)
    body = prose.split("\n\n")[-1]
    # At least one bullet per sentence, none longer than the sentence it came from.
    assert len(items) >= len(cw.sentences(body))
    for item in items:
        assert item[0].isupper() and not item.endswith(".")
        assert not re.search(r"\b(?:basically|actually|just|in order to)\b", item, re.I), item
        assert not item.lower().startswith(("so ", "and "))
    assert len(items) == len({i.lower() for i in items})
    if prose.startswith("# "):
        assert out.startswith("# Trip")


def test_prose_to_bullets_drops_a_repeat_and_a_sentence_that_says_nothing():
    out = cw.to_bullets("The price goes up in June. They basically said the price goes up in June. Anyway, that's it.")
    assert _bullets(out) == ["The price goes up in June"]


@pytest.mark.parametrize(
    ("bullets", "expected"),
    [
        ("- met supplier Monday\n- price up 5 percent\n- use old stock first\n- ask for a discount",
         "Met supplier Monday. Also, price up 5 percent. Use old stock first. Finally, ask for a discount."),
        ("1. Preheat the oven\n2. Mix the flour and eggs\n3. Bake for 20 minutes",
         "First, preheat the oven. Then mix the flour and eggs. Finally, bake for 20 minutes."),
        ("* Fence is broken\n* Shed roof leaks", "Fence is broken. Also, shed roof leaks."),
        ("- First call the bank\n- Then cancel the card\n- Finally order a new one",
         "First, first call the bank."),
    ],
)
def test_bullets_to_prose_makes_capitalised_sentences_joined_by_connectives(bullets, expected):
    out = cw.to_prose(bullets)
    if expected.endswith("first call the bank."):
        # Items that already say "then" are steps: no "Also", and every one a sentence.
        assert "Also" not in out and out.count(".") == 3
        return
    assert out == expected


def test_bullets_to_prose_keeps_a_sub_item_after_its_parent_and_names_and_i():
    out = cw.to_prose("- Ask Sam about the budget\n  - due Friday\n- I can do the slides\n- NASA talk on Monday")
    assert out.startswith("Ask Sam about the budget. Due Friday.")
    assert "I can do the slides." in out and "NASA talk" in out


@pytest.mark.parametrize(
    ("text", "plain_bit", "gone"),
    [
        ("We utilised the remainder of the budget.", "used the rest", "utilised"),
        ("In order to save money we are purchasing fewer licences.", "To save money", "In order to"),
        ("However, the team was unable to obtain approval.", "But, the team", "However"),
        ("Please inform the landlord prior to moving out.", "tell the landlord before", "prior to"),
        ("Commence the backup at approximately 9.", "Start the backup at about 9", "Commence"),
        ("We REQUIRE additional chairs.", "NEED extra chairs", "additional"),
    ],
)
def test_say_it_plainly_swaps_long_words_and_keeps_case(text, plain_bit, gone):
    out = cw.plainly(text)
    assert plain_bit in out and gone not in out


@pytest.mark.parametrize(
    "long",
    [
        "We started the project in March with a small team of four people and a modest budget, but the scope grew every month and by the summer we had twice the work and the same number of people.",
        "The landlord said the boiler would be replaced before winter because the old one failed its safety check twice, so we should keep the receipts for the engineer's visits until the work is done.",
        "I read the whole report on the train this morning and most of it was about the new pricing model; the part about the old customers was missing entirely and nobody seems to have noticed that yet.",
    ],
)
def test_say_it_plainly_splits_a_long_sentence_at_its_middle_joint(long):
    out = cw.plainly(long)
    said = cw.sentences(out)
    assert len(said) >= 2
    assert all(len(s.split()) <= cw.LONG_WORDS for s in said)
    assert all(s[0].isupper() for s in said)


@pytest.mark.parametrize("prose", PROSE + [
    "Honestly the meeting was long. The meeting was really long. We agreed the budget is 2,000. Sam will send the minutes. Anyway, that's it.",
])
def test_shorter_is_shorter_and_keeps_the_first_sentence(prose):
    out = cw.shorter(prose)
    assert len(out.split()) < len(prose.split())
    first = cw.sentences(prose.split("\n\n")[-1])[0]
    assert cw.trim(cw.concise(first)).rstrip(".") in out


def test_shorter_drops_fillers_and_repeats_before_any_sentence_with_news():
    out = cw.shorter(PROSE[0] + " They basically said the price will go up by five percent. Anyway, that's it.")
    assert "discount" in out and "old stock" in out
    assert out.count("price will go up") == 1 and "Anyway" not in out and "Basically" not in out


@pytest.mark.parametrize("text", [PROSE[0], PROSE[2], "- one point about rent\n- another point about rent and bills\n- a third about bills", PROSE[4]])
def test_add_a_summary_puts_the_key_sentence_under_the_title_once(text):
    once = cw.with_summary(text)
    twice = cw.with_summary(once)
    assert once.count("**Summary:**") == 1 and twice.count("**Summary:**") == 1
    if text.startswith("# "):
        assert once.startswith("# Trip\n\n**Summary:**")
    summary = re.search(r"\*\*Summary:\*\* (.*)", once).group(1)
    # Every word of the summary is the text's own: nothing invented.
    own = set(re.findall(r"[a-z0-9']+", text.lower())) | {"to"}
    assert set(re.findall(r"[a-z0-9']+", summary.lower())) - {"key", "words"} <= own


SOURCES = [
    {"content": "# Supplier call\nThey will raise prices in June. The rep was called Dana. We can order old stock until May.", "written": "2026-10-20"},
    {"content": "Budget review: we have 2000 left for stock. Need approval from finance for more.", "written": "2026-09-02"},
    {"content": "- buy seeds\n- check the shed\n- book the van for Saturday", "written": "2026-10-29"},
]


def test_write_up_is_dated_grouped_and_names_each_note():
    out = cw.write_up("met supplier, price going up. need to decide on stock", SOURCES, TODAY)
    assert out.startswith("# Met supplier\n\nMet supplier, price going up. Need to decide on stock.")
    # Oldest first, grouped by month when the notes span more than one.
    assert out.index("## September 2026") < out.index("**Budget review**, written on 2 September:") < out.index("## October 2026")
    assert "**Supplier call**, written last week:" in out
    assert "**Buy seeds**, written yesterday:" in out
    # Each note's key points, not its opening pasted whole.
    assert "- We have 2000 left for stock" in out and "Budget review: we have" not in out
    assert "- They will raise prices in June" in out


@pytest.mark.parametrize(
    ("sources", "title"),
    [
        (SOURCES[:1], "# Supplier call"),
        ([{"content": "Budget review: 2000 left.", "written": "2026-10-29"}, {"content": "Travel budget is 500 this year.", "written": "2026-10-29"}], "# Notes on budget"),
        ([{"content": "Rent is due on the 1st.", "written": ""}, {"content": "The cat needs a vet visit.", "written": "2026-10-30"}], "# From my notes"),
    ],
)
def test_write_up_from_notes_alone_is_titled_from_them(sources, title):
    out = cw.write_up("", sources, TODAY)
    assert out.startswith(title + "\n")
    assert "## " not in out  # one month, or undated: no month headings


@pytest.mark.parametrize(
    ("instruction", "kind"),
    [
        ("make it shorter", "shorter"), ("shorten this", "shorter"), ("tighten it up", "shorter"),
        ("add a summary", "summary"), ("tl;dr at the top", "summary"), ("summarise it", "summary"),
        ("simplify the wording", "plain"), ("say it more plainly", "plain"),
        ("turn it into bullet points", "bullets"), ("as a list", "bullets"),
        ("write it out as paragraphs", "expand"),
        ("make a flowchart", "diagram"), ("turn this into a timeline", "diagram"), ("draw a mind map", "diagram"),
        ("make it sound formal", ""), ("add a joke", ""),
    ],
)
def test_a_refine_instruction_picks_the_pass_or_none(instruction, kind):
    assert cw.refine_kind(instruction) == kind


@pytest.mark.parametrize("kind", ["continue", "translate-es", "translate-ja"])
def test_carrying_on_and_translating_say_they_need_a_model(kind):
    done = cw.compose(kind=kind, thoughts="", draft="My draft.", today=TODAY)
    assert done.text == ""
    assert "needs a model" in done.message and "Settings, Models" in done.message
    assert chr(0x2014) not in done.message and "!" not in done.message


def test_an_instruction_the_composer_cannot_do_says_what_it_can():
    done = cw.compose(kind="note", thoughts="", draft="My draft.", instruction="make it sound formal", today=TODAY)
    assert done.text == "" and "shorter, a summary, plain words" in done.message


def test_a_rewrite_in_any_voice_but_plain_needs_a_model_and_plain_works():
    assert cw.compose(kind="rewrite", tone="formal", thoughts="", draft="We utilised it.", today=TODAY).text == ""
    assert cw.compose(kind="rewrite", tone="plain", thoughts="", draft="We utilised it.", today=TODAY).text == "We used it."


def test_write_up_with_a_draft_already_there_adds_below_it():
    done = cw.compose(kind="note", thoughts="also check the van", draft="# Plan\n\nThe draft I wrote.", today=TODAY)
    assert done.text.startswith("# Plan\n\nThe draft I wrote.\n\n") and done.text.endswith("Check the van.")


# --- the route ---------------------------------------------------------------------


def _stream(response) -> list[dict]:
    return [json.loads(line) for line in response.text.splitlines() if line.strip()]


@pytest.mark.parametrize(
    ("body", "has"),
    [
        ({"thoughts": PROSE[0], "kind": "bullets"}, "- We met with the supplier on Monday"),
        ({"thoughts": "- the gate is open\n- the fence is broken\n- the roof leaks", "kind": "expand"}, "Also, the fence is broken."),
        ({"draft": PROSE[0], "kind": "rewrite", "tone": "plain"}, "We met with the supplier"),
        ({"draft": PROSE[0], "kind": "note", "instruction": "add a summary"}, "**Summary:**"),
        ({"draft": "1. Boil water\n2. Add pasta\n3. Drain", "kind": "note", "instruction": "make a flowchart"}, "```mermaid\nflowchart TD"),
    ],
)
def test_the_writing_room_composes_with_no_model(ai_client, fake_ollama, body, has):
    fake_ollama.running = False
    done = ai_client.post("/drafts/compose", json=body).json()
    assert has in done["draft"]
    assert done["by"] == "composer" and done["said"] and not done["message"]
    events = _stream(ai_client.post("/drafts/compose/stream", json=body))
    assert [e["type"] for e in events] == ["done"] and events[0]["by"] == "composer" and has in events[0]["draft"]
    assert not fake_ollama.chat_calls


def test_write_up_my_notes_reads_the_picked_notes_with_their_dates(ai_client, fake_ollama):
    fake_ollama.running = False
    made = ai_client.post("/entries", json={"content": "Budget review: we have 2000 left for stock. Need approval for more."}).json()
    done = ai_client.post("/drafts/compose", json={"thoughts": "", "kind": "note", "source_ids": [made["id"]]}).json()
    assert done.get("by") == "composer", done
    assert done["draft"].startswith("# Budget review\n\n**Budget review**, written today:")
    assert "- We have 2000 left for stock" in done["draft"]


@pytest.mark.parametrize("kind", ["continue", "translate-fr"])
def test_the_route_says_a_model_pass_needs_a_model_and_keeps_the_draft(ai_client, fake_ollama, kind):
    fake_ollama.running = False
    events = _stream(ai_client.post("/drafts/compose/stream", json={"draft": "My careful draft.", "kind": kind}))
    assert events[0]["draft"] == "My careful draft." and "needs a model" in events[0]["message"]
    assert "by" not in events[0]


def test_with_a_model_the_model_still_does_the_work(ai_client, fake_ollama):
    """Decision 75: with a model on, nothing here runs."""
    fake_ollama.librarian_reply = "- From the model"
    done = ai_client.post("/drafts/compose", json={"thoughts": PROSE[0], "kind": "bullets"}).json()
    assert done["draft"] == "- From the model" and "by" not in done
