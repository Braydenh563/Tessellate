"""How a framed summary talks (INBOX 1512, the owner: "still needs better
social skills, grammar and variation"). With no model, "Summarise my notes
in Hobbies." quoted link reasons in the first person ("the mouse is used as
my gaming mouse on my laptop"), kept a reason's capital after a colon,
read a caption as "a picture of X depicts", said every group with the same
frames ("go together", "You linked X to Y:") and had no line naming the
threads. Each is a rule here, said of every summary, every group and every
link reason:

- **A link reason** is the person's words about their own notes: re-voiced
  to the second person ("your gaming mouse"), or, when it is slang or a
  joke ("random ass sketches lol"), quoted whole as theirs. Never a capital
  after the colon unless the word is a name.
- **A caption** is said as what the picture shows, past a captioner's own
  frame ("A photo depicts ...").
- **Groups vary**: each group's line and its link line have a wording of
  their own, turned by the group's place, and a link between the two notes
  the line just named refers back to them ("You linked them").
- **The lead names the threads**: "They fall into three threads: gaming,
  art and gym."

This module imports no composer: `composer_frame` and `composer_digest`
both call it, so it joins no import cycle.
"""

from __future__ import annotations

import re
from collections import Counter

from tessellate.ai import common_words, realise
from tessellate.core.lazyre import lazy_compile

# --- link reasons -------------------------------------------------------------

#: Slang, a joke or a laugh: the reason is said as the person's own words,
#: quoted, never re-voiced into the app's ("they are both random ass sketches").
_CASUAL = lazy_compile(
    r"\b(?:lol|lmao|lmfao|rofl|haha+|hehe+|omg|bruh|tbh|ngl|idk|af|asf|ass|ahh|xd|lowkey)\b|[:;]-?[()DPp]|!!|\?!",
    re.I,
)
#: The person's "I" as the reader's "you", the longest forms first.
_SECOND_PERSON = (
    (lazy_compile(r"\bI am\b"), "you are"), (lazy_compile(r"\bI was\b"), "you were"),
    (lazy_compile(r"\bI'm\b|\bIm\b", re.I), "you're"), (lazy_compile(r"\bI've\b", re.I), "you've"),
    (lazy_compile(r"\bI'd\b", re.I), "you'd"), (lazy_compile(r"\bI'll\b", re.I), "you'll"),
    (lazy_compile(r"\bI\b"), "you"), (lazy_compile(r"\bmyself\b", re.I), "yourself"),
    (lazy_compile(r"\bmine\b", re.I), "yours"), (lazy_compile(r"\bmy\b", re.I), "your"),
    (lazy_compile(r"\bme\b", re.I), "you"),
)
_CALENDAR = lazy_compile(r"(?:Mon|Tues|Wednes|Thurs|Fri|Satur|Sun)day|January|February|March|April|May|June|July|August|"
                         r"September|October|November|December")
_ENDINGS = ("ies", "es", "ed", "ing", "s", "d", "ly")


def _plain_word(word: str) -> bool:
    """A word of everyday English ("Shared", "Both"), not a name: its base
    form is in the shipped word list."""
    low = word.lower()
    if low in common_words.WORDS:
        return True
    return any(low.endswith(end) and low[: -len(end)] in common_words.WORDS for end in _ENDINGS if len(low) > len(end) + 2)


def lower_first(text: str) -> str:
    """`text` after a colon or other words: its first word lowered when it is
    a plain word written with a capital only because it led ("Shared Tuesday
    9pm legs training"), kept when it is a name ("Lisbon trip packing"), a
    shape ("iPhone") or "I"."""
    first = re.match(r"[A-Za-z][\w'-]*", text)
    if not first:
        return text
    word = first.group(0)
    if word == "I" or not word[1:].islower() or _CALENDAR.fullmatch(word) or not _plain_word(word):
        return text
    return text[:1].lower() + text[1:]


def reason_said(reason: str) -> str:
    """A link's reason as one clause after a colon: in the second person
    ("the mouse is used as your gaming mouse on your laptop"), or quoted as
    the person's own words when it is slang (“they are both random ass
    sketches lol”); "" for none."""
    text = " ".join(str(reason or "").split()).strip(" .")
    if not text:
        return ""
    if _CASUAL.search(text):
        return f"“{text}”"
    return lower_first(voiced(text))


