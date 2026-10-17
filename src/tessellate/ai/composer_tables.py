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

VOICES = ("natural", "professional")
DEFAULT_VOICE = "natural"


def voice_of(value: object) -> str:
    """`value` as a voice name: anything unknown is the default."""
    return value if value in VOICES else DEFAULT_VOICE


# --- phrase variants ---------------------------------------------------------------

#: canonical key -> {voice: [texts besides the canonical one]}. The canonical
#: text (`composer.PHRASES[key]`) is the first natural variant.
_FAMILIES: dict[str, dict[str, list[str]]] = {
    # Openers: said before the strongest sentence, which is the answer.
    "open_notes": {
        "natural": ["Here is what your notes say: ", "Your notes say: ", "Looking through your notes: ", "Here is what I found in your notes: ", "What your notes have: "],
        "professional": ["According to your notes: ", "Your notes record the following: ", "Per your notes: ", "The relevant entry in your notes reads: ", "Your records show: ", "From the notes on file: "],
    },
    "open_wrote": {
        "natural": ["This is what you wrote: ", "You wrote: ", "Here is how you put it: ", "Your own words: "],
        "professional": ["You recorded the following: ", "As you wrote it: ", "In your own words: ", "The entry reads: ", "Your entry states: "],
    },
    "open_put": {
        "natural": ["Here is how your notes put it: ", "This is how you put it: ", "Your notes word it like this: ", "In your notes it reads: "],
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
        "natural": ["Changing tack", "Moving on", "On a different note"],
        "professional": ["Turning to another matter", "On a different matter", "As for a different entry"],
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
        "professional": ["Previously, on ", "At an earlier date, on ", "Prior to this, on "],
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
        "professional": ["In chronological order:", "Listed chronologically:", "In order of entry:"],
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
    "ov_also": "Also",
    "ov_reads": ", reading ",
    "ov_next_who": "Who is ",
}
#: The canonical `wrote_on_b` pairs with the canonical `wrote_on_a`.
PAIRED = {
    "wrote_on_b": "wrote_on_a", "mention_mid": "mention_lead", "summary_mid": "summary_lead",
    "ov_lead_b": "ov_lead_a", "ov_span_b": "ov_span_a", "ov_who_end": "ov_who_mid",
    "ov_shared_end": "ov_shared_mid", "ov_more_b": "ov_more_a",
}


#: Variants added on 2026-10-10 from the Gemini branch, filtered: no filler
#: openers ("Ah,", "Hm,", "Let's see..."; the owner: "I think a lot of
#: composer responses start with 'ah,'"), no exclamation marks, no "closest
#: match" (INBOX 724), no two strings glued by a missing comma, and only a
#: variant whose ending matches its family's (a family ending ": " is followed
#: straight by the quote). The dropped ones are listed in the triage notes.
_FAMILIES_ADDED: dict[str, dict[str, list[str]]] = {'open_notes': {'natural': ['From your notes: ',
                            'According to your notes: ',
                            'Looking at your notes: ',
                            "Based on what you've saved: ",
                            "Here's what I found in your notebook: ",
                            'Checking your entries: ',
                            "From what you've written: ",
                            'Your notes have this to say: ',
                            'Gathering from your records: ',
                            'Based on your notebook: ',
                            'Diving into your notes: ',
                            'Scanning through your notes: ',
                            'Here is what your records show: '],
                'professional': ['A review of your records indicates: ',
                                 'The documentation shows: ',
                                 'As documented in your notes: ',
                                 'Based on the available records: ',
                                 'Referencing your entries: ']},
 'open_wrote': {'natural': ['Here is what you wrote: ',
                            'You wrote this: ',
                            'This is what you saved: ',
                            "Here's what you noted down: ",
                            'You previously noted: ',
                            'You captured this: ',
                            'Here is your exact note: ',
                            'This was your thought: ',
                            'You documented this: '],
                'professional': ['The exact phrasing in your records is: ',
                                 'Your documentation notes: ',
                                 'The record indicates: ']},
 'open_put': {'natural': ["This is how it's phrased: ",
                          'Your notes put it this way: ',
                          'Here is the phrasing you used: ',
                          'This is exactly how it is noted: ',
                          'The notes express it as: '],
              'professional': ['It is expressed in the records as: ',
                               'The formal entry states: ',
                               'The phrasing recorded is: ']},
 'open_figure': {'natural': ["Here's the amount you jotted down: ",
                             'The number you saved: ',
                             'I found this figure: ',
                             'This is the exact amount in your notes: ',
                             "Here's the number: "],
                 'professional': ['The recorded value is: ',
                                  'According to the entry, the figure is: ',
                                  'The stated numerical value is: ',
                                  'The specific amount noted is: ']},
 'open_date': {'natural': ["Here's the exact date: ",
                           'This is the day you saved: ',
                           'The day noted down: ',
                           'I found this date: ',
                           'This is the time you mentioned: '],
               'professional': ['The specified date is: ',
                                'The scheduled date recorded is: ',
                                'The timestamp noted is: ',
                                'As dated in the records: ']},
 'open_where': {'natural': ["Here's the location you saved: ",
                            'The spot mentioned in your notes: ',
                            'This is the location: ',
                            'I found this place: ',
                            'The whereabouts noted: '],
                'professional': ['The address specified in the entry is: ',
                                 'The site documented is: ',
                                 'The recorded whereabouts are: ',
                                 'According to the entry, the location is: ']},
 'closest_a': {'natural': ['The closest your notes come is this: ',
                           'Here is the nearest mention: ',
                           'The closest thing to that is: ',
                           "Here's the best match from your notes: ",
                           'This seems to be the closest record: ',
                           'The most relevant entry is this: ',
                           'The nearest hit I could find is: '],
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
                          'If we look at your notes',
                          'Drawing from your entries',
                          'Judging by your notebook',
                          'From what is written here',
                          'According to your entries',
                          'Relying on your notes',
                          'Based on what I found'],
              'professional': ['As indicated by the records',
                               'Based on the documentation',
                               'According to the available entries',
                               'As documented',
                               'In light of the recorded notes']},
 'notes_have': {'natural': ['Here is what your notes say on that: ',
                            'This is what you have saved: ',
                            "Here's what your records show: ",
                            'Your notes capture this: ',
                            'Here is the relevant information: ',
                            'This is what I found on that: ',
                            "Here's the data you saved: ",
                            'Your entries state the following: '],
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
                        'Furthermore',
                        'Additionally',
                        'On a similar note',
                        'Adding to that'],
            'professional': ['As a supplementary point',
                             'Coupled with this',
                             'Building on this',
                             'Additionally',
                             'In conjunction with this',
                             'Furthermore',
                             'In addition',
                             'Supplementary to this']},
 'separately': {'natural': ['Separately',
                            'Elsewhere',
                            'In another place',
                            'In a different note',
                            'On another topic',
                            'Changing gears',
                            'Meanwhile',
                            'In a totally different entry',
                            'Pivoting slightly',
                            'Shifting focus',
                            'In unrelated notes',
                            'Off to the side',
                            'On a different track'],
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
                           'Across your other entries',
                           'In a different spot',
                           'Looking somewhere else',
                           'In another corner of your notebook',
                           'Somewhere else entirely',
                           'In another part of your records',
                           'Looking at other entries',
                           'In completely different notes'],
               'professional': ['In another location',
                                'Documented elsewhere',
                                'In a distinct file',
                                'In a different section of the records']},
 'another_note': {'natural': ['On another note',
                              'In another entry',
                              'From a different note',
                              'Looking at a separate note',
                              'Switching to another note',
                              'In a completely different entry',
                              'According to another record',
                              'Turning to another note',
                              'As captured in another note'],
                  'professional': ['Addressing a distinct topic',
                                   'Transitioning to a separate point',
                                   'With regard to another note',
                                   'In reference to a separate entry',
                                   'Shifting focus to another record']},
 'later_on': {'natural': ['Later, on ',
                          'Further down the line on ',
                          'Sometime after, on ',
                          'Then, on ',
                          'Following that, on ',
                          'Subsequent to that, on ',
                          'Eventually, on ',
                          'A bit later, on ',
                          'Moving forward to ',
                          'Fast forward to ',
                          'As time passed, on ',
                          'Later down the road on '],
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
                         'Subsequently on ',
                         'And then on ',
                         'Which brings us to ',
                         'The next entry on ',
                         'The next record on ',
                         'Continuing on '],
             'professional': ['In the following record, dated ',
                              'Subsequently, on ',
                              'The subsequent entry on ',
                              'Continuing on ',
                              'In due course, on ']},
 'earlier_on': {'natural': ['Earlier, on ',
                            'Before that, on ',
                            'Prior to this, on ',
                            'Looking back, on ',
                            'Going back in time to ',
                            'Previously, on ',
                            'In a prior entry on ',
                            'Tracing back to ',
                            'Way back on ',
                            'Earlier in your notes on ',
                            'Before all this, on '],
                'professional': ['In a preceding entry, dated ',
                                 'Earlier in the timeline, on ',
                                 'Historically, on ',
                                 'Dating back to ',
                                 'In a prior record, on ']},
 'and_on': {'natural': ['Another one on ',
                        "There's also this on ",
                        'And here is another on ',
                        'As well as on ',
                        'Not forgetting this from '],
            'professional': ['A further entry on ',
                             'Also recorded on ',
                             'Moreover, on ',
                             'Supplementary to this, on ']},
 'before_that': {'natural': ['Before that, on ',
                             'Beforehand, on ',
                             'Stepping back further to ',
                             'Preceding that, on ',
                             'Long before that, on ',
                             'Going even further back to '],
                 'professional': ['In a prior instance, dated ',
                                  'Chronologically prior, on ',
                                  'In the preceding entry on ']},
 'latest_a': {'natural': ['The very latest from ',
                          'Right at the end, on ',
                          'The newest update on ',
                          'Bringing it up to date on ',
                          'Most recently, on '],
              'professional': ['The final record, dated ',
                               'Concluding the timeline on ',
                               'The ultimate entry on ',
                               'The latest available data, as of ',
                               'Updating to the most recent record on ']},
 'latest_b': {'natural': ['The most recent update, from ',
                          'The absolute newest, from ',
                          'Bringing us to the present, from ',
                          'The latest word, from '],
              'professional': ['The most current record, originating from ',
                               'The concluding note, dated ',
                               'The definitive recent entry, from ',
                               'The latest documentation from ']},
 'latest_c': {'natural': ['As of ', 'Where things left off on '],
              'professional': ['As of the record dated ']},
 'latest_undated': {'natural': ['The freshest note: ',
                                'The most recent update: ',
                                'Here is the latest: ',
                                'The newest thing saved: ',
                                'The most current note: '],
                    'professional': ['The most current record: ',
                                     'The final documented point: ',
                                     'The most recent update available: ',
                                     'The latest recorded observation: ']},
 'of_found': {'natural': ['Out of the notes I looked at, ',
                          'From the notes I could find, ',
                          'Of the ones retrieved, ',
                          'Taking these notes, ',
                          'Looking through this batch, ',
                          'Of the relevant notes, '],
              'professional': ['From the compiled entries, ',
                               'Reviewing the retrieved documentation, ',
                               'Of the pertinent records, ',
                               'Considering the recovered entries, ',
                               'Within the retrieved entries, ',
                               'Based on the entries found, ',
                               'Among the matching entries, ',
                               'Per the entries retrieved, ']},
 'across_found': {'natural': ['If we look at all these notes, ',
                              'Across the board in these notes, ',
                              'Combining what I found, ',
                              'Taking everything retrieved into account, ',
                              'In summary of the found notes, ',
                              'Across all the results, '],
                  'professional': ['Aggregating the retrieved records, ',
                                   'Consolidating the data from the entries, ',
                                   'In aggregate, the documentation shows ',
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
 'disagree_check': {'natural': [' Since they differ, you might want to see which is correct.',
                                " It's worth verifying which one is right since they conflict.",
                                ' Because of this mismatch, you should check the latest status.',
                                ' You might want to double-check this discrepancy.',
                                ' Take a look to see which one still applies.'],
                    'professional': [(' Due to this discrepancy, verification of the current status is '
                                     'recommended.'),
                                     ' It is prudent to cross-reference these entries for accuracy.',
                                     ' Resolution of this inconsistency is advised.',
                                     ' Please verify the correct information, given the discrepancy.',
                                     ' Confirmation of the accurate record is recommended.']},
 'timeline': {'natural': ['In the order you wrote them:',
                          'Arranged chronologically:',
                          'Here is the timeline:',
                          'Looking at them in order:',
                          'Tracing the sequence of events:',
                          'In chronological order:',
                          'Following the timeline:',
                          'From oldest to newest:'],
              'professional': ['Presented in chronological sequence:',
                               'Ordered by date of entry:',
                               'Sequenced chronologically:',
                               'Following the timeline of records:',
                               'Listed from earliest to latest:']},
 'each_side': {'natural': ['Here is what each says.',
                           "Let's look at both sides.",
                           'Here is the breakdown of each.',
                           "Here's what you wrote for each.",
                           'This is the information for both sides.'],
               'professional': ['Details for each are provided below.',
                                'The respective entries are as follows.',
                                'Information pertaining to each follows.',
                                'The documentation for both is detailed below.',
                                'A breakdown of each is presented.']},
 'side_none': {'natural': ["I didn't find anything specifically on this.",
                           "There's no standalone note for this one.",
                           "This one doesn't have its own specific mention.",
                           'Nothing focuses solely on this.',
                           'I have nothing on just this one alone.',
                           "There isn't a note isolated to this."],
               'professional': ['There is no isolated documentation for this subject.',
                                'No specific record pertains solely to this.',
                                'An exclusive entry for this was not retrieved.',
                                'The records lack a standalone mention of this.',
                                'No independent documentation is available for this.',
                                'This topic lacks an isolated entry in the records.']},
 'both': {'natural': ['Combining both',
                      'Looking at the two together',
                      'Taking both into account',
                      'For both combined',
                      'Together',
                      'Both sides considered'],
          'professional': ['In combination', 'Evaluating both simultaneously', 'Considered jointly']},
 'missing': {'natural': ['None of these notes mention ',
                         'These notes do not talk about ',
                         "I couldn't find any reference to ",
                         'There is nothing in these notes regarding ',
                         'No note found brings up ',
                         "I don't see any mention of ",
                         'It looks like these notes omit ',
                         'None of these records discuss '],
             'professional': ['The retrieved documentation lacks any reference to ',
                              'There is no recorded information regarding ',
                              'The entries omit any discussion of ',
                              'The provided records do not address ',
                              'An absence of documentation was noted for ']},
 'nothing': {'natural': [], 'professional': []}}
_PAIRS_ADDED: dict[str, dict[str, list[str]]] = {}
#: Nothing found, eight ways a voice (the owner: "can it have more varied
#: responses??"); the families start empty here and take their lines whole.
for _key in composer_replies.NOTHING_FAMILIES:
    _FAMILIES.setdefault(_key, {"natural": [], "professional": []})
for _table, _added in ((_FAMILIES, _FAMILIES_ADDED), (_PAIRS, _PAIRS_ADDED), (_FAMILIES, composer_replies.NOTHING_FAMILIES)):
    for _key, _by_voice in _added.items():
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
    ("party", "celebration", "gathering", "get-together"),
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
    "nicer|quicker|lighter|heavier|(?:more|less) [a-z]+")
)

