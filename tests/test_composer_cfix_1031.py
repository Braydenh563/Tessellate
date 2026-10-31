"""The composer audit of 2026-10-31 (docs/roadmap/agent-remaining/audit-1031-composer.md),
one class per test group, each over many phrasings. Notebook and fixed clock:
`tests/_seed_1031c.py` (Saturday 31 October 2026, 11:30)."""

from __future__ import annotations

import pytest

import tests._seed_1031c as seed_c


@pytest.fixture
def notebook(client, session, monkeypatch):
    seed_c.seed(session)
    return seed_c.asker(client, monkeypatch)


@pytest.fixture
def big_notebook(client, session, monkeypatch):
    seed_c.seed(session, filler=150)
    return seed_c.asker(client, monkeypatch)


# C1. A note titled with the name is a member of "who is X", whatever its body says.

@pytest.mark.parametrize("question", [
    "who is Tom", "who's Tom", "tell me about Tom", "what do I know about Tom", "what have I written about Tom",
    "what do my notes say about Tom", "who is tom?", "WHO IS TOM",
])
def test_the_note_titled_with_the_name_is_said_for_a_who_ask(notebook, question):
    said, _ = notebook(question)
    assert "data team at Vireo" in said, said
    assert "three notes" in said, said


@pytest.mark.parametrize("question", ["where does Tom work", "what does Tom do", "what does Tom do for work", "where does Tom work again"])
def test_a_pronoun_line_in_the_note_titled_with_the_name_answers_a_slot(notebook, question):
    said, _ = notebook(question)
    assert "data team at Vireo" in said, said


# C2. A list item is not a newer value of a relation.

@pytest.mark.parametrize("question", [
    "who is Sara", "what have I written about Sara", "what is in the Sara note", "what does Sara want for her birthday",
    "what should I get Sara", "tell me about Sara", "when is Sara's birthday",
])
def test_a_gift_list_does_not_replace_the_sara_note(notebook, question):
    said, _ = notebook(question)
    assert "used to be" not in said and "my sister" not in said, said
    assert "an older note" not in said.lower() and "earlier, on" not in said.lower(), said


def test_a_real_replacement_is_still_reported_in_the_second_person():
    from tessellate.ai import supersede

    notes = [
        {"content": "Uni days this semester: Tuesday and Thursday", "created_at": "2026-02-20T10:00:00"},
        {"content": "Uni days this semester are Monday and Wednesday", "created_at": "2026-07-20T10:00:00"},
    ]
    kept, replaced = supersede.current("what are my uni days", notes)
    assert len(kept) == 1 and replaced
    first_person = [{"content": "My favourite colour is blue", "created_at": "2026-01-01"}, {"content": "My favourite colour is now green", "created_at": "2026-06-01"}]
    kept, replaced = supersede.current("what is my favourite colour", first_person)
    assert len(kept) == 1
    assert "your" not in supersede.older_line(replaced) or "my" not in supersede.older_line(replaced)


@pytest.mark.parametrize("old, new", [("Sara is my sister", "Sara: a jazz record"), ("Tom is my brother", "Tom: coffee beans"), ("Sara is my sister", "Sara is a runner")])
def test_a_relation_is_never_a_stale_value(old, new):
    from tessellate.ai import supersede

    notes = [{"content": old, "created_at": "2026-01-01"}, {"content": new, "created_at": "2026-06-01"}]
    kept, replaced = supersede.current("who is " + old.split()[0], notes)
    assert len(kept) == 2 and not replaced


# C3. A holiday or month word in a topic question is searched for, not read as a day of writing.

@pytest.mark.parametrize("question", [
    "what do I know about Christmas", "tell me about Christmas", "anything about Christmas", "what have I written about Christmas",
    "what do I know about christmas", "who is coming for Christmas", "who's coming for Christmas", "what do my notes say about Christmas",
])
def test_a_holiday_in_a_topic_question_finds_the_notes_that_hold_it(notebook, question):
    said, _ = notebook(question)
    assert "coming for Christmas" in said, said
    assert "Nothing went" not in said and "can't find" not in said and "couldn't find" not in said, said


@pytest.mark.parametrize("question", ["how much did I save in October", "how much have I saved in October", "how much did I save in October?"])
def test_a_verb_and_a_month_read_the_months_notes_that_hold_the_verb(big_notebook, question):
    said, _ = big_notebook(question)
    assert "$500" in said and "can't find" not in said, said