#: A section's label that is a sentence leading into its list ("The split
#: follows this structure:"), not a name: "it also has the split follows
#: this structure" (INBOX 1512) is said "it also says the split follows ...".
_LABEL_VERB = lazy_compile(
    r"\s(?:is|are|was|were|has|have|had|will|can|should|must|goes|go|looks|follows|follow|works|means|includes|"
    r"contains|runs|starts|ends|says|needs|need|wants|want|did|does|do|went|looked)\b", re.I)


def label_is_sentence(label: str) -> bool:
    words = label.split()
    return len(words) >= 3 and bool(_LABEL_VERB.search(label))


_NUMBER_WORDS = frozenset("one two three four five six seven eight nine ten eleven twelve several few many some two".split())
_PREPOSITIONS = frozenset("for of before after to in on with by at from about until".split())


def _plural_head(words: list[str]) -> bool:
    """Whether the noun phrase before its first preposition is a plural or a counted one
    ("goals for the half", "three gates before then"), which takes no "a"."""
    if words[0].lower() in _NUMBER_WORDS or words[0][:1].isdigit():
        return True
    head: list[str] = []
    for word in words:
        if word.lower() in _PREPOSITIONS:
            break
        head.append(word)
    last = (head or words)[-1].lower()
    return last.endswith("s") and not last.endswith(("ss", "us", "is"))


def with_article(head: str) -> str:
    """"warm up" as "a warm up" after "has": a label of two or more plain
    words that is not a plural or a count; "attendees", "goals for the half",
    "three gates", "Phase 2" and "key points" stay as they are."""
    words = head.split()
    if len(words) < 2 or not head[:1].islower() or _plural_head(words) or words[0] in _LEADING | {"your", "my"}:
        return head
    return f"{'an' if head[0] in 'aeiou' else 'a'} {head}"


def voiced(text: str) -> str:
    """The person's "I" and "my" as "you" and "your", for words said back."""
    for pattern, said in _SECOND_PERSON:
        text = pattern.sub(said, text)
    return text


# --- captions -----------------------------------------------------------------

#: A captioner's verb between its frame and what the picture shows.
_SHOWING = lazy_compile(r"\s(?:depicts|shows|contains|features|displays|captures|portrays|is of)\s")
#: Nouns that name a picture and add nothing to what it shows.
_PICTURE_NOUNS = frozenset("image picture photo photograph pic snapshot shot".split())
_LEADING = frozenset("a an the this one".split())
#: The most words "a picture of X depicts ..." may name X in.
_NAMED_WORDS = 5
_OF = lazy_compile(r"^(?:(?:a|an|the|this|one)\s+)?(?:picture|photo|photograph|image|pic|snapshot)\s+of\s+(?=\S)", re.I)


def _picture_frame(subject: str) -> tuple[bool, str]:
    """Whether `subject` ("A close-up photo", "a picture of a gaming mouse")
    only names the picture, and what it names after "of", if anything."""
    words = subject.split()
    at = next((n for n, w in enumerate(words[:4]) if w.lower().strip(",") in _PICTURE_NOUNS), -1)
    if at == -1:
        return False, ""
    rest = words[at + 1:]
    if not rest:
        return True, ""
    if rest[0].lower() == "of" and len(rest) > 1:
        return True, " ".join(rest[1:])
    return False, ""


def caption_said(caption: str) -> str:
    """What a picture shows, past its captioner's frame: "A photo depicts a
    black gaming mouse" is "a black gaming mouse"; "a picture of a gaming
    mouse depicts its buttons" is "a gaming mouse"; a kind that says
    something ("a pencil sketch of a dragon") is kept."""
    text = " ".join(str(caption or "").split()).rstrip(".")
    verb = _SHOWING.search(text)
    if verb:
        framed, named = _picture_frame(text[: verb.start()])
        #: Only a short name before the verb: "features" and "shows" are nouns
        #: too, and "a hill with arrows pointing to different features and a
        #: caption" was said as "a hill with arrows pointing to different" (1555).
        if framed and len(named.split()) <= _NAMED_WORDS:
            text = named or text[verb.end():]
    text = _OF.sub("", text, count=1)
    first = text.split(" ", 1)[0]
    return text[:1].lower() + text[1:] if first.lower() in _LEADING else text


