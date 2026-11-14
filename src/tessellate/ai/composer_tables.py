"""The composer's wider vocabulary, as data (2026-10-06, the owner: "expand the
available sentence sections, grammar, lingo, understanding ... more natural
language and professional language options ... just expand its vocabulary").

Nothing here is logic. `composer.py` merges these tables into its own:

- **Voices.** The composer writes in one of two registers, `natural` (the
  default: plain, friendly) or `professional` (formal, record-keeping), read
  from the `composer_voice` preference. Every joining phrase and opener has
  several variants in each voice; `VOICE_VARIANTS[voice][key]` lists the
  `PHRASES` keys that say what `key` says in that voice. A variant is an
  ordinary `PHRASES` entry, so the closed-set rule holds: the traceability
  check and the copy-rule test cover them all. A variant keeps the shape of
  the phrase it varies (a trailing space stays a trailing space, a phrase
  that ends before a date still ends before a date), so the code around it
  needs no new cases.
- **Synonyms, comparison words, wrappers, lead-ins, small talk, next steps**:
  more of each, in the same shape as the tables they extend.

Every phrase follows the copy rules: sentence case, no em-dashes, no
exclamation marks, no "Oops"; facts stay quoted from the notes, so nothing
here says anything about a note's contents.
"""

from __future__ import annotations

import re

from tessellate.ai import composer_replies
from tessellate.core.lazyre import lazy_compile

VOICES = ("natural", "professional")
DEFAULT_VOICE = "natural"


def voice_of(value: object) -> str:
    """`value` as a voice name: anything unknown is the default. The composed
    voices' "formal" (a persona's cue) reads the professional lines."""
    if value == "formal":
        return "professional"
    return value if value in VOICES else DEFAULT_VOICE


# --- phrase variants ---------------------------------------------------------------

#: canonical key -> {voice: [texts besides the canonical one]}. The canonical
#: text (`composer.PHRASES[key]`) is the first natural variant.
_FAMILIES: dict[str, dict[str, list[str]]] = {
    # Openers: said before the strongest sentence, which is the answer.
    "open_notes": {
        "natural": ["Here is what your notes say: ", "Your notes say: ", "Here is what I found: ", "Here is what I found in your notes: ", "What your notes have: "],
        "professional": ["This is in your notes: ", "Your notes record the following: ", "Per your notes: ", "The relevant entry in your notes reads: ", "Your records show: ", "From the notes on file: "],
    },
    "open_wrote": {
        "natural": ["This is what you wrote: ", "You wrote: ", "Here is how you put it: ", "In your words: "],
        "professional": ["You recorded the following: ", "As you wrote it: ", "In your own words: ", "The entry reads: ", "Your entry states: "],
    },
    "open_put": {
        "natural": ["Here is how your notes put it: ", "You put it like this: ", "Your notes word it like this: ", "In your notes it reads: "],
        "professional": ["Your notes state it as follows: ", "Your notes phrase it as follows: ", "The wording in your notes is: ", "Your notes describe it thus: "],
    },
    "open_figure": {
        "natural": ["Here is the figure you noted: ", "The figure in your notes: ", "You noted this number: ", "The number written down: "],
        "professional": ["The figure recorded in your notes: ", "The recorded figure: ", "The number on record: ", "Your notes give the figure as follows: "],
    },
    "open_date": {
        "natural": ["Here is the date you noted: ", "The date in your notes: ", "You noted this date: ", "The date written down: "],
        "professional": ["The date recorded in your notes: ", "The recorded date: ", "The date on record: ", "Your notes give the date as follows: "],
    },
    "open_where": {
        "natural": ["This is where you noted it: ", "The place in your notes: ", "You noted the place like this: ", "Where it says: "],
        "professional": ["The location recorded in your notes: ", "Your notes give the location as follows: ", "The recorded location: ", "The place on record: "],
    },
    "closest_a": {
        "natural": ["The nearest thing in your notes is this: ", "Not quite, but this is close: ", "Your notes come closest with this: ", "This is the closest I can find: "],
        "professional": ["The nearest entry in your notes reads: ", "The closest relevant entry is: ", "No entry answers this directly. The closest reads: ", "The most relevant entry on file is: "],
    },
    "closest_b": {
        "natural": ["Nothing says that outright. The nearest is: ", "Your notes do not say it directly. The closest is: ", "No note puts it exactly. The nearest is: "],
        "professional": ["Nothing states this directly. The nearest entry is: ", "No entry answers this directly. The closest is: ", "The notes do not state this outright. The nearest entry is: "],
    },
    "going_by": {
        "natural": ["Based on your notes", "From what your notes say", "Judging by your notes", "Reading your notes"],
        "professional": ["According to your notes", "Based on the notes on file", "Per your notes", "As your notes record it", "On the evidence of your notes"],
    },
    "notes_have": {
        "natural": ["Your notes say this on that: ", "This is what your notes say on that: ", "Here is what your notes have on that: ", "On that, your notes say: "],
        "professional": ["Your notes record the following on that: ", "On this point, your notes state: ", "The relevant notes state: ", "Your notes say the following on that: "],
    },
    # Joiners: how the next note is brought in. A trailing space means the
    # quote follows straight on; no trailing space means a comma comes first.
    "and_join": {
        "natural": ["Also ", "Plus ", "As well, "],
        "professional": ["In addition, ", "Additionally, ", "Furthermore, "],
    },
    "on_top": {
        "natural": ["Besides that", "On top of this", "Beyond that", "As well as that"],
        "professional": ["In addition to this", "Moreover", "Further to this", "Beyond this"],
    },
    "separately": {
        "natural": ["On a separate note", "Apart from that", "Aside from that"],
        "professional": ["As a separate point", "Distinct from the above", "As a distinct matter"],
    },
    "elsewhere": {
        "natural": ["In another place", "Somewhere else", "Over in another note"],
        "professional": ["In a separate entry", "Elsewhere in your notes", "In a further entry"],
    },
    "another_note": {
        "natural": ["On a different note"],
        "professional": ["Turning to another matter", "On something else", "As for a different entry"],
    },
    "later_on": {
        "natural": ["Later still, on ", "A little later, on ", "After that, on "],
        "professional": ["Subsequently, on ", "At a later date, on ", "Afterwards, on "],
    },
    "then_on": {
        "natural": ["Next, on ", "Following that, on ", "Soon after, on "],
        "professional": ["Thereafter, on ", "Following this, on ", "At the next entry, on "],
    },
    "earlier_on": {
        "natural": ["Earlier still, on ", "A little earlier, on ", "Going back, on "],
        "professional": ["Previously, on ", "At an earlier date, on ", "Before this, on "],
    },
    "and_on": {
        "natural": ["Also on ", "Plus on ", "And again on "],
        "professional": ["In addition, on ", "Additionally, on ", "Furthermore, on "],
    },
    "before_that": {
        "natural": ["Before then, on ", "Prior to that, on ", "Even earlier, on "],
        "professional": ["Preceding this, on ", "Before this, on ", "At an earlier point, on "],
    },
    "latest_a": {
        "natural": ["Latest of all, on ", "The most recent one, on ", "Newest of all, on "],
        "professional": ["Most recently, as of ", "The most recent entry, dated ", "The latest entry, on "],
    },
    "latest_b": {
        "natural": ["The freshest, from ", "The latest, from ", "Newest of all, from "],
        "professional": ["The most recent entry, from ", "The latest entry, from ", "The newest entry, from "],
    },
    "latest_c": {
        "natural": ["Up to ", "As things stood on "],
        "professional": ["As recorded on ", "Current as of "],
    },
    "latest_undated": {
        "natural": ["The newest one: ", "The latest one: ", "The last one: "],
        "professional": ["The most recent entry: ", "The latest entry: ", "The newest entry: "],
    },
    "of_found": {
        "natural": ["Among the notes found, ", "Looking at the notes found, "],
        "professional": ["Of the notes retrieved, ", "Among the notes retrieved, "],
    },
    #: A compare asked again in one chat (L205 left its counts as the only opener: one way over twenty turns).
    "compare_lead": {
        "natural": ["Side by side, ", "By the count, ", "Counting the notes, ", "Put side by side, ", "Going by your notes, ",
                    "To compare, ", "In numbers, ", "Laid side by side, ", "Weighing them up, "],
        "professional": ["In comparison, ", "By count, ", "Comparing the records, ", "Set side by side, ", "On the record, ",
                         "For comparison, ", "In terms of number, ", "Measured by notes, ", "Taken together, "],
    },
    "across_found": {
        "natural": ["Looking across the notes found, ", "Taking the notes found together, "],
        "professional": ["Across the notes retrieved, ", "Taken together, the notes retrieved show that "],
    },
    # Disagreement.
    "disagree_lead": {
        "natural": ["Your notes might not agree here. ", "Your notes may say different things here. ", "Careful, your notes may disagree here. "],
        "professional": ["Your notes may conflict on this point. ", "There may be a discrepancy in your notes. ", "Your notes appear to differ here. "],
    },
    "but_newer": {
        "natural": ["Yet in a newer note", "Then again, in a newer note"],
        "professional": ["However, in a newer note", "By contrast, in a newer note", "Conversely, in a newer note"],
    },
    "but_older": {
        "natural": ["Yet in an older note", "Then again, in an older note"],
        "professional": ["However, in an older note", "By contrast, in an older note", "Conversely, in an older note"],
    },
    "but_other": {
        "natural": ["Yet in another note", "Then again, in another note"],
        "professional": ["However, in another note", "By contrast, in another note", "Conversely, in another note"],
    },
    "disagree_check": {
        "natural": [" They may disagree, so it is worth checking which is current.", " That may not match, so it is worth checking which is current.", " These could conflict, so check which one is current."],
        "professional": [" These entries may conflict, so it is advisable to confirm which is current.", " These may be inconsistent, so please confirm which is current.", " The two may differ, so it is worth confirming which is current."],
    },
    # Lists and comparisons.
    "timeline": {
        "natural": ["Oldest first:", "Here they are, oldest first:", "In the order they were written:"],
        "professional": ["In date order:", "Listed chronologically:", "In order of entry:"],
    },
    "each_side": {
        "natural": ["Here is what each one says.", "This is what each says.", "Here is each side."],
        "professional": ["Each is set out below.", "Each side follows.", "The notes on each side follow."],
    },
    "side_none": {
        "natural": ["Nothing found is about this one by itself.", "Nothing here is only about this one."],
        "professional": ["Nothing found addresses this side on its own.", "No entry found concerns this side alone."],
    },
    "both": {
        "natural": ["Both at once", "Both in one place"],
        "professional": ["Both combined", "Taken together"],
    },
    "missing": {
        "natural": ["None of these notes say anything about ", "These notes do not mention "],
        "professional": ["None of the notes found mention ", "No note found mentions ", "The notes found make no mention of "],
    },
    # No answer: one voice each, since the wording must stay a question.
    "nothing": {
        "natural": [],
        "professional": ["None of the notes found answers that. Which note might hold it, or how else might it be phrased?"],
    },
}

