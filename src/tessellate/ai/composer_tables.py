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

from tessellate import data
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
_FAMILIES: dict[str, dict[str, list[str]]] = data.table("composer_tables.json")["_FAMILIES.1"]

#: Pairs said around a measured value: the second takes the first's index, so
#: "Recorded on 3 March: ..." never meets "you wrote: ". Equal lengths.
_PAIRS: dict[str, dict[str, list[str]]] = data.table("composer_tables.json")["_PAIRS.1"]
#: The overview of a topic (INBOX 787, the owner: "the composer is still
#: pretty barebone, has no life to it"): how many notes, over which days,
#: the thread most of them share, then the notes grouped by it. Each pair
#: varies together so "You have ... notes about" never meets "entries on".
_OVERVIEW_PAIRS: dict[str, dict[str, list[str]]] = data.table("composer_tables.json")["_OVERVIEW_PAIRS.1"]
_FAMILIES.update({
    "ov_also": {"natural": ["Other notes", "The rest"], "professional": ["Other entries", "Remaining entries"]},
    #: The one left over, said as one (never "There are one more besides": audit 1031 C36).
    "ov_one_more": {"natural": ["There is one more besides.", "And one more not shown here."], "professional": ["One further entry is not shown.", "One entry is not shown here."]},
    "ov_reads": {"natural": [", which reads ", ", with the words "], "professional": [", reading ", ", which reads "]},
})
_PAIRS.update(_OVERVIEW_PAIRS)
#: The canonical texts the variants above vary (`composer.PHRASES` takes them).
OVERVIEW_PHRASES = data.table("composer_tables.json")["OVERVIEW_PHRASES.1"]
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
_FAMILIES_ADDED: dict[str, dict[str, list[str]]] = data.table("composer_tables.json")["_FAMILIES_ADDED.1"]
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
EXTRA_SYNONYM_GROUPS: tuple[tuple[str, ...], ...] = data.deep_tuple(data.table("composer_tables.json")["EXTRA_SYNONYM_GROUPS.1"])

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
EXTRA_WRAPPERS: tuple[str, ...] = data.deep_tuple(data.table("composer_tables.json")["EXTRA_WRAPPERS.1"])

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
SOCIAL_NATURAL_EXTRA: dict[str, tuple[str, ...]] = {k: data.deep_tuple(v) for k, v in data.table("composer_tables.json")["SOCIAL_NATURAL_EXTRA.1"].items()}

#: The professional voice's lines, one tuple per kind. Same kinds as `SOCIAL`.
SOCIAL_PROFESSIONAL: dict[str, tuple[str, ...]] = {k: data.deep_tuple(v) for k, v in data.table("composer_tables.json")["SOCIAL_PROFESSIONAL.1"].items()}

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

EXTRA_SYNONYM_GROUPS = EXTRA_SYNONYM_GROUPS + data.deep_tuple(data.table("composer_tables.json")["EXTRA_SYNONYM_GROUPS.2"])

#: A concept word and the members a note may name instead: "sport" is a note that says only "swimming".
#: Read by `composer._fit_terms`, for scoring only (the answer never prints the member as if it were typed).
CONCEPTS: dict[str, tuple[str, ...]] = {
    "sport": ("swimming", "swam", "running", "ran", "football", "tennis", "cycling", "cycled", "gym", "yoga", "climbing", "hiking", "badminton", "rugby", "cricket", "golf"),
    "exercise": ("swimming", "swam", "running", "ran", "gym", "yoga", "cycling", "hiking", "climbing", "workout"),
    #: "gym" is a place, not a concept: a running note is not a gym note (test_engine_probe_step0 p7).
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
VERB_NOUN_PAIRS: tuple[tuple[str, ...], ...] = data.deep_tuple(data.table("composer_tables.json")["VERB_NOUN_PAIRS.1"])
EXTRA_SYNONYM_GROUPS = EXTRA_SYNONYM_GROUPS + VERB_NOUN_PAIRS
EXTRA_ASKING_WORDS = EXTRA_ASKING_WORDS | frozenset(data.deep_tuple(data.table("composer_tables.json")["EXTRA_ASKING_WORDS.1"]))
EXTRA_WRAPPERS = EXTRA_WRAPPERS + data.deep_tuple(data.table("composer_tables.json")["EXTRA_WRAPPERS.2"])
EXTRA_TRAILERS = EXTRA_TRAILERS + data.deep_tuple(data.table("composer_tables.json")["EXTRA_TRAILERS.1"])
EXTRA_LEAD_INS = EXTRA_LEAD_INS + data.deep_tuple(data.table("composer_tables.json")["EXTRA_LEAD_INS.1"])
NEXT_STEPS_EXTRA = NEXT_STEPS_EXTRA + data.deep_tuple(data.table("composer_tables.json")["NEXT_STEPS_EXTRA.1"])
NEXT_STEPS_PROFESSIONAL = NEXT_STEPS_PROFESSIONAL + data.deep_tuple(data.table("composer_tables.json")["NEXT_STEPS_PROFESSIONAL.1"])
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