#: Where a noun phrase's own verb could no longer be: a preposition or a
#: relative word opens a modifier ("a lamp that shows the time").
_MODIFIER_OPENERS = frozenset(
    "with in on of by that which who whom whose at under near from for and or to beside behind over as while where into onto "
    "against along around between through above below across inside outside".split()
)
#: Verbs a captioner gives a scene's subject (a closed list: no tagger here).
_CAPTION_VERBS = frozenset(
    "is are was were has have had does do can will depicts depict shows show contains contain features feature displays display "
    "captures capture portrays portray sits sit stands stand lies lie rests rest appears appear looks look floats float "
    "walks walk runs run flies fly sleeps sleep holds hold wears wear plays play gathers gather swims swim hangs hang "
    "fills fill covers cover surrounds surround stretches stretch glows glow rises rise falls fall flows flow grows grow "
    "wanders wander poses pose smiles smile waits wait lounges lounge perches perch crouches crouch leans lean".split()
)
_SENTENCE_BREAK = lazy_compile(r"[.!?][\"”’)]?\s+[A-Z]")


def caption_form(caption: str) -> tuple[bool, str]:
    """(whole, said): a caption that is a sentence of its own (a subject with
    its own verb, or several sentences) is `whole` and said as it stands, with
    no final full stop; a noun phrase is said lowered after "shows" like
    `caption_said` (INBOX 1599: "shows a vibrant forest scene depicts several
    creatures" spliced a sentence after a verb)."""
    text = " ".join(str(caption or "").split())
    bare = text.rstrip(".")
    said = caption_said(text)
    if said.lower() != bare.lower():
        return False, said
    bare = bare[:1].upper() + bare[1:]
    if _SENTENCE_BREAK.search(bare):
        return True, bare
    for n, word in enumerate(w.strip(",;:\"'()").lower() for w in bare.split()):
        if word in _MODIFIER_OPENERS:
            break
        if n and word in _CAPTION_VERBS:
            return True, bare
    return False, said


#: A picture line says itself whole: no frame of writing goes round it
#: ("You wrote that the picture in ...", "Your note says “The picture ...”").
PICTURE_LEADS = ("the picture in ", "its picture ", "your picture ")


def said_whole(body: str) -> bool:
    return body.lower().startswith(PICTURE_LEADS)


_MONTHS = ("January", "February", "March", "April", "May", "June", "July", "August", "September", "October",
           "November", "December")


def _day_said(note: dict) -> str:
    """"12 October" from the note's ISO `created_at` or the route's `written`
    words ("Monday 12 October 2026, 18:00"); "" when it has neither."""
    iso = re.match(r"(\d{4})-(\d{2})-(\d{2})", str(note.get("created_at") or ""))
    if iso:
        return f"{int(iso.group(3))} {_MONTHS[int(iso.group(2)) - 1]}"
    words = re.search(rf"\b(\d{{1,2}}) ({'|'.join(_MONTHS)})\b", str(note.get("written") or ""))
    return f"{int(words.group(1))} {words.group(2)}" if words else ""


def picture_name(note: dict) -> str:
    """A note that is only a picture, named by its day ("your picture from
    12 October"), never by its markdown ("your ![](/media/cat.png) note")."""
    day = _day_said(note)
    return f"your picture from {day}" if day else "your picture with no title"


def note_from(note: dict) -> str:
    """A note named by its day ("your note from 12 October") when its own
    words are quoted on the line after: the name must not say them twice."""
    day = _day_said(note)
    return f"your note from {day}" if day else "a note of yours"


# --- group and link lines -----------------------------------------------------

#: A group's line, one wording a group in turn so neighbours differ.
GROUP_FRAMES = (
    "{theme} go together: {names}{tail}",
    "then there are {theme}: {names}{tail}",
    "{theme} make a thread of their own: {names}{tail}",
    "{theme} are another thread: {names}{tail}",
)
#: A link between the two notes the line just named, said back to them.
LINK_BACK = (
    "You linked them{tail}.",
    "The link between them says why{tail}.",
    "You joined the two with a link{tail}.",
    "Your link between them gives the reason{tail}.",
)
#: A link inside a bigger group, its two ends named.
LINK_NAMED = (
    "You linked {a} to {b}{tail}.",
    "{A} is linked to {b}{tail}.",
    "The link from {a} to {b} says why{tail}.",
    "You joined {a} and {b} with a link{tail}.",
)
LINK_BARE = ("You linked them.", "They are linked too.", "You joined the two with a link.", "You linked the pair.")