#: Pairs said around a measured value: the second takes the first's index, so
#: "Recorded on 3 March: ..." never meets "you wrote: ". Equal lengths.
_PAIRS: dict[str, dict[str, list[str]]] = {
    "wrote_on_a": {
        "natural": ["You wrote this on ", "Back on ", "On "],
        "professional": ["Recorded on ", "Dated ", "Entered on ", "As of "],
    },
    "wrote_on_b": {
        "natural": [": ", " you wrote: ", " you noted: "],
        "professional": [": ", ": ", ": ", ", your notes state: "],
    },
    #: "At least three of your notes mention “sourdough”": the one opener a
    #: broad question had, so twenty turns of it opened alike (CHAT_PLAN
    #: decision 51's floor, measured 1 of 20 before these).
    #: Eight a voice since Brief 84 (decision 59's social variation: the
    #: floor's lowest question opened three ways in twenty turns).
    "mention_lead": {
        "natural": ["I count at least ", "No fewer than ", "I found at least ", "There are at least ",
                    "By my count, at least ", "I can see at least ", "Going through them, at least ", "It looks like at least "],
        "professional": ["At least ", "A minimum of ", "No fewer than ", "The records show at least ",
                         "Upon review, at least ", "By count, at least ", "The search returns at least ", "In total, at least ",
                         "On record, at least ", "The notes hold at least "],
    },
    "mention_mid": {
        "natural": [" of your notes that mention ", " of your notes bring up ", " notes of yours that mention ", " notes of yours that mention ",
                    " of your notes bring up ", " of your notes that mention ", " of your notes mention ", " of your notes mention "],
        "professional": [" of the entries mention ", " entries reference ", " of the records mention ", " entries that mention ",
                         " of the entries mention ", " entries reference ", " entries that reference ", " of the records mention ",
                         " entries reference ", " entries that mention "],
    },
    #: A broad answer over several notes, none of which holds every word
    #: asked, opens with one clause naming the topic and how many notes it
    #: quotes (INBOX 729: "it just uses one word sentence joints").
    "summary_lead": {
        "natural": ["Here are ", "There are ", "I have "],
        "professional": ["The records hold ", "Retrieved: ", "There are "],
    },
    "summary_mid": {
        "natural": [" of your notes on ", " notes here on ", " notes that bear on "],
        "professional": [" entries on ", " entries concerning ", " relevant entries on "],
    },
}
#: The overview of a topic (INBOX 787, the owner: "the composer is still
#: pretty barebone, has no life to it"): how many notes, over which days,
#: the thread most of them share, then the notes grouped by it. Each pair
#: varies together so "You have ... notes about" never meets "entries on".
_OVERVIEW_PAIRS: dict[str, dict[str, list[str]]] = {
    "ov_lead_a": {
        "natural": ["I found ", "There are ", "Your notebook holds "],
        "professional": ["The notebook holds ", "There are ", "The records show "],
    },
    "ov_lead_b": {
        "natural": [" notes about ", " notes on ", " notes about "],
        "professional": [" entries on ", " entries concerning ", " entries on "],
    },
    #: Every first half reads with every second half: a conversation that has
    #: used one second half picks another, whichever first half it has.
    "ov_span_a": {
        "natural": [", from ", ", running from "],
        "professional": [", dated ", ", spanning "],
    },
    "ov_span_b": {
        "natural": [" to ", " to "],
        "professional": [" to ", " to "],
    },
    "ov_theme_mid": {
        "natural": [" is in ", " features in "],
        "professional": [" appears in ", " is mentioned in "],
    },
    "ov_who_mid": {
        "natural": [" is in ", " appears in "],
        "professional": [" appears in ", " is named in "],
    },
    "ov_who_end": {
        "natural": [" of your notes", " of your notes"],
        "professional": [" entries", " entries"],
    },
    "ov_shared_mid": {
        "natural": [" comes up in ", " is in "],
        "professional": [" appears in ", " is named in "],
    },
    "ov_shared_end": {
        "natural": [" of these notes.", " of them."],
        "professional": [" of these entries.", " of these entries."],
    },
    "ov_more_a": {
        "natural": ["There are ", "And "],
        "professional": ["A further ", "There are "],
    },
    "ov_more_b": {
        "natural": [" more besides.", " more not shown here."],
        "professional": [" entries not shown.", " entries not shown here."],
    },
}
_FAMILIES.update({
    "ov_also": {"natural": ["Other notes", "The rest"], "professional": ["Other entries", "Remaining entries"]},
    #: The one left over, said as one (never "There are one more besides": audit 1031 C36).
    "ov_one_more": {"natural": ["There is one more besides.", "And one more not shown here."], "professional": ["One further entry is not shown.", "One entry is not shown here."]},
    "ov_reads": {"natural": [", which reads ", ", with the words "], "professional": [", reading ", ", which reads "]},
})
_PAIRS.update(_OVERVIEW_PAIRS)
#: The canonical texts the variants above vary (`composer.PHRASES` takes them).
OVERVIEW_PHRASES = {
    "ov_lead_a": "You have ",
    "ov_lead_b": " notes about ",
    "ov_span_a": ", written from ",
    "ov_span_b": " to ",
    "ov_theme_mid": " comes up in ",
    "ov_theme_end": " of them.",
    "ov_who_mid": " comes up in ",
    "ov_who_end": " of your notes",
    "ov_shared_mid": " is in ",
    "ov_shared_end": " of these notes.",
    "ov_more_a": "Plus ",
    "ov_more_b": " more.",
    "ov_one_more": "Plus one more.",
    "ov_filed": " are filed under it",
    "ov_filed_one": " is filed under it",
    "ov_also": "Also",
    "ov_reads": ", reading ",
    "ov_next_who": "Who is ",
}
#: The canonical `wrote_on_b` pairs with the canonical `wrote_on_a`.
PAIRED = {
    "wrote_on_b": "wrote_on_a", "mention_mid": "mention_lead", "summary_mid": "summary_lead",
    "ov_lead_b": "ov_lead_a", "ov_span_b": "ov_span_a", "ov_who_end": "ov_who_mid",
    "ov_shared_end": "ov_shared_mid", "ov_more_b": "ov_more_a",
    "echo_end": "echo", "next_tag_b": "next_tag_a", "next_note_b": "next_note_a",
}


