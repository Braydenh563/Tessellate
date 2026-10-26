"""The composer's wider vocabulary and its two voices (2026-10-06, the owner:
"expand the available sentence sections, grammar, lingo, understanding ...
more natural language and professional language options").

Every entry of `ai/composer_tables.py` is exercised: each phrase variant is
reached by some question, in the voice it belongs to; each synonym group
reads as a group; each wrapper, comparison form and lead-in does what it says;
each small-talk line follows the copy rules. The rule that facts stay quoted
from the notes is held by the eval's traceability check, run in both voices.
"""

from __future__ import annotations

import pytest

from tessellate.ai import composer, composer_tables
from tests import _composer_eval as ev
from tests.test_composer_688 import NOTES, TODAY, _note, ask

EM_DASH = chr(0x2014)

# --- the tables are wider -------------------------------------------------------------


def test_the_tables_are_at_least_twice_what_they_were():
    assert len(composer.PHRASES) >= 198
    assert len(composer.SYNONYM_GROUPS) >= 40
    assert len(composer.LEAD_INS) >= 60
    assert len(composer._WRAPPERS) >= 24
    assert len(composer._CONTRACTIONS) >= 4
    assert len(composer._COMPARE_SIDES) >= 6
    assert sum(len(lines) for lines in composer.SOCIAL.values()) >= 68
    assert len(composer.NEXT_STEPS) >= 6


def test_every_joining_phrase_and_opener_has_both_voices():
    for key in ("open_notes", "open_wrote", "going_by", "and_join", "later_on", "timeline", "each_side", "missing"):
        assert len(composer_tables.VOICE_VARIANTS["natural"][key]) >= 3
        assert len(composer_tables.VOICE_VARIANTS["professional"][key]) >= 3


def test_an_unknown_voice_is_the_natural_one():
    assert composer_tables.voice_of("shouty") == "natural"
    assert composer_tables.voice_of(None) == "natural"
    assert composer_tables.voice_of("professional") == "professional"
    assert composer.compose("When is the dentist?", NOTES, today=TODAY, voice="shouty")["text"] == composer.compose(
        "When is the dentist?", NOTES, today=TODAY
    )["text"]


# --- phrase variants -----------------------------------------------------------------

_KEYS = [(voice, key) for voice, table in composer_tables.VOICE_VARIANTS.items() for key in sorted(table)]


def _voiced_over_questions(voice: str, key: str) -> set[str]:
    seen = set()
    for i in range(400):
        out = composer._Answer({}, TODAY)
        out.voice = voice
        out.question = f"question number {i} about the harbor"
        seen.add(out.voiced(key))
    return seen


@pytest.mark.parametrize(("voice", "key"), _KEYS)
def test_every_variant_of_a_phrase_is_reached_by_some_question(voice, key):
    assert _voiced_over_questions(voice, key) == set(composer_tables.VOICE_VARIANTS[voice][key])


@pytest.mark.parametrize(("name", "key"), sorted(composer_tables.CANON.items()))
def test_a_variant_keeps_the_shape_of_the_phrase_it_varies(name, key):
    variant, original = composer.PHRASES[name], composer.PHRASES[key]
    assert variant.endswith(" ") == original.endswith(" ") or key.startswith("wrote_on")
    assert variant.startswith(" ") == original.startswith(" ") or key.startswith("wrote_on")
    assert variant.endswith(("?", ".")) == original.endswith(("?", ".")) or key.startswith(("wrote_on", "of_found", "across_found"))
    assert EM_DASH not in variant and "!" not in variant and "Oops" not in variant


@pytest.mark.parametrize("voice", composer_tables.VOICES)
def test_the_two_halves_of_a_pair_take_the_same_variant(voice):
    for i in range(60):
        out = composer._Answer({}, TODAY)
        out.voice = voice
        out.question = f"when did I write about thing {i}"
        a, b = out.voiced("wrote_on_a"), out.voiced("wrote_on_b")
        table = composer_tables.VOICE_VARIANTS[voice]
        assert table["wrote_on_a"].index(a) == table["wrote_on_b"].index(b)