@pytest.mark.parametrize("phrase, said", [
    ("Christmas", "at Christmas"), ("christmas", "at Christmas"), ("Easter", "at Easter"), ("the weekend", "over the weekend"),
    ("in October", "in October"), ("last week", "last week"), ("20 October", "on 20 October"), ("Halloween", "on Halloween"),
])
def test_a_time_phrase_carries_its_preposition(phrase, said):
    from tessellate.ai import composer

    assert composer.window_said(phrase) == said


@pytest.mark.parametrize("question, kept", [
    ("what did I write in October", True), ("what did I write last week", True), ("what did I do at Christmas", True),
    ("what do I know about last week", True), ("what do I know about Christmas", False), ("who is coming for Christmas", False),
    ("what do I know about the weekend", False), ("what do I know about October", False),
])
def test_only_a_writing_question_keeps_the_window(question, kept):
    from datetime import date

    from tessellate.ai import composer

    assert bool(composer.plan(question, date(2026, 10, 31)).window) is kept


def test_the_search_does_not_read_a_topic_holiday_as_a_range():
    from datetime import date

    from tessellate.search import query

    for question in ("who is coming for Christmas", "what do I know about Christmas", "tell me about Easter"):
        understood = query.understand(question, date(2026, 10, 31))
        assert not understood.has_range and understood.subject, question
    assert query.understand("what did I do at Christmas", date(2026, 10, 31)).has_range


# C12. A follow-on keeps its subject: a pronoun, a person, a total, "the last one".

@pytest.mark.parametrize("question, previous, said", [
    ("how much does it cost", "tell me about the Lisbon trip", "how much does the Lisbon trip cost"),
    ("when is it", "tell me about the Lisbon trip", "when is Lisbon trip"),
    ("what should I get her", "who is Sara", "what should I get Sara"),
    ("when is her birthday", "who is Sara", "when is Sara's birthday"),
    ("what else do I know about her", "who is Sara", "what else do I know about Sara"),
    ("where does she live", "who is Sara", "where does Sara live"),
    ("what does he do", "who is Tom", "what does Tom do"),
    ("how far in total", "what do I know about running", "how far in total for running?"),
    ("what's the total", "what do I know about running", "what's the total for running?"),
    ("when was the last one", "what do I know about running", "when was the last one for running?"),
])
def test_a_follow_on_names_what_it_leans_on(question, previous, said):
    from tessellate.ai import composer

    got = composer.follow_on(question, [{"question": previous, "answer": "x"}])
    assert got is not None and got.question == said, got


@pytest.mark.parametrize("question", [
    "how far did I run in total", "when was the last one with Tom", "what time", "what is the weather", "who is Sara",
])
def test_a_question_with_its_own_subject_stands_alone(question):
    from tessellate.ai import composer

    got = composer.follow_on(question, [{"question": "what do I know about running", "answer": "x"}])
    assert got is None or got.kind != "pronoun", got


# C9. A day a preposition of aim leads is where something is headed, not the day it happened.

@pytest.mark.parametrize("question", ["when did I call mum", "when did I last call mum", "when did I phone mum"])
def test_a_day_the_sentence_aims_at_is_not_the_day_of_the_event(notebook, question):
    said, _ = notebook(question)
    assert "26 October" in said and "2025" not in said and "25 December" not in said, said
    assert "coming for Christmas" in said, said


# C10 and C11. A note open is answered from that note: a line in a script with no spaces is a
# sentence, not a title, and no question about "this" is a search or the world.

@pytest.fixture
def opened(client, session, monkeypatch):
    ids = seed_c.seed(session)
    go = seed_c.asker(client, monkeypatch)
    return lambda key, question: go(question, open_id=ids[key])[0]


@pytest.mark.parametrize("question", [
    "what is this note about", "summarise this", "tell me more", "what is this", "what's in here", "explain this", "tl;dr",
])
def test_a_japanese_note_open_is_quoted_not_called_a_title(opened, question):
    said = opened("jp1", question)
    assert "今日は雨が降っていたので" in said, said
    assert "only a title" not in said and "general knowledge" not in said and "。." not in said, said