#: Variants added on 2026-10-10 from the Gemini branch, filtered: no filler
#: openers ("Ah,", "Hm,", "Let's see..."; the owner: "I think a lot of
#: composer responses start with 'ah,'"), no exclamation marks, no "closest
#: match" (INBOX 724), no two strings glued by a missing comma, and only a
#: variant whose ending matches its family's (a family ending ": " is followed
#: straight by the quote). The dropped ones are listed in the triage notes.
_FAMILIES_ADDED: dict[str, dict[str, list[str]]] = {'open_notes': {'natural': ['From your notes: ',
                            'This is in your notes: ',
                            'Your notes say: ',
                            "From what you saved: ",
                            "I found this in your notebook: ",
                            'From your entries: ',
                            "It says here: ",
                            'Your notebook has: ',
                            'In your entries: ',
                            'From your notebook: ',
                            'In your notebook: ',
                            'In your notes: ',
                            'Here is what you have down: '],
                'professional': ['A review of your records indicates: ',
                                 'The documentation shows: ',
                                 'As documented in your notes: ',
                                 'Based on the available records: ',
                                 'Referencing your entries: ']},
 'open_wrote': {'natural': ['Here is what you wrote: ',
                            'You wrote this: ',
                            'You saved this: ',
                            "You wrote down: ",
                            'You wrote this down: ',
                            'Here is the note: '],
                'professional': ['The exact phrasing in your records is: ',
                                 'Your documentation notes: ',
                                 'The record indicates: ']},
 'open_put': {'natural': ["It is worded like this: ",
                          'Your note puts it like this: ',
                          'Here is how you worded it: ',
                          'This is how you wrote it: ',
                          'It reads: '],
              'professional': ['It is expressed in the records as: ',
                               'The formal entry states: ',
                               'The phrasing recorded is: ']},
 'open_figure': {'natural': ["You wrote down this amount: ",
                             'The number in your note: ',
                             'The figure is: ',
                             'The amount in your notes: ',
                             "The number is: "],
                 'professional': ['The recorded value is: ',
                                  'According to the entry, the figure is: ',
                                  'The stated numerical value is: ',
                                  'The specific amount noted is: ']},
 'open_date': {'natural': ["The date is: ",
                           'The day in your note: ',
                           'The date in your note: ',
                           'The date reads: ',
                           'The time in your note: '],
               'professional': ['The specified date is: ',
                                'The scheduled date recorded is: ',
                                'The timestamp noted is: ',
                                'As dated in the records: ']},
 'open_where': {'natural': ["The place in your note: ",
                            'The place in your notes: ',
                            'The place is: ',
                            'The place reads: ',
                            'Where, in your note: '],
                'professional': ['The address specified in the entry is: ',
                                 'The site documented is: ',
                                 'The recorded whereabouts are: ',
                                 'According to the entry, the location is: ']},
 'closest_a': {'natural': ['The closest your notes come is this: ',
                           'Here is the nearest I found: ',
                           'The closest thing to that is: ',
                           "Your best match is: ",
                           'This is the nearest thing: ',
                           'The nearest note reads: ',
                           'The nearest I could find is: '],
               'professional': ['An exact match is unavailable; the most related entry states: ',
                                'While indirect, the closest record indicates: ',
                                'The most pertinent note available reads: ',
                                'There is no direct reference. The nearest approximation is: ']},
 'closest_b': {'natural': ['Nothing here says it outright. The nearest is: ',
                           "It doesn't say exactly, but the closest is: ",
                           "I couldn't find an exact match, but this is close: ",
                           "There's no direct mention. The best match is: ",
                           'Not stated explicitly, but the closest thing is: ',
                           "There isn't a direct answer, but this comes close: ",
                           "I didn't see an exact hit. The nearest entry is: "],
               'professional': ['An explicit answer is not recorded. The closest relevant entry is: ',
                                ('There is no unequivocal statement on this matter. The most pertinent entry '
                                'is: '),
                                'Direct clarification is absent. The nearest equivalent is: ']},
 'going_by': {'natural': ['Going by your notes',
                          'Based on your records',
                          'According to what you saved',
                          'In your notes',
                          'From your entries',
                          'Going by your notebook',
                          'From what is written here',
                          'According to your entries',
                          'From your notes',
                          'From what I found'],
              'professional': ['As indicated by the records',
                               'Based on the documentation',
                               'According to the available entries',
                               'As documented',
                               'In light of the recorded notes']},
 'notes_have': {'natural': ['Here is what your notes say on that: ',
                            'This is what you have saved: ',
                            "Here's what your records show: ",
                            'Your notes say this: ',
                            'Here is what I found on that: ',
                            'This is what I found on that: ',
                            "Here is what you saved on that: ",
                            'Your entries say: '],
                'professional': ['Regarding this matter, the records show: ',
                                 'The associated documentation reads: ',
                                 'The entry corresponding to this subject states: ',
                                 'In relation to this, the file reads: ',
                                 'The record states the following on this topic: ']},
 'and_join': {'natural': ['And ',
                          'Plus, ',
                          'Additionally, ',
                          'Also, ',
                          "What's more, ",
                          'On top of that, ',
                          'Furthermore, ',
                          'Moreover, ',
                          'Along with this, ',
                          'Together with that, ',
                          'At the same time, ',
                          'Coupled with this, ',
                          'Not to mention, ',
                          'As well as that, ',
                          'To add to this, ',
                          'In addition, ',
                          'To build on that, ',
                          'Adding to the thought, ',
                          'Expanding on this, '],
              'professional': ['Moreover, ',
                               'Further, ',
                               'As an additional point, ',
                               'Complementary to this, ',
                               'In parallel, ']},
 'on_top': {'natural': ['Along with that',
                        'To add to that',
                        'More than that',
                        'In addition to that',
                        'Besides that',
                        'And',
                        'Along the same lines',
                        'Adding to that'],
            'professional': ['As a supplementary point',
                             'Coupled with this',
                             'Building on this',
                             'And',
                             'In conjunction with this',
                             'Besides that',
                             'In addition',
                             'Supplementary to this']},
 'separately': {'natural': ['Apart from that',
                            'Elsewhere',
                            'In another place',
                            'In a different note',
'On something else',
],
                'professional': ['In a separate context',
                                 'Independently',
                                 'Separately noted',
                                 'Addressing a separate matter',
                                 'On an unrelated point',
                                 'In an independent entry',
                                 'Regarding a distinct matter',
                                 'Addressed separately',
                                 'In an unrelated context',
                                 'In another section of the records']},
 'elsewhere': {'natural': ['Elsewhere',
                           'In other notes',
                           'In your other notes',
                           'In another note',
'In another part of your notebook',
'Somewhere else in your notes',
],
               'professional': ['In another location',
                                'Documented elsewhere',
                                'In a distinct file',
                                'In a different section of the records']},
 'another_note': {'natural': ['In another note',
                              'In another note',
                              'In a different note',
'In a different note',
'Elsewhere in your notes',
'Another note has it as'],
                  'professional': ['Addressing a distinct topic',
                                   'Transitioning to a separate point',
                                   'With regard to another note',
                                   'In reference to a separate entry',
                                   'Shifting focus to another record']},
 'later_on': {'natural': ['Later, on ',
                          'A while later, on ',
                          'A while after, on ',
                          'Then, on ',
                          'Following that, on ',
                          'After that, on ',
                          'In the end, on ',
                          'A bit later, on ',
                          'Then, on ',
                          'Then, on ',
                          'Later still, on ',
                          'Later still, on '],
              'professional': ['In a subsequent entry, dated ',
                               'Following that time, on ',
                               'Further in time, on ',
                               'Progressing chronologically to ',
                               'At a later juncture, on ',
                               'In a later record on ',
                               'Following this entry, on ',
                               'A subsequent entry on ',
                               'In a more recent document on ',
                               'Proceeding chronologically to ',
                               'Later documentation on ',
                               'In a following record on ',
                               'As noted in a later entry on ']},
 'then_on': {'natural': ['Then on ',
                         'Next on ',
                         'After that, on ',
                         'After that, on ',
                         'And then on ',
                         'Then there is ',
                         'Next, on ',
                         'Next, on ',
                         'Then, on '],
             'professional': ['In the following record, dated ',
                              'Subsequently, on ',
                              'The subsequent entry on ',
                              'Then, on ',
                              'In due course, on ']},
 'earlier_on': {'natural': ['Earlier, on ',
                            'Before that, on ',
                            'Before this, on ',
                            'Going back, on ',
                            'Back on ',
                            'Previously, on ',
                            'Earlier, on ',
                            'Back on ',
                            'Long before, on ',
                            'Earlier in your notes on ',
                            'Before that, on '],
                'professional': ['In a preceding entry, dated ',
                                 'Earlier in the timeline, on ',
                                 'Historically, on ',
                                 'Dating back to ',
                                 'In a prior record, on ']},
 'and_on': {'natural': ['Another one on ',
                        "There is also this on ",
                        'And here is another on ',
                        'As well as on ',
                        'There is this from '],
            'professional': ['A further entry on ',
                             'Also recorded on ',
                             'Moreover, on ',
                             'Supplementary to this, on ']},
 'before_that': {'natural': ['Before that, on ',
                             'Earlier, on ',
                             'Going further back, to ',
                             'Before that, on ',
                             'Long before that, on ',
                             'Even further back, on '],
                 'professional': ['In a prior instance, dated ',
                                  'Chronologically prior, on ',
                                  'In the preceding entry on ']},
 'latest_a': {'natural': ['The latest, from ',
                          'Most recently, on ',
                          'The newest, on ',
                          'Most recently, on ',
                          'Most recently, on '],
              'professional': ['The final record, dated ',
                               'Concluding the timeline on ',
                               'The ultimate entry on ',
                               'The latest available data, as of ',
                               'Updating to the most recent record on ']},
 'latest_b': {'natural': ['The latest, from ',
                          'The newest, from ',
                          'Most recently, from ',
                          'The latest, from '],
              'professional': ['The most current record, originating from ',
                               'The concluding note, dated ',
                               'The definitive recent entry, from ',
                               'The latest documentation from ']},
 'latest_c': {'natural': ['As of ', 'Where things left off on '],
              'professional': ['As of the record dated ']},
 'latest_undated': {'natural': ['The newest note: ',
                                'The latest one: ',
                                'Here is the latest one: ',
                                'The newest one: ',
                                'The latest note: '],
                    'professional': ['The most current record: ',
                                     'The final documented point: ',
                                     'The most recent update available: ',
                                     'The latest recorded observation: ']},
 'of_found': {'natural': ['Of these notes, ',
                          'Among these notes, ',
                          'In these notes, ',
                          'Of the notes here, ',
                          'Going by these, ',
                          'Looking at these notes, '],
              'professional': ['Of these entries, ',
                               'Between these entries, ',
                               'Based on these entries, ',
                               'In these entries, ',
                               'Within these entries, ',
                               'Among the matching entries, ',
                               'Of the pertinent records, ',
                               'Per these entries, ']},
 'across_found': {'natural': ['If we look at all these notes, ',
                              'Across these notes, ',
                              'Together, ',
                              'Together, ',
                              'Overall, ',
                              'Overall, '],
                  'professional': ['Aggregating these records, ',
                                   'Consolidating the data from the entries, ',
                                   'In aggregate, these records show ',
                                   'Evaluating the records collectively, ']},
 'disagree_lead': {'natural': ['Your notes may disagree here. ',
                               'There seems to be a conflict in your notes. ',
                               "I'm seeing some conflicting information. ",
                               'Your notes have differing accounts on this. ',
                               'Interestingly, your notes disagree here. ',
                               "There's a bit of a contradiction in your records. ",
                               'Your entries are saying two different things here. '],
                   'professional': ['The records contain contradictory information. ',
                                    'A potential inconsistency exists in the documentation. ',
                                    'The entries do not appear to align on this matter. ',
                                    'Note a discrepancy within the records regarding this. ',
                                    'The documented evidence presents conflicting details. ']},
 'but_newer': {'natural': [], 'professional': ['In a more recent document, however']},
 'but_older': {'natural': [], 'professional': ['In a preceding document, however']},
 'but_other': {'natural': [], 'professional': ['In a distinct document, however']},
 'disagree_check': {'natural': [' They differ, so check which one is right.',
                                " They conflict, so it is worth checking which one is right.",
                                ' They do not match, so check the latest one.',
                                ' They do not match, so it is worth a second look.',
                                ' Check which one still applies.'],
                    'professional': [(' Due to this discrepancy, verification of the current status is '
                                     'recommended.'),
                                     ' It is prudent to cross-reference these entries for accuracy.',
                                     ' Resolution of this inconsistency is advised.',
                                     ' Please verify the correct information, given the discrepancy.',
                                     ' Confirmation of the accurate record is recommended.']},
 'timeline': {'natural': ['In the order you wrote them:',
                          'Oldest first:',
                          'Here they are in order:',
                          'In order:',
                          'In order:',
                          'In date order:',
                          'In date order:',
                          'Oldest to newest:'],
              'professional': ['Presented in chronological sequence:',
                               'Ordered by date of entry:',
                               'Sequenced chronologically:',
                               'Following the timeline of records:',
                               'Listed from earliest to latest:']},
 'each_side': {'natural': ['Here is what each says.',
                           "Here are both.",
                           'Here is each one.',
                           "Here is what you wrote for each.",
                           'Here is what each says.'],
               'professional': ['Details for each are provided below.',
                                'The respective entries are as follows.',
                                'Information pertaining to each follows.',
                                'The documentation for both is detailed below.',
                                'A breakdown of each is presented.']},
 'side_none': {'natural': ["I didn't find anything specifically on this.",
                           "There is no note on this one alone.",
                           "This one has no note of its own.",
                           'No note is only about this.',
                           'I have nothing on this one alone.',
                           "There is no note about this one alone."],
               'professional': ['There is no isolated documentation for this subject.',
                                'No specific record pertains solely to this.',
                                'An exclusive entry for this was not retrieved.',
                                'The records lack a standalone mention of this.',
                                'No independent documentation is available for this.',
                                'This topic lacks an isolated entry in the records.']},
 'both': {'natural': ['Both together',
                      'The two together',
                      'Both together',
                      'Both together',
                      'Together',
                      'Both together'],
          'professional': ['In combination', 'Evaluating both simultaneously', 'Considered jointly']},
 'missing': {'natural': ['None of these notes mention ',
                         'These notes do not mention ',
                         "I can't find anything about ",
                         'There is nothing in these notes about ',
                         'No note mentions ',
                         "I can't find anything about ",
                         'These notes say nothing about ',
                         'None of these notes say anything about '],
             'professional': ['The retrieved documentation lacks any reference to ',
                              'There is no recorded information regarding ',
                              'The entries omit any discussion of ',
                              'The provided records do not address ',
                              'An absence of documentation was noted for ']},
 'nothing': {'natural': [], 'professional': []}}