@pytest.mark.parametrize("voice", composer_tables.VOICES)
def test_the_professional_voice_never_uses_a_natural_only_opener_and_the_reverse(voice):
    other = "natural" if voice == "professional" else "professional"
    mine = {composer.PHRASES[k] for keys in composer_tables.VOICE_VARIANTS[voice].values() for k in keys}
    theirs = {composer.PHRASES[k] for keys in composer_tables.VOICE_VARIANTS[other].values() for k in keys} - mine
    for question in ("What is the Harbor launch plan?", "When is the dentist?", "Is the deposit paid?", "What about Lisbon?"):
        result = ask(question, NOTES, voice=voice)
        used = {p[1] for p in result["parts"] if p[0] == "template"}
        assert not (used & theirs), (voice, question, used & theirs)


def test_the_same_question_is_answered_in_the_same_words_each_time():
    for voice in composer_tables.VOICES:
        first = ask("What about the beta testers?", NOTES, voice=voice)["text"]
        assert ask("What about the beta testers?", NOTES, voice=voice)["text"] == first


def test_the_voices_differ_and_both_quote_the_notes_unchanged():
    natural = ask("When is the launch date?", NOTES)
    professional = ask("When is the launch date?", NOTES, voice="professional")
    assert natural["grounding"] == professional["grounding"]
    #: Only the connecting words change: the quoted sentences are the same.
    quotes = lambda r: [p[1] for p in r["parts"] if p[0] == "quote"]  # noqa: E731
    assert quotes(natural) == quotes(professional)


@pytest.mark.parametrize("voice", composer_tables.VOICES)
def test_the_eval_keeps_the_rule_in_both_voices(voice):
    rows = ev.run(voice=voice)
    assert [r["failures"] for r in rows if r["failures"]] == []
    assert ev.summary(rows)["grounded"] == 1.0


def test_the_professional_voice_gives_a_professional_nothing_found():
    out = composer.compose("What is the capital of Peru?", NOTES, today=TODAY, voice="professional")
    assert out["text"].startswith(tuple(composer.PHRASES[k] for k in composer_tables.VOICE_VARIANTS["professional"]["none_found"]))
    assert out["text"].endswith(tuple(composer.PHRASES[k] for k in composer_tables.VOICE_VARIANTS["professional"]["nothing_ask"]))
    assert out["text"] != composer.compose("What is the capital of Peru?", NOTES, today=TODAY)["text"]


def test_a_voice_gives_more_distinct_openers_than_one_fixed_phrase():
    questions = [
        "What is the Harbor launch plan?", "What about the public API?", "Tell me about the dentist",
        "What about Lisbon?", "What did the beta feedback say?", "What about the reading list?",
        "Is the deposit paid?", "How many testers are active?", "Where is the spare key?", "What is the status of the sync rewrite?",
    ]
    for voice in composer_tables.VOICES:
        openings = {ask(q, NOTES, voice=voice)["text"].split("\n", 1)[0][:18] for q in questions}
        assert len(openings) >= 4, openings


# --- synonyms -----------------------------------------------------------------------


@pytest.mark.parametrize("group", composer_tables.EXTRA_SYNONYM_GROUPS, ids=lambda g: g[0])
def test_each_new_synonym_group_reads_as_one_thing_said_several_ways(group):
    stems = {composer._stem(w) for w in group}
    for stem in stems:
        others = composer._alternatives(stem)
        assert (stems - {stem}) <= others, (group, stem)
        assert composer._holds(stem, set(stems))