@pytest.mark.parametrize("question", [
    "what dates are in this", "which dates does it mention", "any dates in here", "are there any dates in this", "what dates are mentioned",
])
def test_a_dates_question_with_a_note_open_reads_that_note(opened, question):
    assert "4 November 2026" in opened("dentist", question)
    assert "does not give a date" in opened("jp1", question)
    assert "parser" not in opened("dentist", question) and "pickup" not in opened("dentist", question)


@pytest.mark.parametrize("question", ["what is this", "what is this note about", "tell me more", "summarise this"])
def test_a_title_only_note_open_says_so_never_the_world(opened, question):
    said = opened("weekend", question)
    assert "only a title" in said and "general knowledge" not in said, said


def test_a_sentence_ends_at_a_full_width_stop():
    from tessellate.ai import composer

    view = composer.read_note({"id": 1, "content": "今日は雨が降っていたので、家で読書をした。村上春樹の新しい本を読み始めた。", "created_at": "2026-10-22T20:00:00"}, 0)
    assert [s.text for s in view.sentences] == ["今日は雨が降っていたので、家で読書をした。", "村上春樹の新しい本を読み始めた。"]


# C8. One stem for a word and its plural; a plural noun leads with the notes that say it as typed.

@pytest.mark.parametrize("plural, singular", [
    ("meetings", "meeting"), ("bookings", "booking"), ("buildings", "building"), ("paintings", "painting"),
    ("books", "book"), ("notes", "note"), ("recipes", "recipe"), ("trips", "trip"),
])
def test_a_plural_and_its_word_share_a_stem(plural, singular):
    from tessellate.ai import composer

    assert composer._stem(plural) == composer._stem(singular)


@pytest.mark.parametrize("question", [
    "what have I written about meetings", "what do I know about meetings", "tell me about meetings", "any meetings", "meetings",
])
def test_a_plural_subject_is_not_called_missing(notebook, question):
    said, _ = notebook(question)
    assert "None of your notes mention" not in said and "Do you remember roughly" not in said, said
    assert "meeting" in said.lower(), said


@pytest.mark.parametrize("question", ["what do I know about books", "tell me about books", "what have I written about books"])
def test_a_plural_noun_leads_with_the_notes_that_say_it(notebook, question):
    said, _ = notebook(question)
    assert said.index("Piranesi") < (said.index("Lisbon") if "Lisbon" in said else 10**6), said
    assert "lisbon notes go together" not in said, said


# C7. A question that names a note by its title is answered from that note.

@pytest.mark.parametrize("question, expect", [
    ("what is Tom's note about", "data team at Vireo"), ("what does the Tom note say", "data team at Vireo"),
    ("what is in the Tom note", "data team at Vireo"), ("tell me about the Tom note", "data team at Vireo"),
    ("what is in the note called Tom", "data team at Vireo"), ("summarise the Tom note", "conference in June"),
    ("what is in the Sara note", "your sister"), ("what does the Sara note say", "your sister"),
    ("what is Sara's note about", "your sister"), ("read the Sara note", "your sister"), ("explain the note titled Sara", "your sister"),
])
def test_a_titled_note_is_read_when_it_is_named(notebook, question, expect):
    said, _ = notebook(question)
    assert expect in said and "Gift ideas" not in said and "called" not in said, said


@pytest.mark.parametrize("question", ["what is in the shopping note", "what is in the xyzzy note"])
def test_a_note_name_no_title_holds_falls_to_the_search(notebook, question):
    said, _ = notebook(question)
    assert "Gift ideas" not in said or "shopping" in said or "xyzzy" in said, said


# C13. The weather does not take "you"; a date-only heading line is the note's day, not a fact.

@pytest.mark.parametrize("line, said", [
    ("Rained all day, baked banana bread and watched Arrival.", "it rained all day, and you baked banana bread and watched Arrival."),
    ("Snowed all morning.", "it snowed all morning."),
])
def test_a_weather_verb_takes_it_not_you(line, said):
    from tessellate.ai import composer_digest

    assert composer_digest._second_person(line) == said


@pytest.mark.parametrize("question", [
    "what do I know about Arrival", "tell me about my diary", "what did I write about October", "what did I do on 24 October",
    "what did I do last Saturday",
])
def test_no_answer_says_you_rained_or_a_day_has_itself(notebook, question):
    said, _ = notebook(question)
    assert "you rained" not in said and "24 October has" not in said and "has Saturday 24 October" not in said, said