#: The professional register for the fragments that had none (L97): how many notes mention a thing, an
#: echoed sentence, a note that lists, the citation tail and the next-question chips. Natural keeps its one
#: wording, so only the professional voice changes; each pair has equal lengths.
_PAIRS_ADDED: dict[str, dict[str, list[str]]] = {
    "mentions_one": {"natural": [], "professional": [" refers to ", " makes reference to ", " records "]},
    "mention_many": {"natural": [], "professional": [" refer to ", " make reference to ", " record "]},
    "echo": {"natural": [], "professional": [" (This statement is repeated ", " (The same statement appears "]},
    "echo_end": {"natural": [], "professional": [" times in the records.)", " times across the entries.)"]},
    "lists": {"natural": [], "professional": [" enumerates ", " itemises ", " sets out "]},
    "cite_from": {"natural": [], "professional": [" Source: your ", " Recorded in your ", " Taken from your "]},
    "cite_from_note": {"natural": [], "professional": [" Source: your note ", " Recorded in your note ", " Taken from your note "]},
    "next_tag_a": {"natural": [], "professional": ["What further records exist on ", "Which other entries address "]},
    "next_tag_b": {"natural": [], "professional": ["?", "?"]},
    "next_note_a": {"natural": [], "professional": ["What does the entry “", "What is recorded in the entry “"]},
    "next_note_b": {"natural": [], "professional": ["” state?", "” contain?"]},
    "next_latest_a": {"natural": [], "professional": ["What is the most recent entry on ", "What is the latest record on "]},
    "next_when_a": {"natural": [], "professional": ["On what date was an entry made on ", "When was a record made about "]},
}
#: Nothing found, eight ways a voice (the owner: "can it have more varied
#: responses??"); the families start empty here and take their lines whole.
for _key in composer_replies.NOTHING_FAMILIES:
    _FAMILIES.setdefault(_key, {"natural": [], "professional": []})
for _table, _added in ((_FAMILIES, _FAMILIES_ADDED), (_PAIRS, _PAIRS_ADDED), (_FAMILIES, composer_replies.NOTHING_FAMILIES)):
    for _key, _by_voice in _added.items():
        _table.setdefault(_key, {"natural": [], "professional": []})
        for _voice, _variants in _by_voice.items():
            _table[_key][_voice] = _table[_key][_voice] + _variants


def _build() -> tuple[dict[str, str], dict[str, dict[str, tuple[str, ...]]], dict[str, str]]:
    extra: dict[str, str] = {}
    voices: dict[str, dict[str, tuple[str, ...]]] = {"natural": {}, "professional": {}}
    canon: dict[str, str] = {}
    for key, by_voice in {**_FAMILIES, **_PAIRS}.items():
        for voice, texts in by_voice.items():
            tag = "n" if voice == "natural" else "p"
            keys = [f"{key}_{tag}{i}" for i in range(1, len(texts) + 1)]
            for name, text in zip(keys, texts):
                extra[name] = text
                canon[name] = key
            #: Natural keeps the original phrase as its first variant; the
            #: professional list is its own words only (a key with none in
            #: one voice says its original in both).
            voices[voice][key] = (key, *keys) if voice == "natural" else tuple(keys) or (key,)
    return extra, voices, canon


EXTRA_PHRASES, VOICE_VARIANTS, CANON = _build()


# --- synonyms ---------------------------------------------------------------------

#: One thing said several ways, never a broader idea (the rule of
#: `composer.SYNONYM_GROUPS`, which these extend). Everyday topics.
EXTRA_SYNONYM_GROUPS: tuple[tuple[str, ...], ...] = (
    # Time.
    ("deadline", "due", "cutoff"),
    ("schedule", "agenda", "timetable", "calendar", "itinerary"),
    ("late", "delayed", "overdue"),
    ("daily", "everyday"),
    ("yearly", "annual", "annually"),
    ("often", "frequently", "regularly"),
    ("quickly", "fast", "rapid", "speedy", "swift"),
    ("anniversary", "birthday", "bday"),
    ("booking", "reservation"),
    # Money.
    ("salary", "wage", "income", "earnings"),
    ("invoice", "bill", "receipt"),
    ("refund", "reimbursement", "repayment"),
    ("loan", "mortgage", "debt", "borrow"),
    ("rent", "lease", "tenancy"),
    ("tax", "taxes", "vat"),
    ("insurance", "insured", "insurer"),
    ("discount", "sale", "voucher", "coupon"),
    ("expense", "expenses", "outgoings", "spending"),
    # Work.
    ("boss", "manager", "supervisor"),
    ("colleague", "coworker", "teammate", "workmate"),
    ("promotion", "promoted"),
    ("interview", "screening"),
    ("resume", "cv"),
    ("task", "todo", "errand", "chore"),
    ("client", "customer"),
    ("proposal", "pitch", "bid"),
    ("report", "writeup"),
    ("presentation", "slides", "deck"),
    ("email", "mail"),
    ("contract", "agreement"),
    ("office", "workplace"),
    ("feedback", "critique", "evaluation"),
    ("goal", "target", "objective", "aim"),
    ("project", "initiative"),
    # Study.
    ("exam", "quiz", "examination"),
    ("homework", "assignment", "coursework"),
    ("lecture", "lesson", "seminar"),
    ("teacher", "tutor", "professor", "lecturer", "instructor"),
    ("study", "revise", "revision", "learn", "learning"),
    ("student", "pupil"),
    ("university", "college", "uni"),
    ("essay", "paper", "dissertation", "thesis"),
    ("degree", "diploma", "qualification"),
    # Health.
    ("medicine", "medication", "meds", "pills", "tablets", "prescription"),
    ("sick", "ill", "unwell", "poorly"),
    ("pain", "ache", "sore", "hurt", "hurts"),
    ("sleep", "nap", "snooze"),
    ("exercise", "workout", "gym", "fitness"),
    ("diet", "nutrition"),
    ("dentist", "dental", "teeth", "tooth"),
    ("hospital", "clinic", "surgery"),
    ("allergy", "allergic", "allergies"),
    ("vaccine", "vaccination", "jab"),
    ("therapy", "counselling", "therapist", "counsellor"),
    # Travel.
    ("flight", "plane", "airline", "fly", "flying"),
    ("passport", "visa"),
    ("luggage", "baggage", "suitcase", "bags"),
    ("train", "rail", "railway"),
    ("bus", "coach"),
    ("taxi", "cab", "uber"),
    ("ticket", "tickets"),
    ("tour", "sightseeing", "excursion"),
    ("beach", "coast", "seaside", "shore"),
    ("directions", "route"),
    ("arrive", "arrival"),
    ("depart", "departure", "leave", "leaving"),
    ("lodging", "hostel", "bnb", "guesthouse"),
    # Home.
    ("fix", "repair", "mend"),
    ("clean", "cleaning", "tidy"),
    ("sofa", "couch", "settee"),
    ("fridge", "refrigerator"),
    ("tv", "television"),
    ("bin", "trash", "rubbish", "garbage"),
    ("garden", "yard", "lawn"),
    ("bathroom", "toilet", "loo", "washroom"),
    ("neighbour", "neighbor"),
    ("move", "moving", "relocate", "relocation"),
    ("boiler", "heating", "heater", "radiator"),
    ("paint", "painting", "decorate", "decorating"),
    ("roommate", "flatmate", "housemate"),
    # People.
    ("mum", "mom", "mother", "mam"),
    ("dad", "father"),
    ("brother", "bro", "sibling"),
    ("sister", "sis"),
    ("spouse", "partner"),
    ("kid", "kids", "child", "children"),
    ("baby", "infant", "newborn"),
    ("grandma", "granny", "gran", "nan", "nana", "grandmother"),
    ("grandpa", "grandad", "granddad", "grandfather"),
    ("party", "celebration", "celebrate", "gathering", "get-together"),
    # Feelings.
    ("happy", "glad", "pleased", "delighted", "cheerful"),
    ("sad", "unhappy", "upset", "gloomy", "miserable"),
    ("angry", "mad", "furious", "annoyed", "irritated"),
    ("scared", "afraid", "frightened", "fear"),
    ("excited", "thrilled", "eager", "keen"),
    ("tired", "exhausted", "weary", "fatigue"),
    ("bored", "boring", "dull"),
    ("hate", "dislike", "detest"),
    ("proud", "pride"),
    ("lonely", "isolated"),
    ("confused", "puzzled", "unsure", "unclear"),
    ("calm", "relaxed", "peaceful"),
    ("grateful", "thankful"),
    ("worried", "anxious", "nervous", "concerned", "stressed", "stress", "anxiety"),
    # Tasks.
    ("finish", "complete", "done", "finished", "wrap"),
    ("start", "begin", "started", "began"),
    ("delay", "postpone", "defer", "reschedule"),
    ("cancel", "scrap", "abandon"),
    ("urgent", "asap", "pressing"),
    ("prepare", "prep", "preparing"),
    ("blocked", "stuck", "stalled"),
    ("arrange", "organise", "organize"),
    # Places.
    ("restaurant", "cafe", "diner", "bistro", "eatery"),
    ("pub", "tavern"),
    ("shop", "store"),
    #: "What do I need from the shops" is the grocery list (2026-10-30 sweep).
    ("shops", "groceries", "grocery", "supermarket"),
    ("museum", "gallery"),
    ("cinema", "theater", "theatre"),
    ("address", "location", "street"),
    ("city", "town"),
    ("country", "nation"),
    ("neighbourhood", "neighborhood", "district", "suburb"),
    ("mountain", "peak", "summit"),
    ("church", "chapel", "cathedral"),
    # Comparison words said two ways.
    ("better", "superior", "preferable", "nicer"),
    ("cheaper", "cheapest"),
    ("faster", "quicker", "speedier"),
    ("pros", "advantages", "benefits", "upsides"),
    ("cons", "disadvantages", "drawbacks", "downsides"),
)

# --- comparison ---------------------------------------------------------------------

_MORE = (
    ("better|worse|cheaper|faster|slower|bigger|smaller|larger|longer|shorter|easier|harder|safer|nearer|closer|"
    "nicer|quicker|lighter|heavier|pricier|costlier|cheapest|soonest|oldest|newest|sooner|earlier|later|older|newer|(?:more|less) [a-z]+")
)

#: "which note", "which one", "which of the two": the same ask as "which".
_WHICH = r"which(?: (?:one|note|entry|of (?:the|these|those|my) (?:two|notes)|of them|(?!(?:is|are|was|were)\b)[a-z]+))?"