@pytest.mark.parametrize(
    ("question", "title", "body"),
    [
        ("When is the dentist booked?", "Teeth check", "The dental check-up is on the 21st."),
        ("What is the salary?", "Offer", "The wage is fixed for a year."),
        ("Where is the spare key?", "House", "The key lives in the kitchen drawer."),
        ("When does my flight leave?", "Trip", "The plane departs at nine in the morning."),
        ("Who is my flatmate?", "Home", "My housemate is called Sam."),
        ("What is the deadline?", "Work", "The cutoff for the report is Friday."),
        ("What is the insurance?", "Car", "The insurer is called Acme."),
        ("What am I worried about?", "Mood", "I felt anxious about the interview."),
        ("What was the invoice?", "Money", "The bill came to 120 pounds."),
        ("What is the exam about?", "Study", "The quiz covers chapter four."),
    ],
)
def test_a_new_synonym_finds_the_note_that_says_the_same_thing_differently(question, title, body):
    notes = [_note(1, f"# {title}\n\n{body}", 3), _note(2, "# Other\n\nNothing about it here at all.", 2)]
    result = composer.compose(question, notes, today=TODAY)
    assert result["grounding"] and result["grounding"][0]["note_id"] == 1


# --- comparison words -----------------------------------------------------------------

_COMPARE_CASES = [
    ("Is Lisbon cheaper than Porto?", ("Lisbon", "Porto")),
    ("Is the Lisbon flat cheaper than the Porto flat", ("the Lisbon flat", "the Porto flat")),
    ("Alfama is better than Príncipe Real", ("Alfama", "Príncipe Real")),
    ("Which is faster, the old list or the new list?", ("the old list", "the new list")),
    ("Which is cheaper: Lisbon or Porto", ("Lisbon", "Porto")),
    ("Lisbon compared with Porto", ("Lisbon", "Porto")),
    ("How does Lisbon compare to Porto?", ("Lisbon", "Porto")),
    ("How does Alfama stack up against Príncipe Real?", ("Alfama", "Príncipe Real")),
    ("What are the pros and cons of Lisbon and Porto?", ("Lisbon", "Porto")),
    ("Pros and cons of Alfama vs Príncipe Real", ("Alfama", "Príncipe Real")),
    ("How is Lisbon different from Porto?", ("Lisbon", "Porto")),
    ("Lisbon differs from Porto", ("Lisbon", "Porto")),
    ("Comparison of Lisbon and Porto", ("Lisbon", "Porto")),
    ("Comparison between Alfama and Príncipe Real", ("Alfama", "Príncipe Real")),
    ("Are the beta testers more active than the alpha testers?", ("the beta testers", "the alpha testers")),
    ("Is the sync rewrite easier than the old sync", ("the sync rewrite", "the old sync")),
    ("What is the difference between Alfama and Príncipe Real?", ("Alfama", "Príncipe Real")),
    ("Lisbon versus Porto", ("Lisbon", "Porto")),
    ("Compare Lisbon with Porto", ("Lisbon", "Porto")),
]


@pytest.mark.parametrize(("question", "sides"), _COMPARE_CASES)
def test_a_comparison_in_other_words_names_its_two_sides_and_is_read_as_a_comparison(question, sides):
    assert composer.compare_sides(question) == sides
    assert composer.classify(question) == "compare"


@pytest.mark.parametrize("word", sorted(composer_tables.EXTRA_ASKING_WORDS))
def test_a_comparison_word_is_never_the_subject(word):
    assert word not in composer.subject_terms(f"is the harbor plan {word} than the sync plan")


@pytest.mark.parametrize(
    "question",
    ["How much cheaper is the flat?", "What is the better option?", "pros and cons of working remotely", "Is the list faster now?"],
)
def test_a_question_with_one_side_is_not_read_as_a_comparison(question):
    assert composer.classify(question) != "compare"


def test_a_cheaper_than_question_draws_both_sides_from_the_notes():
    result = ask("Is Lisbon cheaper than Porto?", NOTES)
    assert result["shape"] == "compare"
    assert "Lisbon" in result["text"] and "Porto" in result["text"]


# --- wrappers, trailers and contractions -------------------------------------------------