#: Two-sided comparison patterns, tried after the originals in
#: `composer._COMPARE_SIDES`: each needs both sides in the question.
EXTRA_COMPARE_SIDES: tuple[re.Pattern[str], ...] = (
    re.compile(rf"^(?:(?:is|are|was|were|does|do|did)\s+)?(?P<a>.+?)\s+(?:(?:is|are|was|were)\s+)?(?:{_MORE}) than (?P<b>.+?)[?.!]*$", re.I),
    re.compile(r"^(?:how|what) (?:does|do|did) (?P<a>.+?) (?:compare|stack up|measure up) (?:with|to|against) (?P<b>.+?)[?.!]*$", re.I),
    re.compile(r"^(?P<a>.+?),? compare[sd]? (?:with|to) (?P<b>.+?)[?.!]*$", re.I),
    re.compile(rf"^which (?:is|are|was|were) (?:{_MORE})[,:]?\s+(?P<a>.+?) or (?P<b>.+?)[?.!]*$", re.I),
    re.compile(r"^(?:(?:what are|what is) )?(?:the )?(?:pros and cons|advantages and disadvantages|upsides and downsides|pros|cons) of (?P<a>.+?) (?:and|or|vs\.?|versus) (?P<b>.+?)[?.!]*$", re.I),
    re.compile(r"^(?:how|what) (?:is|are) (?P<a>.+?) (?:different|difference|differs?) from (?P<b>.+?)[?.!]*$", re.I),
    re.compile(r"^(?P<a>.+?) (?:differs?|is different|is a difference) from (?P<b>.+?)[?.!]*$", re.I),
    re.compile(r"^(?:the )?comparison (?:of|between) (?P<a>.+?) (?:and|with|to|vs\.?|versus) (?P<b>.+?)[?.!]*$", re.I),
    re.compile(r"\b(?:similarities|contrast) between (?P<a>.+?) and (?P<b>.+?)[?.!]*$", re.I),
)