#: "what do I know about Tom and Sara" (composer-r6 E10): two things asked about at once are
#: answered one at a time, like a comparison's sides, not as one pooled search. Short names
#: only, and no clause on the right ("... and what I should pack" is one question).
_EACH_LEAD = (
    r"(?:what (?:do|did|have|can|could) (?:i|we|you|my notes)(?: (?:ever|already|really))? (?:know|say|said|written|wrote|noted|saved|mention|jotted)|"
    r"tell me|remind me|show me|"
    r"anything|everything|what(?:'s| is| do you know))\s*(?:all )?(?:about|on|regarding)"
)
_EACH_NAME = r"(?!(?:what|how|why|when|where|who|which|if|that|i|my|me)\b)[\w'’ ,-]{1,30}?"

#: The bare form ("what do my notes say about Tom and Sara" is read down to "Tom and Sara"
#: by `rephrase`): capitalised names only, as typed, so "salt and pepper" stays one thing.
_NAME = r"[A-Z][\w'’-]+(?: [A-Z][\w'’-]+)?"
_BARE_NAMES = rf"^(?P<a>{_NAME}(?:, {_NAME})*),? and (?P<b>{_NAME})[?.!]*$"

#: "tom and sara" as typed in lower case: two names only when neither is an everyday word ("salt and pepper" stays one thing); `composer_ask.compare_sides` is the gate.
LOWER_PAIR = lazy_compile(r"^(?P<a>[a-z][\w'’-]{1,20}) and (?P<b>[a-z][\w'’-]{1,20})[?.!]*$")

#: Tried last (after the comparison verbs, or "Compare Lisbon and Porto" would be a bare pair).
BARE_COMPARE_SIDES: tuple[re.Pattern[str], ...] = (lazy_compile(_BARE_NAMES),)

#: "one mentions", "two mention", "the other mentions": the composer's own count lead for a comparison.
_COUNT_MENTIONS = r"(?:one|two|three|four|five|six|\d+|the other)\s+mentions?"

#: Two-sided comparison patterns, tried after the originals in
#: `composer._COMPARE_SIDES`: each needs both sides in the question.
EXTRA_COMPARE_SIDES: tuple[re.Pattern[str], ...] = (
    lazy_compile(rf"^{_EACH_LEAD}\s+(?P<a>{_EACH_NAME})\s+and\s+(?P<b>{_EACH_NAME})[?.!]*$", re.I),
    lazy_compile(rf"^(?:(?:is|are|was|were|does|do|did)\s+)?(?P<a>.+?)(?<!\s)\s+(?:(?:is|are|was|were)\s+)?(?:{_MORE}) than (?P<b>.+?)[?.!]*$", re.I),
    lazy_compile(r"^(?:how|what) (?:does|do|did) (?P<a>.+?) (?:compare|stack up|measure up) (?:with|to|against) (?P<b>.+?)[?.!]*$", re.I),
    #: The composer's own lead, said back: "Among these notes, one mentions Lisbon and one mentions Atlas" (W10 B30).
    lazy_compile(rf"^(?:[^,]{{3,40}},\s*)?{_COUNT_MENTIONS}\s+(?P<a>.+?)(?:,|\s+and)\s+(?:and\s+)?{_COUNT_MENTIONS}\s+(?P<b>.+?)[?.!]*$", re.I),
    lazy_compile(r"^(?P<a>.+?),? compare[sd]? (?:with|to) (?P<b>.+?)[?.!]*$", re.I),
    lazy_compile(rf"^{_WHICH} (?:is|are|was|were) (?:the )?(?:{_MORE})[,:]?\s+(?P<a>.+?) or (?P<b>.+?)[?.!]*$", re.I),
    #: "which of alpha, beta and gamma is the newest": the names between "of" and the verb (L105).
    lazy_compile(rf"^which(?: one)? of (?:the |my )?(?P<a>.+?),? (?:or|and) (?P<b>.+?) (?:is|are|was|were|comes?|came) (?:the )?(?:{_MORE}|earliest|latest|first|last)[?.!]*$", re.I),
    #: "which comes first, the dentist or the trip".
    lazy_compile(r"^which(?: one)? (?:comes|came|is|was) first[,:]?\s+(?P<a>.+?) or (?P<b>.+?)[?.!]*$", re.I),
    #: The same asked the other way round: "Lisbon or Tokyo, which is cheaper" (audit 1030 Z58).
    lazy_compile(rf"^(?P<a>[\w' ,-]+?) or (?P<b>[\w' ,-]+?),? {_WHICH} (?:is|are|was|were) (?:the )?(?:{_MORE})[?.!]*$", re.I),
    #: "which costs more, Lisbon or Tokyo" and the other way round (round 2 E9).
    lazy_compile(r"^which(?: one| note)? costs? (?:more|less)[,:]?\s+(?P<a>.+?) or (?P<b>.+?)[?.!]*$", re.I),
    lazy_compile(r"^(?P<a>[\w' ,-]+?) or (?P<b>[\w' ,-]+?),? which(?: one| note)? costs? (?:more|less)[?.!]*$", re.I),
    #: "Lisbon or Atlas which", "Lisbon or Atlas, which one": two names and a bare which (D3).
    lazy_compile(r"^(?P<a>[\w' -]{1,40}?) or (?P<b>[\w' -]{1,40}?),?\s+which(?: one| is| of them| note)?(?: \w+){0,3}[?.!]*$", re.I),
    lazy_compile(r"^(?:(?:what are|what is) )?(?:the )?(?:pros and cons|advantages and disadvantages|upsides and downsides|pros|cons) of (?P<a>.+?) (?:and|or|vs\.?|versus) (?P<b>.+?)[?.!]*$", re.I),
    lazy_compile(r"^(?:how|what) (?:is|are) (?P<a>.+?) (?:different|difference|differs?) from (?P<b>.+?)[?.!]*$", re.I),
    lazy_compile(r"^(?P<a>.+?) (?:differs?|is different|is a difference) from (?P<b>.+?)[?.!]*$", re.I),
    lazy_compile(r"^(?:the )?comparison (?:of|between) (?P<a>.+?) (?:and|with|to|vs\.?|versus) (?P<b>.+?)[?.!]*$", re.I),
    lazy_compile(r"\b(?:similarities|contrast) between (?P<a>.+?) and (?P<b>.+?)[?.!]*$", re.I),
    #: "how are Deep Work and The Overstory different" (audit 1029 C36).
    lazy_compile(r"^(?:how|in what ways?) (?:are|were|do|did) (?P<a>.+?) and (?P<b>.+?) (?:different|differ|alike|similar|the same)[?.!]*$", re.I),
    #: "what changed between the old plan and the new one", "what is different between A and B" (audit 1031 C24).
    lazy_compile(r"^what(?:'s| is| has| have)? (?:changed|different|the change|the changes) between (?P<a>.+?) and (?P<b>.+?)[?.!]*$", re.I),
)

#: The comparison triggers added to the "compare" shape rule: all two-sided,
#: so a question with one subject is never read as a comparison.
COMPARE_SHAPE_EXTRA = (
    rf"^(?:[^,]{{3,40}},\s*)?{_COUNT_MENTIONS}\s+.+?(?:,|\s+and)\s+(?:and\s+)?{_COUNT_MENTIONS}\s+|"
    #: Loose on purpose: `compare_sides` (case-sensitive, names only) is the gate for a bare "Tom and Sara".
    r"^[\w'’, -]{3,60} and [\w'’ -]{2,30}[?.!]*$|"
    rf"^{_EACH_LEAD}\s+{_EACH_NAME}\s+and\s+{_EACH_NAME}[?.!]*$|"
    r"^[\w' -]{1,40}? or [\w' -]{1,40}?,?\s+which\b|"
    r"^which(?: one)? (?:comes|came|is|was) first\b.+? or |"
    rf"^which(?: one)? of .+? (?:or|and) .+? (?:is|are|was|were|comes?|came) (?:the )?(?:{_MORE}|earliest|latest|first|last)\W*$|"
    r"^which(?: one| note)? costs? (?:more|less)\b.+? or |^[\w' ,-]+? or [\w' ,-]+?,? which(?: one| note)? costs? (?:more|less)\W*$|"
    rf"\b(?:{_MORE}) than\b|\bcompare[sd]? (?:with|to)\b|\b(?:pros and cons|advantages and disadvantages) of .+? (?:and|or|vs\.?|versus) |"
    rf"^{_WHICH} (?:is|are|was|were) (?:the )?(?:{_MORE})\b.+? or |^[\w' ,-]+? or [\w' ,-]+?,? {_WHICH} (?:is|are|was|were) (?:the )?(?:{_MORE})\W*$|\b(?:differs?|different|difference) from\b|\bcomparison (?:of|between)\b|"
    r"\b(?:similarities|contrast) between\b|\bstack up against\b|\bmeasure up (?:to|against)\b|"
    r"^(?:how|in what ways?) (?:are|were|do|did) .+? and .+? (?:different|differ|alike|similar|the same)\W*$|"
    r"^what(?:'s| is| has| have)? (?:changed|different|the change|the changes) between .+? and "
)

#: Comparison words are asking words: dropped from the subject, so "is Lisbon
#: cheaper than Porto" is about Lisbon and Porto and is never told no note
#: mentions "cheaper".
EXTRA_ASKING_WORDS = frozenset(
    """compared comparison versus better worse cheaper faster slower bigger smaller larger longer shorter
    easier harder safer pros cons advantages disadvantages drawbacks upsides downsides differ differs
    different than similarities contrast sooner soonest later pricier costlier dearer cheapest older oldest newer nearer closer""".split()
)

# --- wrappers, trailers and contractions ------------------------------------------