def more_theme(theme: str, i: int) -> str:
    """"two of your notes" is "two more of your notes" after the first group."""
    if i and theme.startswith(("two of", "some of")):
        return theme.replace(" of ", " more of ", 1)
    return theme


def group_said(theme: str, names: str, tail: str, i: int) -> str:
    return GROUP_FRAMES[i % len(GROUP_FRAMES)].format(theme=more_theme(theme, i), names=names, tail=tail)


_REASON_STOP = frozenset("shared share both same about with the and are is these those notes note related similar also together linked link".split())


def restated(reason: str, first: dict, second: dict) -> bool:
    """Whether every word of a link's `reason` is already in the two notes
    ("Shared Tuesday 9pm legs training" over a note that says "tuesday for legs"
    and one that says "Training"): the link line then says no more than they do."""
    words = [w for w in re.findall(r"[a-z0-9]+", reason.lower()) if w not in _REASON_STOP]
    held = re.findall(r"[a-z0-9]+", f"{first.get('content')} {second.get('content')}".lower())
    return bool(words) and all(any(h.startswith(w[:4]) for h in held) for w in words)


def link_said(a: str, b: str, reason: str, i: int, back: bool) -> str:
    """The link line: back to "them" when the group is just the pair."""
    said = reason_said(reason)
    tail = f": {said}" if said else ""
    if back:
        return LINK_BACK[i % len(LINK_BACK)].format(tail=tail) if said else LINK_BARE[i % len(LINK_BARE)]
    line = LINK_NAMED[i % len(LINK_NAMED)].format(a=a, b=b, A=a[:1].upper() + a[1:], tail=tail)
    return line[:1].upper() + line[1:]


# --- the lead -----------------------------------------------------------------

_THREAD_STOP = frozenset("""
just also very really with from that this have will been into about your their them they there what when then than some
more most other each both note notes picture image photo shows depicts media day days week today because which while
""".split())
_WORD = lazy_compile(r"[a-z][a-z'-]{3,}")


def _stem(word: str) -> str:
    for end in ("es", "s"):
        if word.endswith(end) and len(word) > len(end) + 3:
            return word[: -len(end)]
    return word


def thread_word(texts: list[str]) -> str:
    """The word most of a group's notes share ("gaming", "sketches"), as
    written, or "" when no word is shared by two of them."""
    seen: Counter = Counter()
    said: dict[str, str] = {}
    for text in texts:
        stems = set()
        for word in _WORD.findall(text.lower()):
            if word in _THREAD_STOP or word.isdigit():
                continue
            stem = _stem(word)
            said.setdefault(stem, word)
            stems.add(stem)
        seen.update(stems)
    shared = [stem for stem, n in seen.most_common() if n > 1]
    return said[shared[0]] if shared else ""


LEAD_FRAMES = (
    "They fall into {count} threads: {names}.",
    "{Count} threads run through them: {names}.",
    "Mostly they are about {names}.",
)


def lead_said(threads: list[str], seed: int = 0) -> str:
    """"They fall into three threads: gaming, art and gym." for two or more
    named threads, else ""."""
    named = list(dict.fromkeys(t for t in threads if t))
    if len(named) < 2:
        return ""
    count = realise.count_word(len(named))
    frame = LEAD_FRAMES[seed % len(LEAD_FRAMES)]
    return frame.format(count=count, Count=count.capitalize(), names=realise.join_items(named))


# --- a quote is the note's own words -------------------------------------------

_QUOTED = lazy_compile(r"“([^”\n]{3,600})”")
_PIECE_END = lazy_compile(r"(?<=[.!?])\s+")
_MARK_CHARS = lazy_compile(r"[*_`#>~]|!\[[^\]\n]{0,300}\]\([^)\n]{0,1000}\)")
_TOKEN = lazy_compile(r"[a-z0-9']+")
#: How much of a piece's words a note's sentence must hold to be what the
#: piece was made from.
_SAME_SENTENCE = 0.6


def _flat(text: str) -> str:
    text = _MARK_CHARS.sub(" ", text).replace("’", "'").replace("‘", "'").lower()
    return " ".join(text.split()).strip(" .…!?:;,")