# C14. A group's line names the notes that carry the tag, and says how the others are in it.

def test_a_shared_tag_is_said_of_its_holders_only():
    from tessellate.ai import composer_frame

    notes = [
        {"id": 1, "content": "Meeting\n\nWeekly sync.", "tags": ["meeting"], "category": "Work"},
        {"id": 2, "content": "Meeting with Priya\n\nAtlas scope.", "tags": ["meeting", "atlas"], "category": "Work"},
        {"id": 3, "content": "Project Atlas\n\nShip in November.", "tags": ["atlas", "work"], "category": "Work"},
    ]
    group = composer_frame.Group([1, 2, 3], "meeting", "share #meeting", 1.0, "also", links=[(2, 3)])
    line = composer_frame.group_line(group, notes, "work")
    assert line.index("Meeting and") < line.index("Project Atlas"), line
    assert "share #meeting: " in line and "Project Atlas is linked to them" in line, line
    assert "share #meeting: Meeting, Project Atlas" not in line, line


def test_a_tag_all_carry_is_said_of_all():
    from tessellate.ai import composer_frame

    notes = [{"id": i, "content": f"Note {i}\n\nbody", "tags": ["gym"], "category": "Health"} for i in (1, 2, 3)]
    line = composer_frame.group_line(composer_frame.Group([1, 2, 3], "gym", "all tagged #gym", 1.0, "also"), notes, "gym")
    assert "linked to" not in line and "all tagged #gym" in line, line


# C15. A count of a doing counts every dated line, and a count line is that many doings.

@pytest.mark.parametrize("question", [
    "how many times did I run", "how often do I run", "how many times have I run", "how often did I run",
])
def test_a_doing_is_counted_over_every_note(notebook, question):
    said, _ = notebook(question)
    for day in ("3 October", "17 October", "25 October", "30 October"):
        assert day in said, said
    assert "five times" in said and "18 July" not in said, said


@pytest.mark.parametrize("question", ["how long since I last ran", "how long since I ran", "how long has it been since I ran"])
def test_the_last_run_is_the_last_dated_one(notebook, question):
    said, _ = notebook(question)
    assert "25 October" in said and "yesterday" not in said, said


def test_a_count_in_one_line_is_that_many_doings():
    from datetime import date

    from tessellate.ai import composer, composer_doings

    note = {"id": 1, "content": "# Weekly review\n\nRan twice, prepared the Atlas beta and booked nothing.", "created_at": "2026-10-30T20:00:00"}
    view = composer.read_note(note, 0)
    _lemma, _past, forms = composer_doings._forms("run")
    done = composer_doings.doings([view], forms, [], date(2026, 10, 31))
    assert [(d.day, d.times) for d in done] == [(date(2026, 10, 30), 2)]


# C16. The lead is the sentence that holds the asked slot: the doing for "when did I", the length for "how long".

@pytest.mark.parametrize("question", [
    "when did I bake banana bread", "when did I last bake banana bread", "when was it I baked banana bread",
])
def test_when_did_i_leads_with_the_sentence_that_says_the_doing(notebook, question):
    said, _ = notebook(question)
    assert "24 October" in said and "you baked banana bread" in said and "3 ripe bananas" not in said, said


@pytest.mark.parametrize("question", ["how long do I bake banana bread", "how long should I bake banana bread", "how long does banana bread bake"])
def test_how_long_leads_with_the_length(notebook, question):
    said, _ = notebook(question)
    assert said.lstrip().startswith("Bake at 175C for 55 minutes"), said


@pytest.mark.parametrize("word, stem", [("baked", "bake"), ("liked", "like"), ("named", "name"), ("hoped", "hope"), ("hated", "hate")])
def test_a_short_past_form_folds_to_its_verb(word, stem):
    from tessellate.ai import composer

    assert composer._stem(word) == composer._stem(stem)


@pytest.mark.parametrize("word", ["ahead", "bread", "need", "shed", "used", "tied"])
def test_a_word_that_only_ends_in_ed_is_left_whole(word):
    from tessellate.ai import composer

    assert composer._stem(word) == word