#: More of the wrappers a casual, indirect or formal question comes in, each a
#: pattern for `composer._WRAPPERS` (taken off before the question is read).
EXTRA_WRAPPERS: tuple[str, ...] = (
    r"^(?:could|would|can|will) you (?:kindly |please )?(?:advise|inform|clarify|confirm|help me understand|explain to me|point me to)\s+",
    r"^(?:would|do) you (?:mind|happen to) (?:telling|tell|know|knowing|checking|check|looking up|look up|reminding|remind)\s+(?:me\s+)?",
    r"^i(?:'m| am)? (?:just )?(?:curious|wondering|trying to (?:find out|remember|work out|recall)|hoping you can tell me)\s+(?:about\s+)?",
    r"^i(?:'d| would)? (?:really )?(?:like|love) to (?:know|find out|see|check|confirm)\s+",
    r"^i(?:'d| would)? (?:really )?(?:like|love) (?:you )?to (?:tell me|remind me|show me)\s+",
    r"^(?:out of curiosity|just checking|just to check|just to confirm|just to be sure|for reference|for the record)\b[,:]?\s+",
    r"^(?:may|can|could) i (?:ask|check|confirm|know)\s+",
    r"^is it possible to (?:find out|know|check|see|tell)\s+",
    r"^(?:i )?(?:need|want|have) (?:to )?(?:find out|check|confirm|verify|look up|know)\s+",
    r"^i(?:'m| am| was)? (?:just )?(?:hoping|wondering|thinking) (?:that )?(?:you|if you)(?:'d| would| could| can)? (?:could |can |would )?(?:tell|remind|show|let) me\s+(?:about\s+)?",
    r"^to (?:find out|check|confirm|verify|know|see|remember|recall|look up)\s+(?=(?:what|when|where|who|why|how|which|if|whether)\b)",
    r"^(?:kindly|please kindly|would you be so kind as to)\s+(?:tell|remind|show|let) me\s+",
    r"^(?:could|would|can) you (?:quickly |just )?(?:look|search|dig) (?:up|for|through)\s+",
    r"^(?:do|did) (?:i|we) (?:ever )?(?:note|write|record|mention|jot|save) (?:down )?(?:anything )?(?:about|on)\s+",
    r"^(?:anyone|somebody|someone) (?:know|remember)\s+",
    r"^(?:one more thing|another thing|and finally|finally|lastly|last one|one last thing)\b[,:]?\s+",
    r"^(?:oh and|oh,|also,|and also|and then)\s+(?=\w)",
    r"^(?:sorry|apologies|excuse me|pardon me)\b[,.:]?\s+(?=(?:but |can |could |what |when |where |who |why |how |is |are |do |does |did )\w)",
    r"^(?:hm+|erm+|so then|right then|okay then|ok then|alright then|all right then)\b[,.:]?\s+",
    r"^well[,.:]\s+",
    r"^(?:you know (?:what|that)|guess what|listen)\b[,.:]?\s+",
    r"^(?:good (?:morning|afternoon|evening)|morning|evening)\b[,.:]?\s+(?=\w{3,})(?=(?:what|when|where|who|why|how|is|are|do|does|did|can|could)\b)",
    r"^(?:in your notes|from my notes|in my notes|according to my notes|from your notes)\b[,:]?\s+",
    r"^(?:for me|for my records)\b[,:]?\s+",
    r"^(?:hello|hi|hey|dear (?:assistant|atlas|notebook))\b[,.:]?\s+(?=\w)",
)

#: Closing phrases dropped after the question ("... if you can", "... thank you
#: in advance"): joined into the `_TRAILERS` pattern.
EXTRA_TRAILERS: tuple[str, ...] = (
    "if you can", "if possible", "if you could", "when you get a chance", "thanks in advance", "thank you in advance",
    "at your convenience", "kindly", "if that is ok", "if that's ok", "if you do not mind", "if you don't mind",
    "much appreciated", "appreciate it",
    "when you can", "whenever you can", "no rush", "no hurry", "just curious", "out of curiosity", "for reference",
    "for the record", "thanks a lot", "many thanks", "thanks so much",
)

#: "what'd", "where're" and the rest: (pattern, replacement) pairs for
#: `composer._CONTRACTIONS`.
EXTRA_CONTRACTIONS: tuple[tuple[str, str], ...] = (
    (r"^(what|how|where|when|who|why)(?:'d)\b", r"\1 did"),
    (r"^(what|how|where|when|who|why)(?:'ll)\b", r"\1 will"),
    (r"^(what|how|where|when|who|why)(?:'ve)\b", r"\1 have"),
    (r"^(?:whadda|whaddya)\b", "what do you"),
    (r"^howd\b", "how did"),
    (r"^whered\b", "where did"),
    (r"^whend\b", "when did"),
    (r"^whod\b", "who did"),
    (r"^whatd\b", "what did"),
)

# --- lead-ins ------------------------------------------------------------------------

#: More filler a note opens with, taken off with the comma or colon after it
#: (`composer.LEAD_INS`).
EXTRA_LEAD_INS: tuple[str, ...] = (
    "just a thought", "quick thought", "thought", "fyi to self", "heads up", "for the record", "for reference",
    "in short", "in summary", "to summarise", "to summarize", "in other words", "as noted", "as discussed",
    "as mentioned", "as promised", "as usual", "as always", "in brief", "side note", "small note", "a note",
    "one more thing", "another thing", "actually", "anyways", "alright", "all right", "yeah", "hmm", "so yeah",
    "ok so then", "right then", "okay then", "update to self",
)

# --- small talk ---------------------------------------------------------------------

#: More natural lines per kind of turn, appended to `composer.SOCIAL`.
SOCIAL_NATURAL_EXTRA: dict[str, tuple[str, ...]] = {
    "morning": (
        "Good morning. What would you like to check first?",
        "Morning. Ask me about anything you wrote down.",
        "Good morning. Your notes are all here.",
    ),
    "how": (
        "Good, thanks. What would you like to find?",
        "All well here. Anything you want to check in your notes?",
        "Doing fine. What can I look up for you?",
    ),
    "sorry": (
        "That is fine. What would you like to look up?",
        "No harm done. Ask it again and I will have another look.",
        "Nothing to apologise for. What next?",
    ),
    "laugh": (
        "Ha, good. What would you like to find next?",
        "Glad that landed. Anything else to look up?",
        "Nice. Ask me whenever you are ready.",
    ),
    "reaction": (
        "Right. Want me to look anything up about it?",
        "Fair enough. Shall I find something else?",
        "I hear you. What next?",
    ),
    "confused": (
        "Sorry about that. Try asking it in different words, or name the note you mean.",
        "That was unclear. Say it another way and I will look again.",
        "Let me try again. Which part would you like me to look at?",
    ),
    "ack": (
        "Sure. Ask when you are ready.",
        "Understood. What next?",
        "Right. Anything else to look up?",
    ),
}

#: The professional voice's lines, one tuple per kind. Same kinds as `SOCIAL`.
SOCIAL_PROFESSIONAL: dict[str, tuple[str, ...]] = {
    "morning": (
        "Good morning. What would you like to review?",
        "Good morning. Your notes are available whenever you are ready.",
        "Good morning. How may I assist?",
    ),
    "how": (
        "Well, thank you. How may I help with your notes?",
        "Very well, thank you. What would you like to look up?",
        "I am well. What would you like to find in your notes?",
    ),
    "sorry": (
        "There is no need to apologise. How may I help?",
        "No problem. Please rephrase the question and I will look again.",
        "That is quite all right. What would you like to look up?",
    ),
    "laugh": (
        "Glad to hear it. Is there anything else you would like to review?",
        "Understood. How may I help next?",
        "Very good. Please ask whenever you are ready.",
    ),
    "reaction": (
        "Understood. Would you like me to look up anything related?",
        "Noted. Is there anything else you would like to review?",
        "Of course. How may I help next?",
    ),
    "confused": (
        "My apologies, that was unclear. Please rephrase the question, or name the note you mean.",
        "I may have missed the point. Which part would you like me to review again?",
        "Let me try again. Could you put the question in other words?",
    ),
    "ack": (
        "Understood. Is there anything else?",
        "Noted. Please ask whenever you are ready.",
        "Very good. What would you like to review next?",
    ),
    #: The engine is Atlas's assistant (CHAT_PLAN decision 36, amended 2026-10-17), in both voices.
    "who": (
        "I am Atlas's assistant. Without a model running, I answer from your notes in their own words.",
        "This is Atlas's assistant. It locates entries in your notes and reports what they say.",
    ),
    "joke": (
        "I do not compose jokes; I report what your notes contain. If you recorded one, ask for it.",
        "Humour is outside what I do. A joke saved in your notes can be found on request.",
    ),
    "unclear": (
        "That message could not be read. Please ask about a note, a date or a list, or state the action needed.",
        "The message was not recognised as words. What should be located?",
    ),
    "about_app": (
        "I am Atlas. I answer from your notes: dates, decisions and the status of a project. I also set reminders and "
        "tag, move or pin notes on request. Connecting a model adds writing and summaries.",
        "Atlas answers from what you have recorded: a date, a decision, a list or the status of a project, and acts on "
        "request (reminders, tags, pins). Connecting a model adds writing and tools.",
    ),
}

#: Next steps offered after an acknowledgement, each with a "{subject}" slot.
NEXT_STEPS_EXTRA: tuple[str, ...] = (
    "Ask for more on “{subject}” if you like.",
    "I can look up the latest on “{subject}” if you want.",
    "Say “what else” and I will look further into “{subject}”.",
    "Want to know when you last wrote about “{subject}”?",
    "I can pull out the dates for “{subject}” as well.",
    "Say “more” for the rest of what your notes say on “{subject}”.",
)
NEXT_STEPS_PROFESSIONAL: tuple[str, ...] = (
    "I can provide further detail on “{subject}” if required.",
    "Say “tell me more” for additional detail on “{subject}”.",
    "I can also retrieve the latest entry on “{subject}”.",
    "Please ask if you would like the dates recorded for “{subject}”.",
    "I can review the remaining entries on “{subject}” on request.",
    "Would you like the most recent update on “{subject}”?",
)


# --- Added 2026-10-10 from the Gemini branch, filtered as `_FAMILIES_ADDED` is. ---