_WRAPPER_CASES = [
    ("Could you kindly advise when the dentist is?", "when the dentist is?"),
    ("Would you mind telling me when the deposit is due?", "when the deposit is due?"),
    ("Do you happen to know where the spare key is?", "where the spare key is?"),
    ("I am curious about the launch date", "the launch date"),
    ("I'm just wondering if the hotel is booked", "if the hotel is booked"),
    ("I was hoping you could tell me when the flight leaves", "when the flight leaves"),
    ("I would like to know who is on the beta", "who is on the beta"),
    ("I'd love to see what I wrote about Lisbon", "what I wrote about Lisbon"),
    ("Out of curiosity, how many testers are active?", "how many testers are active?"),
    ("Just to confirm, is the deposit paid?", "is the deposit paid?"),
    ("For the record, when is the launch?", "when is the launch?"),
    ("May I ask when the dentist is?", "when the dentist is?"),
    ("Can I check if the visa is booked", "if the visa is booked"),
    ("Is it possible to find out when the boiler service is?", "when the boiler service is?"),
    ("I need to confirm when the rent is due", "when the rent is due"),
    ("Kindly tell me where the passport is", "where the passport is"),
    ("Could you look up the dentist date", "the dentist date"),
    ("Did I ever note anything about the garden shed?", "the garden shed?"),
    ("Oh and when is the dentist?", "when is the dentist?"),
    ("Finally, who is on the beta?", "who is on the beta?"),
    ("Sorry, but when is the launch?", "when is the launch?"),
    ("Erm, when is the launch?", "when is the launch?"),
    ("Well, when is the launch?", "when is the launch?"),
    ("Good morning, when is the dentist?", "when is the dentist?"),
    ("In my notes, when is the dentist?", "when is the dentist?"),
    ("Dear assistant, when is the dentist?", "when is the dentist?"),
    ("When is the dentist, if you can?", "When is the dentist?"),
    ("When is the dentist when you get a chance?", "When is the dentist?"),
    ("When is the dentist, thanks in advance", "When is the dentist"),
    ("When is the dentist at your convenience?", "When is the dentist?"),
    ("When is the dentist, no rush?", "When is the dentist?"),
    ("When is the dentist, kindly?", "When is the dentist?"),
    ("whatd I say about Lisbon", "what I say about Lisbon"),
    ("where'd I put the spare key", "where did I put the spare key"),
    ("how'd the launch go", "how did the launch go"),
    ("what'll the trip cost", "what will the trip cost"),
    ("whaddya know about the beta", "what do you know about the beta"),
]


@pytest.mark.parametrize(("question", "read"), _WRAPPER_CASES)
def test_a_wrapped_or_formal_question_is_read_as_the_question_inside_it(question, read):
    assert composer.rephrase(question) == read


@pytest.mark.parametrize("question", ["Who is my best friend?", "Next dentist appointment?", "Well water pressure at the cabin"])
def test_a_wrapper_never_takes_a_word_of_the_subject(question):
    assert composer.rephrase(question) == question


@pytest.mark.parametrize(
    ("question", "shape"),
    [
        ("Would you mind telling me when the dentist is?", "when"),
        ("Could you kindly advise how many testers are active?", "count"),
        ("Out of curiosity, who is on the beta?", "who"),
        ("I'm curious why the list felt slow", "explain"),
    ],
)
def test_a_formal_wrapper_does_not_change_the_shape(question, shape):
    assert composer.classify(question) == shape


# --- lead-ins ---------------------------------------------------------------------------


@pytest.mark.parametrize("lead", sorted(composer_tables.EXTRA_LEAD_INS))
def test_a_new_lead_in_is_taken_off_a_sentence_with_its_comma(lead):
    note = _note(1, f"# Hills\n\n{lead.capitalize()}, the hills are steep here.", 2)
    view = composer.read_note(note, 0)
    assert view.sentences[0].text == "the hills are steep here." or view.sentences[0].text == "The hills are steep here.", view.sentences[0].text


@pytest.mark.parametrize("lead", sorted(composer.LEAD_INS_BARE))
def test_a_bare_lead_in_is_taken_off_before_a_lowercase_word(lead):
    note = _note(1, f"# Hills\n\n{lead.capitalize()} the hills are steep here.", 2)
    assert composer.read_note(note, 0).sentences[0].text.endswith("hills are steep here.")
    assert not composer.read_note(note, 0).sentences[0].text.lower().startswith(lead)


# --- small talk in two voices ------------------------------------------------------------


