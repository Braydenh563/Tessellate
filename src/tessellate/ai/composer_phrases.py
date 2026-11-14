"""The composed answer's connective tissue: `PHRASES`, the closed list of
joining words that say nothing about the world, and `phrase_options`.

Moved whole from `composer.py` (audit AR3, gods-1101): the code is unchanged,
and `composer` re-exports every name here that anything reads, so
`composer.PHRASES` still works. Imports run one way, down
the layer list in `composer.py`'s docstring, never back to `composer`.
"""

from __future__ import annotations

from tessellate.ai import composer_ack, composer_open, composer_tables, composer_versus


#: The fixed connective phrases: the only words this module writes. Named so
#: the composition reads as a sequence of decisions, and closed so the
#: traceability test can hold every template part of every answer to it.
PHRASES: dict[str, str] = {
    # Layout and punctuation.
    "para": "\n\n",
    "line": "\n",
    "bullet": "- ",
    "indent": "  ",
    "task_done": "- [x] ",
    "task_open": "- [ ] ",
    "bold": "**",
    "space": " ",
    "colon": ": ",
    "comma": ", ",
    "stop": ".",
    "open_quote": "“",
    "close_quote": "”",
    "open_paren": " (",
    "close_paren": ")",
    #: A note the timeline files under the day its text names, not the day it was written (INBOX 1739).
    "written_a": " (written ",
    "written_top": "Written ",
    "about_a": ", about ",
    #: The note an answer rests on, said once in a chat (decision D25: no bracketed title): "From your Gym log note."
    "cite_from": " From your ",
    "cite_note": " note.",
    "cite_from_note": " From your note ",
    #: "2 + 2 is 4." (`_sum`): the sum as asked, then its value.
    "sum_is": " is ",
    "and": " and ",
    "or": " or ",
    # The opening (INBOX 741, the owner: "rn the ask chat messages just say,
    # ur note starting with this says this. also ur not starting with this
    # says this, furthermore, ur note starting with this says this"). The
    # answer is the note's own sentence, said first; the note is named once,
    # after it, as the citation ("[**Harbor launch plan**]"), never by its
    # first words and never as "Your note ... says:". An opener is optional
    # and varied by the question, so two answers in a row do not start alike.
    "open_notes": "From your notes: ",
    "open_wrote": "Here is what you wrote: ",
    "open_put": "Your notes put it this way: ",
    "open_figure": "The number you noted: ",
    "open_date": "The date you noted: ",
    "wrote_on_a": "On ",
    "wrote_on_b": " you wrote: ",
    "closest_a": "The closest your notes come is this: ",
    "closest_b": "Nothing here says it outright. The nearest is: ",
    "going_by": "Going by your notes",
    "not_that": "Not that I can see, but a note says: ",
    "only_plan": "Only as a plan: ",
    # A question that could mean two notes: answered by the likelier, then
    # asked which was meant.
    "clarify_a": "Did you mean ",
    "clarify_or": " or ",
    "qmark": "?",
    "notes_have": "Here is what your notes say on that: ",
    "open_where": "Here is where you noted it: ",
    # The citation: a titled note by its heading, in bold; a note with no
    # heading by the day it was written, since its first words are what the
    # quote already says.
    "your_note": "your note",
    "your_note_cap": "Your note",
    "a_note_from": "A note from ",
    "one_of_your_notes": "one of your notes",
    "one_of_your_notes_cap": "One of your notes",
    "note_from": " from ",
    "list_from": "From ",
    "latest_a": "Most recently, on ",
    "latest_b": "The newest, from ",
    "latest_undated": "The most recent: ",
    "mention_lead": "At least ",
    "mention_mid": " of your notes mention ",
    "summary_lead": "I found ",
    "summary_mid": " notes on ",
    "from_span": ", from ",
    "to_span": " to ",
    "on_day": ", on ",
    # A list the person wrote, as a sentence or as bullets.
    "lists": " lists ",
    "it_lists": "It also lists ",
    "checklist": "Its checklist has ",
    "checklist_of": " of ",
    "checklist_done": " done:",
    "has": " has ",
    "checklist_items_done": " checklist items done:",
    #: Nothing ticked: "no of three" read as a typo (audit 1029 C6).
    "has_none_of_its": " has none of its ",
    "checklist_none_of_its": "Its checklist has none of its ",
    "one_open": "one item, not done:",
    "end_colon": ":",
    # The notes after the first, joined by how they relate to what came
    # before, never the same joining words twice running and never a pile of
    # "also": the same subject mostly needs no joiner at all, the sentence
    # and its citation are enough. Each joiner takes the quote after a comma
    # when its first word can be lowered ("Separately, the hills are steep"),
    # and after a colon when it cannot ("Separately: Lisbon to Porto ...").
    "and_join": "And ",
    "on_top": "On top of that",
    "separately": "Apart from that",
    "elsewhere": "Elsewhere",
    "another_note": "In another note",
    "later_on": "Later, on ",
    "then_on": "Then on ",
    "earlier_on": "Earlier, on ",
    "and_on": "And on ",
    "latest_c": "As of ",
    "in_cap": "In ",
    "you_listed": " you listed ",
    "across_found": "Across the notes found, ",
    "before_that": "Before that, on ",
    "echo": " (Your notes say this ",
    "echo_end": " times.)",
    "disagree_lead": "Your notes may disagree here. ",
    "but_newer": "But in a newer note",
    "but_older": "But in an older note",
    "but_other": "But in another note",
    "disagree_check": " These may disagree, so it is worth checking which is current.",
    "picture_in": "The picture in ",
    "picture_shows": " shows ",
    "picture_called": " is described as ",
    "picture_reads": " has these words in it: ",
    "timeline": "In the order you wrote them:",
    # A comparison.
    "of_found": "Of the notes found, ",
    "only_lead": "Only ",
    "only_appear": " appears in your notes; nothing mentions ",
    "only_appear_many": " appear in your notes; nothing mentions ",
    "mentions_one": " mentions ",
    #: "which is longer, the budget or the Lisbon trip" (audit 1029 C36).
    "is_longer": " is the longer note: ",
    "is_shorter": " is the shorter note: ",
    "words_against": " words against ",
    "words_in": " in ",
    **composer_versus.SAID,
    "mention_many": " mention ",
    "each_side": "Here is what each says.",
    "side_notes": " notes",
    "side_note": " note",
    "comes_up_in": " comes up in ",
    "compare_lead": "Side by side, ",
    "side_in": " in ",
    "both": "Both together",
    "side_none": "Nothing found is about this one on its own.",
    # The close.
    "missing": "None of these notes mention ",
    "newest_lead": "Your ",
    "newest_guess": "I could not tell what that asks about, so here are your ",
    "newest_mid": " newest notes",
    "newest_one_lead": "Your newest note",
    "newest_one_guess": "I could not tell what that asks about, so here is your newest note",
    "until_ahead_days": " days from today, on ",
    "until_ahead_day": " day from today, on ",
    "until_ago_days": " days ago, on ",
    "until_ago_day": " day ago, on ",
    "until_today": "That is today",
    "until_by_note": ", going by your note: ",
    "open_some": " items are still open on ",
    "open_one": " items is still open on ",
    "open_all_a": "All ",
    "open_all_b": " items on ",
    "open_all_c": " are still open",
    "open_single_a": "The one item on ",
    "open_single_b": " is still open",
    "open_none_a": "Everything on ",
    "open_none_b": " is done: all ",
    "open_none_c": " items are ticked.",
    #: No answer, said plainly and asked back (CHAT_PLAN decision 24; INBOX
    #: 741: "when nothing matches at all, it asks a short clarifying
    #: question instead of returning nothing").
    "nothing": (
        "Nothing in the notes found answers that. Which note would it be in, "
        "or how else might you have put it?"
    ),
    # Recall by time (decision 31): "You wrote three notes last week, newest first:".
    "recall_a": "You wrote ",
    "recall_note": " note ",
    "recall_notes": " notes ",
    "recall_b": ", newest first:",
    #: "around <day>" (INBOX 1739): the days either side, the nearest first.
    "recall_near_b": ", nearest first:",
    #: A day's documents are counted beside its notes (INBOX 1739).
    "recall_made": "You made ",
    "recall_note_and": " note and made ",
    "recall_notes_and": " notes and made ",
    "recall_doc": " document ",
    "recall_docs": " documents ",
    "doc_lead": "Document ",
    "recall_dated_note": " note falls ",
    "recall_dated_notes": " notes fall ",
    #: The window held more than the list shows (audit 1029 C11): say so.
    "recall_more_a": "And ",
    "recall_more_b": " more.",
    "recall_none": "Nothing I found was written ",
    "written_on": " was written on ",
    "open_nowhere_a": "No checklist in your notes about ",
    "open_nowhere_b": " has anything left to tick.",
    "bare_a": "Your note ",
    "bare_b": " is only a title so far, with nothing written under it yet.",
    "none_tagged": "No note found is tagged ",
    # A source that is not a note says its kind in its citation (decision 37):
    # "[board **Harbor board**]".
    "your_board_cap": "Your board",
    "your_map_cap": "Your mind map",
    "your_document_cap": "Your document",
    "kind_board": "board ",
    "kind_map": "map ",
    "kind_document": "document ",
    "kind_file": "file ",
    "kind_web": "page ",
    # The help register (decision 36): after the Help topic's own sentence.
    "help_more": " The Guide, on the status bar, has the rest.",
    "help_more_2": " There is more in the Guide, on the status bar.",
    "help_more_3": " The Guide on the status bar goes further.",
    "help_more_4": " For the rest, open the Guide on the status bar.",
    "help_more_5": " The Guide on the status bar says more.",
    "help_more_6": " Open the Guide on the status bar for the rest.",
    "help_more_7": " The rest is in the Guide, on the status bar.",
    "help_more_8": " The Guide, on the status bar, covers the rest.",
    "help_more_9": " More is in the Guide, on the status bar.",
    "help_more_10": " The Guide on the status bar has the details.",
    # Numbered readings of a question that only names something (decision 45).
    "readings_a": "Which do you mean: ",
    "reading_dot": ". ",
    "semicolon": "; ",
    # A utility the app cannot do (decision 41): said, never guessed.
    "utility_weather": "The weather is not something this app knows, and nothing leaves this computer to look it up.",
    "utility_translate": "Translating needs a model: connect one in Settings and the Writing room translates.",
    "utility_generate": "Writing that needs a model: connect one in Settings, Models. Until then I can find what your notes already say about it.",
    "utility_web_off": "Web search is off, so I only read your notes. Turn it on with the Web button beside the chat box, or in Settings, Web search.",
    "utility_web_on": "Yes: web search is on, in Agent mode. Say what to look up, for example: search the web for train times to Perth.",
    #: The no-answer that names what no note found holds, then asks back:
    #: one pair per voice (`_nothing`).
    "none_found": "Nothing I found mentions ",
    "nothing_ask": "Which note would it be in, or how else might you have put it?",
    "none_found_p": "No note found mentions ",
    "nothing_ask_p": "Which note might hold it, or how else might it be phrased?",
    # An unsure reading of a misspelt word, offered the other way.
    "did_you_mean_a": "Did you mean “",
    "did_you_mean_b": "”?",
    # What to ask next: a note's name, a tag or the question's own words in a
    # fixed question.
    "next_note_a": "What does “",
    "next_note_b": "” say?",
    "next_tag_a": "What else do my notes say about ",
    "ov_next_about": "What did I write about ",
    "ov_doing": " of your notes say what you are working on",
    "ov_list": "a list: ",
    "ov_span_one": ", all from ",
    "picture_text_lead": "a picture with the words ",
    "next_tag_b": "?",
    "next_latest_a": "What is the latest on ",
    "feature_offer": "\n\nThe app has a tool for that too. ",
    "next_when_a": "When did I write about ",
}


#: The voices' variants of the joining phrases and openers (`composer_tables`):
#: ordinary entries, so every closed-set check covers them.
PHRASES.update(composer_tables.OVERVIEW_PHRASES)


PHRASES.update(composer_tables.EXTRA_PHRASES)


PHRASES.update(composer_ack.PHRASES)


PHRASES.update(composer_open.PHRASES)


def phrase_options(key: str, voice: str | None = None) -> tuple[str, ...]:
    """Every wording of `key`: the original and the variants of `voice`, or of
    both voices when none is named (the tests, which pin a phrase by its key,
    ask for all of them: the question picks which one an answer uses)."""
    names = {key}
    for name in composer_tables.VOICES if voice is None else (voice,):
        names.update(composer_tables.VOICE_VARIANTS[name].get(key, ()))
    return tuple(sorted(PHRASES[n] for n in names))