# C17 and C47. "Short version", "gist" and "tl;dr" are summarise asks; the chips under an answer are questions it answers.

@pytest.mark.parametrize("question", [
    "give me the short version of Project Atlas", "the gist of Project Atlas", "tl;dr Project Atlas", "Project Atlas in a sentence",
    "summarise Project Atlas", "the short version of Project Atlas",
])
def test_a_summary_ask_does_not_make_its_own_word_a_term(notebook, question):
    said, _ = notebook(question)
    assert "Beta on 10 November" in said, said
    for refusal in ("reference to", "do not mention", "do not talk about", "None of these"):
        assert refusal not in said, said


def _chips(events):
    return next(e for e in events if e["type"] == "grounding").get("next", [])


@pytest.mark.parametrize("question", [
    "what do I know about sourdough", "what do I know about Lisbon", "what do I know about running", "tell me about Tom",
    "what do I know about books", "what do I know about the dentist",
])
def test_every_chip_offered_is_answered(notebook, question):
    _said, events = notebook(question)
    chips = _chips(events)
    assert chips, question
    for chip in chips:
        if chip.startswith("Open "):
            continue
        said, _ = notebook(chip)
        for refusal in ("reference to", "None of these", "do not mention", "I looked, but nothing", "has anything left to tick", "“else”"):
            assert refusal not in said, (question, chip, said)


@pytest.mark.parametrize("question", ["what do I know about sourdough", "what do I know about Lisbon", "tell me about Tom"])
def test_what_is_left_is_offered_only_for_a_note_with_a_list(notebook, question):
    _said, events = notebook(question)
    left = [c for c in _chips(events) if c.startswith("What is left in")]
    assert not left or "packing" in left[0].lower(), left


def test_a_name_in_a_chip_keeps_its_capital(notebook):
    _said, events = notebook("tell me about Tom")
    assert not [c for c in _chips(events) if " tom" in c], _chips(events)


# C6. One count: the pattern line counts the notes the opening counts.

@pytest.mark.parametrize("question", [
    "what have I written about uni", "what do I know about uni", "tell me about uni", "what do I know about cloud",
    "what have I written about university", "anything about uni",
])
def test_the_opening_count_and_the_times_line_agree(notebook, question):
    import re

    said, _ = notebook(question)
    words = {"one": 1, "two": 2, "three": 3, "four": 4, "five": 5, "six": 6, "seven": 7, "eight": 8, "nine": 9, "ten": 10}
    opening = re.search(r"\b(?:have|are|is|there are)?\s*(one|two|three|four|five|six|seven|eight|nine|ten) notes? about", said, re.I)
    times = re.search(r"written about \w+ (\d+) times", said)
    if opening and times:
        assert words[opening.group(1).lower()] == int(times.group(1)), said


# INBOX 1495. A Japanese line is never "1 word"; a long line is named by a short form; the head's dot.

@pytest.mark.parametrize(("text", "words"), [
    ("", 0), ("hello", 1), ("two words", 2), ("今日は雨", 4), ("考え：仕事を済ませてから、練習", 15),
    ("buy 牛乳 and 卵", 5), ("  spaced   out  ", 2), ("カタカナ", 4), ("한국어 단어", 2),
])
def test_a_word_count_counts_cjk_by_character(text, words):
    from tessellate.ai import utilities

    assert utilities.word_count(text) == words
    assert utilities.counts(text)["words"] == words


@pytest.mark.parametrize("line", [
    "考え：仕事を済ませてから、練習としてゴルフを数球打った（笑）",
    "今日は雨が降っていたので傘を持って出かけました、そして駅まで歩いた",
    "メモ：明日の会議の資料を準備する必要がある、忘れないように",
])
def test_a_long_line_with_no_spaces_is_named_by_a_short_form(line):
    from tessellate.ai import realise

    short = realise.cut_title(line, 60)
    assert short.endswith("…") and 4 <= len(short) <= 21, short
    assert line.startswith(short.removesuffix("…"))


def test_a_short_title_is_kept_whole():
    from tessellate.ai import realise

    assert realise.cut_title("Atlas retro meeting", 60) == "Atlas retro meeting"
    assert realise.cut_title("買い物リスト", 60) == "買い物リスト"