#: The comparison triggers added to the "compare" shape rule: all two-sided,
#: so a question with one subject is never read as a comparison.
COMPARE_SHAPE_EXTRA = (
    rf"\b(?:{_MORE}) than\b|\bcompare[sd]? (?:with|to)\b|\b(?:pros and cons|advantages and disadvantages) of .+? (?:and|or|vs\.?|versus) |"
    rf"^which (?:is|are|was|were) (?:{_MORE})\b.+? or |\b(?:differs?|different|difference) from\b|\bcomparison (?:of|between)\b|"
    r"\b(?:similarities|contrast) between\b|\bstack up against\b|\bmeasure up (?:to|against)\b"
)

#: Comparison words are asking words: dropped from the subject, so "is Lisbon
#: cheaper than Porto" is about Lisbon and Porto and is never told no note
#: mentions "cheaper".
EXTRA_ASKING_WORDS = frozenset(
    """compared comparison versus better worse cheaper faster slower bigger smaller larger longer shorter
    easier harder safer pros cons advantages disadvantages drawbacks upsides downsides differ differs
    different than similarities contrast""".split()
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
        "I am Atlas's assistant. I answer from your notes: dates, decisions and the status of a project. I also set reminders and "
        "tag, move or pin notes on request. Connecting a model adds writing and summaries.",
        "Atlas's assistant answers from what you have recorded: a date, a decision, a list or the status of a project, and acts on "
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
 ['month',
  'january',
  'february',
  'march',
  'april',
  'may',
  'june',
  'july',
  'august',
  'september',
  'october',
  'november',
  'december'],
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
 'I can dig up more on “{subject}” if you need it.',
 'Let me know if you want the rest of the notes on “{subject}”.',
 'Should I keep looking for more on “{subject}”?',
 'There might be more on “{subject}”, want me to check?',
 "Say the word and I'll find more on “{subject}”.",
 "I'm happy to pull up more on “{subject}” if that helps.",
 'Want me to dive deeper into “{subject}”?',
 'Tell me if you need anything else on “{subject}”.',
 'I can check for other mentions of “{subject}”.',
 'Should we explore “{subject}” further?',
 'If you want, I can look for more details on “{subject}”.',
 'Want to see what else you wrote about “{subject}”?',
 "Let me know if you'd like me to continue searching for “{subject}”.",
 'Say “more” if you want to see other notes on “{subject}”.',
 "There's likely more on “{subject}” in your notes.",
 'I can always check for more info on “{subject}”.',
 'Let me know if you want me to expand on “{subject}”.',
 'Do you want me to pull up everything you have on “{subject}”?',
 'Should I gather all other mentions of “{subject}”?',
 'Need any further clarification on “{subject}”?',
 'I can run another search on “{subject}” if you want.',
 'Let me know if you want to know anything else about “{subject}”.',
 "I'm ready to keep digging into “{subject}”.",
 "Want to see if there's any related info to “{subject}”?",
 'I can check for context around “{subject}” if you like.',
 'Would it help to see more notes on “{subject}”?'])
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
    "recurrence": "You have written about {subject} {count} times since {since}{after}; {hedge}.",
    "streak": "You have written about {subject} {weeks} weeks running.",
    "drift": "Since {since}, no later note picks up this plan: {plan}. It may be still open.",
    "contrast": "On {first} you wrote {before}; on {last}, {after_said}. You may have changed your mind.",
    "load": "The week of {week} had {count} notes against a usual {usual}; a busy week.",
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
    "after": "clause", "hedge": "hedge",
}

#: Who it is and what it does are said as Atlas's assistant (CHAT_PLAN decision 36,
#: `composer.SOCIAL`): the unnamed lines added for these two kinds are retired.
for _retired in ("who", "about_app"):
    SOCIAL_NATURAL_EXTRA.pop(_retired, None)