EXTRA_SYNONYM_GROUPS = EXTRA_SYNONYM_GROUPS + tuple(tuple(g) for g in [['laptop', 'computer', 'pc', 'mac', 'macbook'],
 ['phone', 'mobile', 'cell', 'smartphone', 'iphone', 'android'],
 ['app', 'application', 'software', 'program', 'tool'],
 ['website', 'site', 'webpage', 'portal', 'url'],
 ['password', 'passcode', 'pin', 'code', 'credential', 'credentials'],
 ['wifi', 'internet', 'connection', 'network', 'broadband'],
 ['message', 'text', 'sms', 'chat', 'dm'],
 ['airport', 'terminal', 'gate'],
 ['laundry', 'washing', 'clothes', 'dry cleaning'],
 ['coffee', 'tea', 'drink', 'beverage', 'caffeine'],
 ['concert', 'gig', 'performance'],
 ['sell', 'vend', 'trade', 'auction'],
 ['make', 'create', 'build', 'construct', 'produce'],
 ['find', 'locate', 'discover', 'search', 'seek'],
 ['stop', 'halt', 'end', 'terminate'],
 ['question', 'query', 'inquiry'],
 ['opinion', 'view', 'perspective', 'stance', 'thoughts', 'belief', 'take', 'hot take'],
 ['music', 'song', 'track', 'tune', 'audio', 'album', 'playlist', 'record'],
 ['game', 'videogame', 'sport', 'match', 'play', 'gaming', 'boardgame'],
 ['disease', 'illness', 'sickness', 'condition', 'infection', 'virus', 'syndrome'],
 ['pet', 'dog', 'cat', 'puppy', 'kitten', 'animal', 'bird', 'fish'],
 ['shoes', 'sneakers', 'boots', 'footwear', 'sandals', 'heels'],
 ['weather', 'climate', 'temperature', 'forecast', 'conditions'],
 ['rain', 'shower', 'storm', 'drizzle', 'precipitation'],
 ['sun', 'sunny', 'clear', 'sunshine', 'bright'],
 ['snow', 'blizzard', 'ice', 'winter', 'cold'],
 ['day', 'date', 'afternoon', 'morning', 'evening', 'night', 'today', 'tomorrow', 'yesterday'],
 ['week', 'weekend', 'weekday', 'fortnight'],
 ['big', 'large', 'huge', 'massive', 'giant', 'enormous', 'gigantic', 'substantial'],
 ['small', 'tiny', 'little', 'miniature', 'compact', 'micro', 'petite'],
 ['good', 'great', 'excellent', 'amazing', 'wonderful', 'fantastic', 'superb', 'awesome', 'perfect', 'ideal'],
 ['bad', 'terrible', 'awful', 'horrible', 'poor', 'inferior', 'dreadful', 'lousy'],
 ['important', 'crucial', 'essential', 'vital', 'significant', 'key', 'major', 'critical'],
 ['unimportant', 'trivial', 'minor', 'insignificant', 'marginal'],
 ['easy', 'simple', 'effortless', 'straightforward', 'basic', 'uncomplicated'],
 ['hard', 'difficult', 'tough', 'challenging', 'complex', 'complicated'],
 ['old', 'ancient', 'past', 'outdated', 'vintage', 'antique', 'obsolete'],
 ['right', 'correct', 'accurate', 'true', 'valid', 'exact'],
 ['success', 'victory', 'triumph', 'achievement', 'accomplishment'],
 ['failure', 'defeat', 'loss', 'disaster', 'flop'],
 ['agree', 'concur', 'consent', 'assent', 'approve'],
 ['disagree', 'differ', 'dissent', 'object', 'oppose', 'argue'],
 ['help', 'assist', 'support', 'aid', 'guide', 'advice', 'advise'],
 ['change', 'modify', 'alter', 'adjust', 'adapt', 'transform', 'update'],
 ['use', 'utilize', 'employ', 'apply', 'operate', 'consume']])

#: A concept word and the members a note may name instead: "sport" is a note that says only "swimming".
#: Read by `composer._fit_terms`, for scoring only (the answer never prints the member as if it were typed).
CONCEPTS: dict[str, tuple[str, ...]] = {
    "sport": ("swimming", "swam", "running", "ran", "football", "tennis", "cycling", "cycled", "gym", "yoga", "climbing", "hiking", "badminton", "rugby", "cricket", "golf"),
    "exercise": ("swimming", "swam", "running", "ran", "gym", "yoga", "cycling", "hiking", "climbing", "workout"),
    "gym": ("swimming", "swam", "running", "ran", "yoga", "workout", "lifting", "weights"),
    "food": ("dinner", "lunch", "breakfast", "recipe", "pasta", "pizza", "soup", "curry", "salad", "cooked", "restaurant"),
    "meal": ("dinner", "lunch", "breakfast", "supper", "brunch"),
    "travel": ("flight", "hotel", "airport", "train", "itinerary", "passport", "trip", "holiday"),
    "pet": ("dog", "cat", "puppy", "kitten", "hamster", "rabbit"),
    "drink": ("coffee", "tea", "wine", "beer", "juice", "water"),
    "music": ("guitar", "piano", "song", "album", "concert", "band", "playlist", "drums", "violin"),
    "money": ("rent", "salary", "budget", "savings", "invoice", "tax", "loan", "mortgage"),
    "health": ("doctor", "dentist", "medicine", "pills", "vaccine", "checkup", "physio", "prescription"),
    "family": ("mum", "dad", "sister", "brother", "aunt", "uncle", "cousin", "grandma", "grandad"),
    "transport": ("bus", "train", "tram", "taxi", "bike", "metro", "commute", "ferry"),
    "clothes": ("jacket", "shoes", "jeans", "shirt", "dress", "coat", "boots", "scarf"),
}

#: The verb a person asks with and the noun a note is written with ("when do I
#: fly" is the "Flight to Lisbon" note; audit 1029 C21). `fly` and `flight`,
#: `travel` and `trip`, `depart` and `departure`, `arrive` and `arrival`,
#: `exercise` and `workout` already sit in groups above (a word is in one
#: group only); the pairs below are the ones that did not.
VERB_NOUN_PAIRS: tuple[tuple[str, ...], ...] = (
    ("decide", "decision"),
    ("invite", "invitation"),
    ("marry", "marriage", "wedding"),
    ("graduate", "graduation"),
    ("retire", "retirement"),
    ("register", "registration", "enrol", "enrolment"),
    ("subscribe", "subscription"),
    ("submit", "submission"),
    ("deliver", "delivery"),
    ("renew", "renewal"),
    ("invest", "investment"),
    ("donate", "donation"),
    ("complain", "complaint"),
    ("vote", "ballot", "election"),
)
EXTRA_SYNONYM_GROUPS = EXTRA_SYNONYM_GROUPS + VERB_NOUN_PAIRS
EXTRA_ASKING_WORDS = EXTRA_ASKING_WORDS | frozenset(['af',
 'asf',
 'bestie',
 'bet',
 'cap',
 'deadass',
 'fr',
 'hella',
 'highkey',
 'lowkey',
 'ngl',
 'nocap',
 'ong',
 'period',
 'periodt',
 'sis',
 'sus',
 'tbh',
 'vibes'])
EXTRA_WRAPPERS = EXTRA_WRAPPERS + tuple([('^(?:quick question|i have a quick '
 'question)\\b[,.:]?\\s+(?=(?:what|when|where|who|why|how|is|are|do|does|did|can|could)\\b)'),
 '^(?:do you know|would you know)\\b[,.:]?\\s+(?=(?:what|when|where|who|why|how)\\b)',
 ("^(?:i )?(?:cant|cannot|can't) (?:remember|recall|think "
 'of)\\b[,.:]?\\s+(?=(?:what|when|where|who|why|how)\\b)'),
 '^(?:by any chance)\\b[,.:]?\\s+(?=(?:do|does|did|is|are|was|were|can|could)\\b)',
 '^(?:let me ask you|let me ask)\\b[,.:]?\\s+',
 "^(?:im not sure|i am not sure|i'm not sure)\\b[,.:]?\\s+(?=(?:if|whether|what|when|where|who|why|how)\\b)",
 ('^(?:can you|could you|would you) (?:help me (?:with|remember)|refresh my memory '
 '(?:on|about)?)\\b[,.:]?\\s+'),
 '^(?:hey )?(?:bot|ai|assistant|computer)[,.:]?\\s+',
 '^(?:tell me|remind me) (?:again )?\\b[,.:]?\\s+(?=(?:what|when|where|who|why|how)\\b)',
 '^(?:can you|could you) (?:check|find) (?:my notes|the notes) (?:for|on)?\\b[,.:]?\\s+',
 '^(?:what does it say|what do my notes say) (?:about|on|regarding)\\b\\s+',
 '^(?:pull up|bring up|search for) (?:my notes|the notes) (?:on|about)?\\b\\s+',
 '^(?:any idea|any clue)\\b\\s+(?=(?:what|when|where|who|why|how|if)\\b)',
 '^(?:i was wondering|i am wondering)\\b\\s+(?=(?:what|when|where|who|why|how|if)\\b)',
 '^(?:bro|bruh|broski|brotato|buddy|mate|dude|man)\\b[,.:]?\\s+',
 ('^(?:no cap|lowkey|highkey|tbh|ngl|fr|for real|deadass|bet|say less|say lesss|im dead|i am '
 'dead|omg|literally)\\b[,.:]?\\s+'),
 '^(?:so basically|like|i mean|bro|bruh|bruhh|dude|man|sis|bestie|besty|besties)\\b[,.:]?\\s+',
 "^(?:its giving|it\\'s giving|vibes|the vibes are)\\b\\s+",
 '^(?:sus|kinda sus|hella sus)\\b[,.:]?\\s+',
 '^(?:ok boomer|bruh moment)\\b[,.:]?\\s+'])
EXTRA_TRAILERS = EXTRA_TRAILERS + tuple(["if you wouldn't mind",
 'if you wouldnt mind',
 'please and thank you',
 'pls and ty',
 'pretty please',
 'when you have a sec',
 'when you have a second',
 'when you have a minute',
 'when you have time',
 "if it's not too much trouble",
 'if its not too much trouble',
 'if it is not too much trouble',
 "if it's easy",
 'if its easy',
 "if that's alright",
 'if that is alright',
 "i'd appreciate it",
 'id appreciate it',
 'i would appreciate it',
 'thank you',
 'thanks',
 'ty',
 'tysm',
 'just wondering',
 'just asking',
 'just so i know',
 'as soon as you can',
 "whenever you're ready",
 'whenever youre ready',
 "if you don't mind me asking",
 'if you do not mind me asking',
 'por favor',
 "if you'd be so kind",
 'if you would be so kind',
 "if you wouldn't mind looking",
 'if you wouldnt mind looking',
 'if you can find it',
 'if you could find it',
 'if you manage to find it',
 'bro',
 'bruh',
 'broski',
 'brotato',
 'buddy',
 'mate',
 'dude',
 'man',
 'my guy',
 'dog',
 'dawg',
 'no cap',
 'fr',
 'for real',
 'deadass',
 'bet',
 'say less',
 'say lesss',
 'ngl',
 'tbh',
 'lowkey',
 'highkey',
 'im dead',
 'literally',
 'omg',
 'bestie',
 'sis',
 'periodt',
 'period',
 'periodtt',
 'vibes',
 'sus',
 'hella',
 'af',
 'asf',
 'on god',
 'ong'])
EXTRA_LEAD_INS = EXTRA_LEAD_INS + tuple(['important note',
 'quick update',
 'just an update',
 'update',
 'memo to self',
 'note to self',
 'reminder',
 'just a reminder',
 'quick reminder',
 'brief note',
 'small reminder',
 'to recap',
 'recap',
 'tl;dr',
 'tldr',
 'long story short',
 'the bottom line is',
 'bottom line',
 'key takeaway',
 'takeaway',
 'in a nutshell',
 'simply put',
 'to cut a long story short',
 'by the way',
 'btw',
 'also',
 'and another thing',
 'moving on',
 'on a related note',
 'speaking of which',
 'incidentally',
 'as an aside',
 "for what it's worth",
 'fwiw',
 'to be honest',
 'tbh',
 'to be fair',
 'tbf',
 'not gonna lie',
 'ngl',
 'at the end of the day',
 'basically',
 'essentially',
 'fundamentally',
 'ultimately',
 'anyway',
 'anyhow',
 'regardless',
 'nevertheless',
 'that being said',
 'having said that',
 'on second thought',
 'wait',
 'hold on',
 'actually, scratch that',
 'scratch that',
 'so',
 'okay',
 'ok',
 'right',
 'sure',
 'listen',
 'look',
 'see',
 'guess what',
 'fun fact',
 'believe it or not',
 'you know what',
 'just to clarify',
 'to be clear',
 'for clarity',
 'let me clarify',
 'just making sure',
 'as expected',
 'no surprise',
 'unsurprisingly',
 'naturally',
 'obviously',
 'clearly'])