def test_the_greeting_names_a_japanese_note_by_a_short_form(client, session, monkeypatch):
    from tessellate.core.database import Entry

    session.add(Entry(content="考え：仕事を済ませてから、練習としてゴルフを数球打った（笑）", created_at=seed_c.NOW))
    session.commit()
    said = seed_c.asker(client, monkeypatch)("hey")[0]
    assert "考え：仕事を済ませてから…" in said and "ゴルフ" not in said, said


def test_no_surface_counts_words_by_its_own_split():
    import re

    from tests._app_js import app_js_text

    text = app_js_text()
    own = re.findall(r"[^\n]*(?:\.match\(/\\S\+/g\)|split\(/\\s\+/\))[^\n]*\.length[^\n]*word[^\n]*", text, re.I)
    assert not own, own[:3]


def test_the_head_dot_is_drawn_between_shown_chips_only():
    from pathlib import Path

    css = Path("frontend/css/04-chat-dock-appearance.css").read_text(encoding="utf-8")
    assert ".chat-subline > :not([hidden]) ~ :not([hidden])::before" in css
    assert ".chat-subline > *+*::before" not in css


# INBOX 1496. A vague pick is a pick; a caption is said once; no filler as a subject.

@pytest.mark.parametrize("question", [
    "errm a random ahh note", "a random note", "gimme a random ahh note lol", "give me any note", "pick a note for me",
    "any note will do", "some random old note", "open a random note", "can you pick a random note for me", "random note please",
])
def test_a_vague_pick_is_answered_as_one_of_your_notes(notebook, question):
    said, _ = notebook(question)
    assert said.startswith("Here is one of your"), said
    assert "nothing in your notes" not in said.lower()


@pytest.mark.parametrize("question", [
    "delete a random note", "a random note about cooking", "random thoughts about notes", "what is a random variable note",
    "tell me a random fact", "give me a note about Lisbon",
])
def test_a_pick_with_a_subject_or_an_act_is_no_pick(question):
    from tessellate.ai import slash

    assert slash.infer(question) is None, question


@pytest.mark.parametrize("caption", [
    "a photo of a grassy hill with blue arrows", "The image shows a photo of a grassy hill with blue arrows",
    "this picture of a grassy hill with blue arrows", "A photograph of a grassy hill with blue arrows",
    "a screenshot of a grassy hill with blue arrows",
])
def test_a_caption_that_names_its_kind_is_said_once(caption):
    import re
    from datetime import date

    from tessellate.ai import composer

    note = {"id": 1, "created_at": "2026-10-20T10:00:00", "tags": [], "content": (
        "Random ahh sketch\n\n![hill.png](/media/hill.png)\n\n"
        f'[Pictures in this note, as this app read them:\n- hill.png: shows {caption}; text in it: "CRAZZYYYY 67"]')}
    text = composer.compose("what is in my random ahh sketch note", [note], today=date(2026, 10, 31))["text"]
    assert not re.search(r"\b(picture|photo|image|screenshot)\b of an? (picture|photo|image|screenshot)\b", text, re.I), text
    assert "grassy hill" in text, text


def test_a_source_card_says_its_title_once_and_no_bare_kind_word():
    from tests._app_js import app_js_text

    text = app_js_text()
    assert "function sourceLines(content)" in text and "const lines = sourceLines(entry.content);" in text
    foot = text[text.index('foot.className = "chat-source-foot muted"') - 120 : text.index('foot.className = "chat-source-foot muted"') + 200]
    assert "if (source.url)" in foot and "group?.one" not in foot


# C48. "What's new with X", "news on X" and "where am I with X" are the latest-on-X ask.

@pytest.mark.parametrize("question, subject", [
    ("what's new with uni", "uni"), ("whats new with uni", "uni"), ("what is new with the Lisbon trip", "lisbon trip"),
    ("any news on Lisbon", "lisbon"), ("news about running", "running"), ("where am I with uni", "uni"),
    ("where am I at with my taxes", "taxes"), ("what's the latest on Lisbon", "lisbon"), ("what is the newest on uni", "uni"),
])
def test_a_news_ask_reads_its_subject_as_a_latest_ask_does(question, subject):
    from tessellate.ai import note_recency

    assert note_recency.status_subject(question) == subject


@pytest.mark.parametrize("question", ["what's new", "what is new with it", "I have a new note about cats", "what is new today", "where am I", "what's the latest"])
def test_no_news_subject_is_read_where_none_is_named(question):
    from tessellate.ai import note_recency

    assert note_recency.status_subject(question) == ""