def _original(piece: str, raws: list[str]) -> str:
    """The note's own sentence the app's re-worded `piece` came from, or the
    piece itself when no sentence is close enough."""
    mine = set(_TOKEN.findall(piece.lower()))
    if len(mine) < 3:
        return piece
    best, score = "", 0.0
    for raw in raws:
        theirs = set(_TOKEN.findall(raw.lower()))
        near = len(mine & theirs) / len(mine | theirs) if theirs else 0.0
        if near > score:
            best, score = raw, near
    return best if score >= _SAME_SENTENCE else piece


#: Words the app swaps or adds when it re-voices a note: never evidence of which sentence it was.
_VOICE_WORDS = frozenset("i me my mine we our us you your yours and that is are was were the a an it".split())
_SENTENCE = lazy_compile(r"[^.!?\n]+(?:[.!?]+|$)")


def _content(text: str) -> set[str]:
    return {re.sub(r"'(?:d|ll|ve|m|s|re)$", "", t) for t in _TOKEN.findall(text.lower())} - _VOICE_WORDS


def _run_of(quote: str, sources: list[str]) -> str:
    """The note's own run of one to three sentences that `quote` re-voiced or
    merged, byte for byte; "" when no run holds most of its words (R9-4)."""
    mine = _content(quote)
    if len(mine) < 3:
        return ""
    best, score = "", 0.0
    for source in sources:
        for line in source.splitlines():
            spans = [(m.start(), m.end()) for m in _SENTENCE.finditer(line) if m.group(0).strip(" -*•|")]
            for size in (1, 2, 3):
                for at in range(len(spans) - size + 1):
                    raw = line[spans[at][0] : spans[at + size - 1][1]].strip(" -*•")
                    theirs = _content(raw)
                    if not theirs:
                        continue
                    hit = len(mine & theirs)
                    recall, precision = hit / len(mine), hit / len(theirs)
                    if recall >= 0.75 and precision >= 0.55 and recall * precision > score:
                        best, score = raw, recall * precision
    return best.rstrip(".") if best and not quote.rstrip().endswith((".", "!", "?")) else best


_TABLE_QUOTE = lazy_compile(r"(?:(?:[Yy]ou (?:wrote|noted down|put down|noted|wrote down)|[Ii]t also says|[Yy]our [^“”\n]{1,60}? note says) )?“\|([^”\n]*\|)[^”\n]*”")


def _row_said(found: re.Match) -> str:
    """A table row is not a quotation: "| Marek | £7,200 |" is "Marek at £7,200" (R9-4)."""
    cells = [c.strip() for c in ("|" + found.group(1)).strip("|").split("|") if c.strip()]
    if len(cells) == 2:
        said = f"{cells[0]} at {cells[1]}" if re.match(r"[£$€\d]", cells[1]) else f"{cells[0]}: {cells[1]}"
    else:
        said = ", ".join(cells)
    return ("You listed " if found.start() == 0 else "you listed ") + said


def own_words(line: str, sources: list[str]) -> str:
    """`line` with every “quote” made the note's own words (INBOX 1515: “Bake
    at 230C. You rested the dough” held the app's re-voicing of the note's
    "Rested the dough"): a quote the notes (or their link reasons) do not hold
    whole is mended sentence by sentence from the sentence it was made from.
    A quote that matches nothing is left as it is."""
    if "“" not in line or not sources:
        return line
    held = " | ".join(_flat(s) for s in sources)
    raws: list[str] = []

    def mend(found: re.Match) -> str:
        quote = found.group(1)
        if _flat(quote) in held:
            return found.group(0)
        if not raws:
            raws.extend(p.strip(" -*•") for s in sources for ln in s.splitlines() for p in _PIECE_END.split(ln) if p.strip(" -*•"))
        pieces = _PIECE_END.split(quote)
        mended = [p if _flat(p) in held else _original(p, raws) for p in pieces]
        if mended and not quote.rstrip().endswith((".", "!", "?")):
            mended[-1] = mended[-1].rstrip(".")
        whole = " ".join(mended)
        if any(_flat(p) not in held for p in mended):
            #: Two sentences merged into one ("list comprehensions and
            #: assignment due Friday"): the note's own run of sentences (R9-4).
            whole = _run_of(quote, sources) or whole
        return "“" + whole + "”"

    return _TABLE_QUOTE.sub(_row_said, _QUOTED.sub(mend, line))