NEXT_STEPS_EXTRA = NEXT_STEPS_EXTRA + tuple(['Would you like me to find out more about “{subject}”?',
 'I can find more on “{subject}” if you need it.',
 'Let me know if you want the rest of the notes on “{subject}”.',
 'Should I keep looking for more on “{subject}”?',
 'There might be more on “{subject}”, want me to check?',
 "Say the word and I'll find more on “{subject}”.",
 "I'm happy to pull up more on “{subject}” if that helps.",
 'Want more detail on “{subject}”?',
 'Anything else on “{subject}”?',
 'There may be other mentions of “{subject}”, just say.',
 'Want to go further into “{subject}”?',
 'If you want, I can look for more details on “{subject}”.',
 'Want to see what else you wrote about “{subject}”?',
 'I can look further for “{subject}” if you like.',
 'Say “more” if you want to see other notes on “{subject}”.',
 "There's likely more on “{subject}” in your notes.",
 'I can check for more on “{subject}” any time.',
 'Let me know if you want me to expand on “{subject}”.',
 'Want everything you have on “{subject}”?',
 'Should I gather the rest on “{subject}”?',
 'Want to see the rest on “{subject}”?',
 'I can search again for “{subject}” if you want.',
 'Ask if you want to know more about “{subject}”.',
 'I can look further into “{subject}”.',
 "Want to see if there's any related info to “{subject}”?",
 'I can check for context around “{subject}” if you like.',
 'Want the other notes on “{subject}”?'])
NEXT_STEPS_PROFESSIONAL = NEXT_STEPS_PROFESSIONAL + tuple(['Would you like me to retrieve further information on “{subject}”?',
 'I can locate additional records regarding “{subject}” if required.',
 'Please advise if you need more details on “{subject}”.',
 'Should I continue searching the documentation for “{subject}”?',
 'There may be further entries on “{subject}”. Shall I proceed?',
 'I am available to extract more data on “{subject}”.',
 'Would you like a deeper analysis of the notes on “{subject}”?',
 'Please inform me if additional context on “{subject}” is necessary.',
 'I can review the files for other mentions of “{subject}”.',
 'Should we examine “{subject}” in greater detail?',
 'If required, I can provide more comprehensive notes on “{subject}”.',
 'Would you care to review further entries concerning “{subject}”?',
 'Please indicate if you wish me to expand on “{subject}”.',
 'I can retrieve all corresponding records for “{subject}”.',
 'Should I compile all remaining mentions of “{subject}”?',
 'Do you require further clarification regarding “{subject}”?',
 'I can execute an additional query for “{subject}” upon request.',
 'Please let me know if you seek further information about “{subject}”.',
 'I am prepared to continue investigating “{subject}”.',
 'Would it be beneficial to retrieve related data on “{subject}”?',
 'I can examine the surrounding context of “{subject}” if you prefer.',
 'Shall I present additional documentation on “{subject}”?'])
for _kind, _lines in {
 'morning': ['Good morning. Need to find anything today?'],
 'compliment': ['I try my best. Anything else to check?',
                "Thanks. Ask away when you're ready.",
                "That's very kind. What's next on the agenda?",
                'I appreciate it. Anything else I can find?',
                'Glad I could help. Want me to dig up anything else?',
                "You're too kind. What else can we find in your notes?",
                'Thank you. Ready for the next question whenever you are.'],
 'insult': ['Ouch, sorry about that. Try asking it another way?',
            "My bad. I'll try to do better. What should we look up?",
            "Sorry. Let's try again. What are we looking for?",
            'Sorry to let you down. How about we try searching another way?',
            "I'll take the hit. What should we look for instead?",
            "My apologies. Let's see if we can get it right this time."],
 'emotion': ['I hear you. Take your time. What can I help you find?',
             "Got it. I'm here when you're ready to check your notes.",
             "That's completely understandable. Let me know what you want to look up.",
             "I'm sorry to hear that. Whenever you're ready, I'm here.",
             'Take a breath. Let me know when you need to search for something.',
             "I understand. Let's focus on what we can find in your notes.",
             'It happens to the best of us. What can I look up for you?',
             "I've got you covered. What do you need from your notes?"],
 'how': ["I'm doing great, thanks for asking. What should we search for?",
         "Everything's running smoothly here. What's on your mind?",
         "I'm well. Let's dive into your notes.",
         'Doing good. Ready to find whatever you need.'],
 'sorry': ["It's all good. Let's try again.",
           "Don't worry about it. What can I find for you?",
           'No worries at all. What should we search for?',
           "It's fine, really. Let me know what you need.",
           "All good. Let's move on to the next search."],
 'laugh': ["Haha, right? Anyway, what's next?",
           "Glad you're amused. What should we look at now?",
           'Heh. Let me know if you need me to find anything else.',
           'Always good for a laugh. Ready for the next question?'],
 'reaction': ['Indeed. Anything else you want me to search?',
              'Totally. Want to check anything else?',
              'Yep. What else can I dig up?',
              'I know, right? What should we look for next?'],
 'confused': ["I didn't quite catch that. Could you phrase it differently?",
              "I'm a bit lost. Can you try asking in another way?",
              "I'm not sure I understand. Could you rephrase?"],
 'ack': ['Got it. What else?',
         'Okay. Let me know what you need.',
         'Acknowledged. Ready when you are.',
         'Alright. What should we look for now?'],
 'who': [("I'm your assistant for searching notes. Ask me a question and I'll find the answer in your "
         'records.')],
 'about_app': [("I'm designed to retrieve answers directly from your notes. Ask me anything you've recorded, "
               "and I'll find it.")]}.items():
    SOCIAL_NATURAL_EXTRA[_kind] = tuple(SOCIAL_NATURAL_EXTRA.get(_kind, ())) + tuple(_lines)
for _kind, _lines in {
 'morning': ['Good morning. What would you like to check first?',
             'Good morning. Need to find anything today?'],
 'compliment': ['Thank you. Is there anything else you would like to review?',
                'I appreciate the feedback. What would you like to review next?'],
 'insult': ['My apologies if the results were unhelpful. How may I improve the search?',
            'I will strive to do better. Please rephrase the question and I will look again.'],
 'emotion': ['Understood. How may I assist you with your notes?',
             'Noted. What would you like to review today?']}.items():
    SOCIAL_PROFESSIONAL[_kind] = tuple(SOCIAL_PROFESSIONAL.get(_kind, ())) + tuple(_lines)


# --- insights (CHAT_PLAN Phase 6, decision 32) -------------------------------------
#
# Each line a measurement with one fixed hedge, never a claim. Every slot is
# typed (`INSIGHT_SLOTS`): a count, a date, the subject asked about or tagged,
# or the person's own words; `tests/test_insights.py` holds the slots to it.

INSIGHT_TEMPLATES: dict[str, str] = {
    "recurrence": "{subject} has come up {count} times since {since}{after}; {hedge}.",
    "streak": "You have written about {subject} {weeks} weeks running.",
    "drift": "Since {since}, no later note picks up {plan}. It may still be open.",
    "contrast": "On {first} you wrote {before}; on {last}, {after_said}. You may have changed your mind.",
    "load": "The week of {week} had {count} notes against a usual {usual}; a busy week.",
    "time_of_day": "Of your {subject} notes, {count} of {total} say {when}.",
    "span": "You first wrote about {subject} on {first} and last on {last}, {count} notes in all.",
    "together": "Your notes about {subject} also name {other} in {count} of them.",
    "silence": "Nothing about {subject} since {last}.",
}
INSIGHT_HEDGES: dict[str, str] = {
    "hobby": "that may be a hobby forming",
    "recurs": "that keeps coming up",
}
#: What each slot may hold: "count" (a whole number the rule counted),
#: "date" (a day the notes were written), "subject" (the asked word or a tag),
#: "span" (a note's own words, a fact's text), "clause" (a fixed clause with a
#: count in it), "hedge" (one of `INSIGHT_HEDGES`).
INSIGHT_SLOTS: dict[str, str] = {
    "count": "count", "weeks": "count", "usual": "count",
    "since": "date", "first": "date", "last": "date", "week": "date",
    "subject": "subject", "plan": "span", "before": "span", "after_said": "span",
    "after": "clause", "hedge": "hedge", "total": "count", "other": "subject", "when": "word",
}

#: Who it is and what it does are said as Atlas's assistant (CHAT_PLAN decision 36,
#: `composer.SOCIAL`): the unnamed lines added for these two kinds are retired.
for _retired in ("who", "about_app"):
    SOCIAL_NATURAL_EXTRA.pop(_retired, None)


#: Words a note says by its shape rather than by name: "does Jake owe me
#: money" is answered by "$40", "what did I rate the ramen" by "8/10". A
#: quoted sentence of that shape (`recognise.says_shape`) means the word is
#: not missing (2026-10-30 sweep).
SHAPE_WORDS: dict[str, str] = {
    **dict.fromkeys(("money", "cost", "costs", "price", "paid", "pay", "spend", "spent", "amount", "cash"), "money"),
    **dict.fromkeys(("rate", "rated", "rating", "score", "scored", "stars", "mark"), "score"),
    **dict.fromkeys(("schedule", "timetable", "routine", "rota"), "schedule"),
    **dict.fromkeys(("temperature", "temperatures", "temp", "degrees", "oven", "hot", "heat"), "temperature"),
}


#: "alright, uhh, I think i wrote a note about eating my homework to smth, it was a joke" (INBOX 1705):
#: the lead-in and the trailing asides are not the subject, which is "eating my homework".
EXTRA_WRAPPERS = EXTRA_WRAPPERS + (
    r"^i (?:think|reckon|guess|believe|swear) (?:i|we) (?:wrote|made|saved|noted|put|jotted|have|had)(?: down)? (?:a |an |the |some )?(?:notes? |one |something )?(?:about|on|regarding)\s+",
)
EXTRA_TRAILERS = EXTRA_TRAILERS + (
    "it was a joke", "it was funny", "it was a funny one", "something like that", "or something", "to something",
)


def concepts(terms: list[str], vocabulary: set[str], stem) -> list[str]:
    """Each concept word no note holds ("sport") put to the first member, in the
    table's order, that a note does hold ("swimming"); any other word kept."""

    def member(term: str) -> str:
        if term in vocabulary:
            return ""
        return next((w for m in CONCEPTS.get(term, ()) for w in (m, stem(m)) if w in vocabulary), "")

    return [member(t) or t for t in terms]