@pytest.mark.parametrize("question", ["what's the latest on Lisbon", "what is new with the Lisbon trip", "any news on Lisbon", "where am I with Lisbon"])
def test_a_status_ask_never_leads_with_a_bare_checklist_item(notebook, question):
    said, _ = notebook(question)
    assert not said.lstrip().startswith(("Passport", "Charger", "Sunscreen")), said


@pytest.mark.parametrize("question", ["what's new with uni", "any news on uni", "where am I with uni"])
def test_a_news_ask_on_uni_leads_with_the_newest_uni_note(notebook, question):
    said, _ = notebook(question)
    assert "Back in July" not in said, said


# C19. "Notes mentioning X" asked as a question is the same listing in Ask and in Chat.

@pytest.mark.parametrize("question", [
    "what do my notes mentioning Lisbon say", "What do My notes mentioning lisbon saY??", "which notes mention Lisbon",
    "what do my notes containing Lisbon say", "which of my notes mention Lisbon", "what notes mention Lisbon",
])
def test_a_word_notes_question_lists_the_same_notes_in_ask_and_in_chat(client, session, monkeypatch, question):
    seed_c.seed(session)
    ask_said, _ = seed_c.asker(client, monkeypatch)(question)
    chat_said, _ = seed_c.asker(client, monkeypatch, chat=True)(question)
    assert ask_said.count("](#/notes/") >= 2, ask_said
    assert ask_said.count("](#/notes/") == chat_said.count("](#/notes/")


@pytest.mark.parametrize("question", ["what is due for uni", "what exams do I have", "what tests do I have coming up", "what is due this week"])
def test_a_due_ask_is_still_a_due_ask(question):
    from tessellate.ai import composer_lists

    assert composer_lists.computed_kind(question) in {"due_for", "dates"}, question


# C26. "Which is the main note" is the defining note of the subject, never "your newest notes".

_UNI = [{"question": "what do I know about uni", "answer": "x"}]


@pytest.mark.parametrize("question", [
    "which is the main note", "which one is the defining note", "which note is the best one", "what's the key note", "whats my main note",
    "which is the central note?", "and which is the principal note", "which is the top note",
])
def test_a_defining_note_ask_leans_on_the_subject_before_it(question):
    from tessellate.ai import composer

    follow = composer.follow_on(question, _UNI)
    assert follow is not None and follow.question == "what do I know about university", (question, follow)


@pytest.mark.parametrize("question, subject", [
    ("which is the main note on uni", "university"), ("which note is the key one for sourdough", "sourdough"), ("what's the best note about Lisbon", "Lisbon"),
])
def test_a_defining_note_ask_names_its_own_subject(question, subject):
    from tessellate.ai import composer

    follow = composer.follow_on(question, None)
    assert follow is not None and follow.question.endswith(subject) or subject == "university" and follow.question.endswith("uni"), (question, follow)


@pytest.mark.parametrize("question", ["what is the main idea of my notes", "which is the best note ever written", "which is the main character", "the main note"])
def test_other_main_questions_are_not_a_defining_ask(question):
    from tessellate.ai import composer

    assert composer.follow_on(question, _UNI) is None, question


def test_a_defining_note_ask_after_the_uni_overview_never_lists_the_newest_notes(notebook):
    first, _ = notebook("what do I know about uni")
    said, _ = notebook("which is the main note", history=[{"question": "what do I know about uni", "answer": first}])
    assert "five newest" not in said and "couldn't find" not in said, said


# C18. "What am I reading" is the Books note, not a question another note asks.

@pytest.mark.parametrize("question", [
    "what am I reading", "What am I reading?", "what am I reading right now", "what am I reading at the moment",
    "what am I currently reading",
])
def test_what_am_i_reading_is_the_books_note(notebook, question):
    said, _ = notebook(question)
    assert "Books note" in said and "Ice Breakers" not in said, said


@pytest.mark.parametrize("question", ["what is reading", "what am I reading about", "what was I reading in September", "what am I rereading"])
def test_media_kind_leaves_other_questions_as_they_are(question):
    from tessellate.ai import question_noise

    assert question_noise.media_kind(question) == question