def test_the_professional_voice_has_every_kind_the_natural_one_has():
    assert set(composer.SOCIAL_PROFESSIONAL) == set(composer.SOCIAL)
    assert all(len(lines) >= 2 for lines in composer.SOCIAL_PROFESSIONAL.values())


@pytest.mark.parametrize("line", [line for lines in composer_tables.SOCIAL_PROFESSIONAL.values() for line in lines])
def test_every_professional_social_line_follows_the_copy_rules(line):
    assert EM_DASH not in line and "!" not in line and "Oops" not in line
    assert line[0].isupper() and "isn't running" not in line


@pytest.mark.parametrize("line", [line for lines in composer_tables.SOCIAL_NATURAL_EXTRA.values() for line in lines])
def test_every_added_natural_social_line_follows_the_copy_rules(line):
    assert EM_DASH not in line and "!" not in line and "Oops" not in line
    assert line[0].isupper() and line in [x for lines in composer.SOCIAL.values() for x in lines]


@pytest.mark.parametrize(
    ("message", "kind"),
    [("hi", "greeting"), ("good morning", "morning"), ("thanks", "thanks"), ("how are you", "how"), ("bye", "bye"), ("sorry", "sorry"),
     ("lol", "laugh"), ("wow", "reaction"), ("what", "confused"), ("ok", "ack"), ("who are you", "who")],
)
def test_a_professional_reply_is_of_the_turns_kind(message, kind):
    assert composer.social(message, voice="professional") in composer.social_surfaces(kind, True)
    assert composer.social(message) in composer.social_surfaces(kind)


def test_the_professional_reply_is_never_the_one_before_and_offers_a_professional_next_step():
    first = composer.social("ok", voice="professional")
    assert composer.social("ok", previous=first, voice="professional") != first
    reply = composer.social("thanks", last_question="When is the sync rewrite?", voice="professional")
    assert any(step.split("{subject}")[0] in reply for step in composer.NEXT_STEPS_PROFESSIONAL)


@pytest.mark.parametrize("step", composer_tables.NEXT_STEPS_EXTRA + composer_tables.NEXT_STEPS_PROFESSIONAL)
def test_every_next_step_follows_the_copy_rules_and_has_its_slot(step):
    assert "{subject}" in step and EM_DASH not in step and "!" not in step and step[0].isupper()


# --- the setting ---------------------------------------------------------------------------


def test_the_voice_is_a_preference_that_defaults_to_natural_and_refuses_other_values(client):
    def voice() -> str:
        prefs = client.get("/preferences").json()
        return prefs["composer_voice"]

    def put(value: str) -> int:
        response = client.put("/preferences", json={"composer_voice": value})
        return response.status_code

    assert voice() == "natural"
    assert put("professional") == 200
    assert voice() == "professional"
    assert put("shouty") == 422
    assert put("natural") == 200
    assert voice() == "natural"


def test_chat_with_no_model_follows_the_voice_preference(client):
    from tests.test_composer_route_688 import _ask

    client.put("/preferences", json={"composer_voice": "professional"})
    out = _ask(client, "thanks", use_tools=False)
    assert out["text"] in composer.SOCIAL_PROFESSIONAL["thanks"]
    client.put("/preferences", json={"composer_voice": "natural"})
    out = _ask(client, "thanks", use_tools=False)
    assert out["text"] in composer.SOCIAL["thanks"]


def test_a_composed_chat_answer_follows_the_voice_preference(ai_client, session):
    from tests.test_composer_route_688 import _ask, _seed

    _seed(session)
    ai_client.put("/preferences", json={"composer_voice": "professional"})
    natural_only = {
        composer.PHRASES[k] for keys in composer_tables.VOICE_VARIANTS["natural"].values() for k in keys
    } - {composer.PHRASES[k] for keys in composer_tables.VOICE_VARIANTS["professional"].values() for k in keys}
    for question in ("What is the Harbor launch plan?", "When is the dentist check-up?", "What about the Harbor launch?"):
        out = _ask(ai_client, question, notes_only=True, use_tools=False, answer_from="notes")
        assert out["meta"][0]["composed"] is True
        assert not any(phrase in out["text"] for phrase in natural_only if phrase.strip(" :,."))
