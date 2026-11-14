"""The conversation itself (audit 1110 F4): turns that are about the talk, not
about a note, read ahead of any search.

- **Social.** "How are you", "thanks for listening", "i feel sick", "i miss
  anna": a short warm line, varied by turn, never a quote from a note.
- **Meta.** "shorter", "say that again", "simpler", "in bullets": acts on the
  previous answer, read from the history the request carries (as
  `composer_talk` does).
- **Comparison.** "which is higher" binds to the numbers the previous answer
  stated, never to general knowledge.

- **Reactions.** "Really?", "maybe", "are you sure", "where did you get that",
  "more detail", "what was my first question": read against the answer before.
- **Declined.** "No thanks" after an offer drops it; "no" after an ack is no repair.

Each reader returns the answer text, or None to leave the turn to the others.
"""

from __future__ import annotations

import re

from tessellate.ai import phrasing

_END = r"[\s?.!]*$"


def _clean(text: str) -> str:
    return " ".join(str(text or "").replace("’", "'").lower().split())


# --- the previous answer ------------------------------------------------------


def _last_answer(history: list[dict] | None) -> str:
    for turn in reversed(history or []):
        said = str(turn.get("answer") or "").strip()
        if said:
            return said
    return ""


def _plain(text: str) -> str:
    """The words without links, bold, quoted-source brackets or lists."""
    text = re.sub(r"\[([^\]]{1,300})\]\(([^)]{0,1000})\)", r"\1", text)
    text = re.sub(r"\[[“\"][^\]]{0,300}[”\"]\]", "", text)
    text = re.sub(r"[*_`]+", "", text)
    return re.sub(r"[ \t]+", " ", text).strip()


def _sentences(text: str) -> list[str]:
    parts = re.split(r"(?<=[.!?])\s+(?=[A-Z0-9“\"])|\n+", _plain(text))
    return [p.strip(" -") for p in parts if p.strip(" -")]


# --- meta: shorter, again, simpler, bullets -------------------------------------

_POLITE = r"(?:(?:can|could|would) you |please |just |now |and |ok |okay )*"
_AGAIN = re.compile(
    rf"^{_POLITE}(?:say (?:that|it) again|repeat (?:that|it|yourself)|(?:say|tell me) (?:that|it) once more|one more time|come again|pardon|what did you (?:just )?say|what was that)(?: please)?{_END}"
)
_SHORTER = re.compile(
    rf"^{_POLITE}(?:(?:make (?:it|that) |be |keep it |give me (?:a |the )?)?(?:shorter|shorten (?:it|that)|short version|brief(?:er)?)|(?:in|as) (?:one|1) sentence|tl;?dr|too long)(?: please)?{_END}"
)
_SIMPLER = re.compile(
    rf"^{_POLITE}(?:(?:make (?:it|that) |explain (?:it|that) )?(?:simpler|simply|more simply|in plain (?:words|english)|in simple (?:words|terms))|simplify(?: (?:it|that))?|dumb (?:it|that) down|eli5|say it simply)(?: please)?{_END}"
)
_BULLETS = re.compile(rf"^{_POLITE}(?:(?:in )?(?:bullets?|bullet points?|a list|list form)|as (?:a )?(?:bullets?|bullet points?|list))(?: please)?{_END}")

_AGAIN_LEADS = ["Of course.", "Sure.", "Here it is again.", "Once more.", "Happy to."]
_SHORT_SAME = ["That is about as short as it gets.", "There is not much more to cut.", "That is already the short version."]
_SIMPLE_LEADS = ["In plain words:", "Put simply:", "Simply put:", "The plain version:"]


def _lead(options: list[str], key: str, history: list[dict] | None, seed: str) -> str:
    recent = [str(t.get("answer") or "") for t in (history or [])][-phrasing.RECENT :]
    return phrasing.choose(options, key, recent, seed)


def _shorter(answer: str, history: list[dict] | None, seed: str) -> str:
    sentences = _sentences(answer)
    if len(sentences) > 1:
        return sentences[0]
    return f"{sentences[0] if sentences else answer} {_lead(_SHORT_SAME, 'short', history, seed)}"


def _simpler(answer: str, history: list[dict] | None, seed: str) -> str:
    keep = [re.sub(r"\s*\([^)]*\)", "", s) for s in _sentences(answer)][:2]
    return f"{_lead(_SIMPLE_LEADS, 'simple', history, seed)} {' '.join(keep)}"


def _bullets(answer: str) -> str:
    return "\n".join(f"- {s}" for s in _sentences(answer))


def meta(question: str, history: list[dict] | None, seed: str = "") -> str | None:
    """A turn about the previous answer, acted on it; None when there is no
    previous answer or the turn is not one of these."""
    answer = _last_answer(history)
    said = _clean(question)
    if not answer or not said or len(said.split()) > 7:
        return None
    if _AGAIN.match(said):
        return f"{_lead(_AGAIN_LEADS, 'again', history, seed)} {answer}"
    if _SHORTER.match(said):
        return _shorter(answer, history, seed)
    if _SIMPLER.match(said):
        return _simpler(answer, history, seed)
    if _BULLETS.match(said):
        return _bullets(answer)
    return None


# --- comparison over the previous answer's numbers ---------------------------------

_HIGH = r"higher|highest|bigger|biggest|larger|largest|greater|greatest|more|most|costlier|dearer|longer|longest"
_LOW = r"lower|lowest|smaller|smallest|less|least|fewer|fewest|cheaper|cheapest|shorter|shortest"
_COMPARE = re.compile(rf"^{_POLITE}(?:and )?(?:which|what)(?: one| is| was| one is| one was| are| were| of them)*(?: the)? (?P<dir>{_HIGH}|{_LOW})(?: of the two| of them| one)?{_END}")
_NUM = r"[£$€]?\d[\d,]*(?:\.\d+)?%?"
_STOP = {"this", "that", "and", "but", "so", "then", "in", "on", "at", "for", "to", "of", "the", "a", "an"}
_AFTER = re.compile(rf"(?P<n>{_NUM})(?P<unit> [a-z]+)? (?:on|for|in|at|to|from) (?:the |a |an |my |your )?(?P<label>[a-z][a-z']*(?: [a-z][a-z']*)?)")
_BEFORE = re.compile(rf"(?P<label>[A-Z][\w' ]{{0,28}}?)\s*(?::|-|is|was|are|were|costs|cost|at|=)\s*(?P<n>{_NUM})(?P<unit> [a-z]+)?")


def _value(raw: str) -> float:
    return float(re.sub(r"[^\d.]", "", raw) or 0)


def _label(raw: str) -> str:
    kept: list[str] = []
    for word in raw.lower().split():
        if word in _STOP:
            break
        kept.append(word)
    return " ".join(kept[:2])


def _pairs(answer: str) -> list[tuple[str, str, float]]:
    """(label, shown figure, value) for each labelled number in the answer, in order."""
    text = _plain(answer)
    found: list[tuple[int, str, str, float]] = []
    for pattern in (_AFTER, _BEFORE):
        for m in pattern.finditer(text):
            unit = (m.group("unit") or "").strip()
            label = _label(m.group("label"))
            if label and label not in {"november", "december"}:
                found.append((m.start(), label, f"{m.group('n')}{' ' + unit if unit and unit not in _STOP else ''}", _value(m.group("n"))))
    seen: set[str] = set()
    out = []
    for _pos, label, shown, value in sorted(found):
        if label not in seen:
            seen.add(label)
            out.append((label, shown, value))
    return out


_COMPARED = [
    "{a} is the {word} at {sa}, against {sb} for {b}.",
    "{a}: {sa}, which beats {sb} for {b}.",
    "That is {a}, with {sa}. {b} comes to {sb}.",
    "{a} wins on {sa}; {b} is {sb}.",
]
_NO_PAIR = [
    "I do not see two numbers in my last answer to compare. Which ones do you mean?",
    "My last answer has no pair of figures to weigh up. Tell me which two and I will compare them.",
]


def compare(question: str, history: list[dict] | None, seed: str = "") -> str | None:
    """"Which is higher" over the previous answer's figures; None when the
    turn is not a comparison or there is no previous answer."""
    answer = _last_answer(history)
    found = _COMPARE.match(_clean(question))
    if not answer or not found:
        return None
    pairs = _pairs(answer)
    if len(pairs) < 2:
        return _lead(_NO_PAIR, "nopair", history, seed)
    high = re.fullmatch(_HIGH, found.group("dir")) is not None
    ordered = sorted(pairs, key=lambda p: p[2], reverse=high)
    (a, sa, _), (b, sb, _) = ordered[0], ordered[1]
    word = "higher" if high else "lower"
    return _lead(_COMPARED, "compare", history, seed).format(a=a.capitalize(), b=b, sa=sa, sb=sb, word=word)


# --- social: how are you, feelings, remarks ---------------------------------------

_HOW = re.compile(
    rf"^(?:(?:hey|hi|hello|so|and|ok|okay) )*(?:how (?:are|r) (?:you|u)(?: doing| going| feeling)?|how(?:'s| is) it going|how have you been|how(?:'s| is) your day(?: going)?|are you (?:ok|okay|alright|well)|you (?:ok|okay|alright)){_END}"
)
_THANKS = re.compile(rf"^(?:thanks|thank you|ty|cheers|thx) for (?:listening|the chat|chatting|talking|being there|being here|hearing me out){_END}")
_LOVE = re.compile(rf"^(?:i )?(?:love|luv|like|adore) (?:you|u)(?: so much| lots| a lot)?{_END}")
_MISS = re.compile(rf"^i (?:really |do |so )*miss (?P<who>[a-z][a-z' ]{{1,30}}?){_END}")
_FEELING_WORDS = (
    "sick|ill|unwell|tired|exhausted|sad|down|low|anxious|stressed|worried|nervous|overwhelmed|awful|terrible|rubbish|lonely|bored|angry|upset|lost|stuck|"
    "burnt out|burned out|drained|knackered|sleepy|happy|great|excited|good|fine|okay|ok|proud|relieved|hopeful|scared|afraid|nauseous|dizzy|hungover|rough|crap|grumpy|cranky|worn out"
)
_FEEL = re.compile(
    rf"^(?:i(?:'m| am|'ve been| have been| feel| felt| am feeling|'m feeling| feel so| feel really| keep feeling)|im|feeling|i just feel|i think i'm)\s+(?:(?:so|really|very|quite|a bit|a little|kind of|kinda|just|pretty|totally|super) )*"
    rf"(?:feeling )?(?P<what>{_FEELING_WORDS})(?: [a-z]+)?(?: (?:about|with|over|because of|from) (?:the |my |our |this |that )?(?P<about>[a-z][a-z' ]{{1,30}}?))?{_END}"
)
_UNHELPFUL = re.compile(
    rf"^(?:(?:well|honestly|ok|okay|so|hmm+|ugh|but) )*(?:you(?:'re| are| were|'ve been)|that(?:'s| is| was)|this(?:'s| is)|the (?:answer|reply|help)(?:'s| is| was))\s+(?:(?:really|just|so|very|too|all that|that|quite|being) )*"
    rf"(?:not (?:(?:very|that|so|all that|really|at all|much) )*(?:helpful|useful|any help|much help|any use)(?: at all)?|unhelpful|no help|no use|not helping|of no help|not much help){_END}"
)
_CANT = re.compile(rf"^i (?:can't|cannot|can not|couldn't|could not) (?:seem to )?(?:focus|concentrate|sleep|cope|relax|switch off|stop worrying|get going|get started)(?: [a-z]+)?{_END}")

_HOW_LINES = [
    "Doing well, thanks. How are you getting on?",
    "All good here. What are you up to today?",
    "Steady and ready. How is your day so far?",
    "Fine, thank you for asking. How about you?",
    "Good, and glad you asked. What is on your mind?",
    "Pretty well. How has your day been?",
]
_HOW_LINES_ASKING = {line for line in _HOW_LINES if line.endswith("?")}
_THANKS_LINES = ["Any time.", "Glad to. I am here whenever you want to talk it through.", "Of course. That is what I am here for.", "My pleasure. Anything else on your mind?"]
_LOVE_LINES = [
    "That is kind of you. I am a program, but I am glad to be useful.",
    "Thank you. I am only a notebook helper, but I like working with your notes.",
    "That made my day, such as a program has one. Anything I can find for you?",
    "Kind of you to say. I will keep your notes in order.",
]
_FEEL_LINES = [
    "I am sorry you are {what}. Take it easy; I am here if you want to write it down or look something up.",
    "That sounds hard, being {what}. Be kind to yourself today.",
    "Sorry to hear you are {what}. I can keep notes or reminders light for today if that helps.",
    "Being {what} is rough. Rest if you can; nothing here needs to be done this minute.",
    "I hear you, {what} is no fun. Tell me if you want something added or found.",
]
_GLAD_LINES = [
    "Glad to hear you are {what}. Anything you want to jot down?",
    "Good, {what} is a nice thing to be. What shall we do with the day?",
    "Lovely, I am happy you are {what}. Tell me what you would like to look up.",
]
_CANT_LINES = [
    "That sounds frustrating. A short break or one small task can help; I can list your next small thing.",
    "Some days are like that. Want me to pull out just one thing from your notes to start with?",
    "I am sorry, that is hard. We can keep it to a single task and leave the rest.",
]
_UNHELPFUL_LINES = [
    "Fair, that did not help. Tell me what you were after, in any words, and I will look again.",
    "Sorry that missed. Name the note, the date or the thing you want and I will start there.",
    "Point taken. Say it another way, or ask for one note by its title, and I will have another go.",
]
_MISS_LINES = [
    "Missing someone is hard. I can pull up what you have written about {who} if that would help.",
    "That is a real feeling, and a kind one. Shall I show what your notes say about {who}?",
    "I am sorry you miss {who}. I can bring up your notes on them whenever you like.",
]
_GLAD = {"happy", "great", "excited", "good", "fine", "okay", "ok", "proud", "relieved", "hopeful"}


def _feeling(said: str, history: list[dict] | None, seed: str) -> str | None:
    if _CANT.match(said):
        return _lead(_CANT_LINES, said, history, seed)
    found = _FEEL.match(said)
    if not found:
        return None
    what = found.group("what")
    lines = _GLAD_LINES if what in _GLAD else _FEEL_LINES
    return _lead(lines, said, history, seed).format(what=what)


def _remark(said: str, history: list[dict] | None, seed: str) -> str | None:
    if _HOW.match(said):
        return _lead(_HOW_LINES, said, history, seed)
    if _THANKS.match(said):
        return _lead(_THANKS_LINES, said, history, seed)
    if _LOVE.match(said):
        return _lead(_LOVE_LINES, said, history, seed)
    if _UNHELPFUL.match(said):
        return _lead(_UNHELPFUL_LINES, said, history, seed)
    missed = _MISS.match(said)
    if missed:
        return _lead(_MISS_LINES, said, history, seed).format(who=missed.group("who").title())
    return None


def social(question: str, history: list[dict] | None, seed: str = "") -> str | None:
    """A warm short line for a greeting-like, feeling or remark turn, else None."""
    said = _clean(question).rstrip("?!. ")
    if not said or len(said.split()) > 9:
        return None
    return _remark(said, history, seed) or _feeling(said, history, seed)


# --- reactions to the answer before ------------------------------------------------------------

_RE_DOUBT = re.compile(rf"^(?:oh |ah |and )*(?:really|seriously|truly|honestly|is that (?:right|true|so)|(?:are )?you (?:really |quite )?(?:sure|certain)(?: about (?:that|it|this))?|sure about (?:that|it)){_END}")
_RE_MUSE = re.compile(rf"^(?:oh |ah |well |um |so |and )*(?:maybe|perhaps|hmm+|hm+|interesting|i see|i guess|possibly|and then|then what|so what|what then){_END}")
_RE_SOURCE = re.compile(
    rf"^{_POLITE}(?:where did (?:you|that|this) (?:get|find|come|read|see)(?: that| it| this)?(?: from)?|where(?:'s| is) (?:that|this|it) from|what(?:'s| is) (?:your|the) source(?:s)?|"
    rf"(?:which|what) note(?:s)? (?:is|was|are|were) (?:that|this|it)(?: from| in)?|how do you know(?: that| this)?|who (?:says|said) (?:that|so)|source(?:s)?){{1}}{_END}"
)
_RE_DETAIL = re.compile(rf"^{_POLITE}(?:(?:give me |tell me |show me |i want |with )?(?:a bit |a little )?more (?:detail|details|info|information)|in (?:more )?detail|elaborate|expand(?: on (?:that|it))?|go into (?:more )?detail|can you elaborate){_END}")
_RE_FIRST = re.compile(rf"^(?:what|which) (?:was|is) (?:my|the) (?:very )?first (?:question|message|thing i (?:asked|said))(?: (?:to you|today|here))?{_END}")

_LINK = re.compile(r"\[([^\]]{1,300})\]\(#/notes/\d+\)")
_CITED = re.compile(r"\bfrom your (?P<t>.+?) note\b|\[\*\*(?P<b>[^*\]]+)\*\*\]", re.I)

_SURE_LINES = [
    "As sure as your notes are: that comes from your {names} {note}.",
    "It is what your {names} {note} says, word for word, so yes.",
    "I only say what your notes do, and that was from your {names} {note}.",
]
_SURE_NONE = ["I am only repeating what your notes say, and I do not see a note behind that one. Ask me again and I will check.", "That one is my own wording, not a quote, so double-check it against your notes."]
_SOURCE_LINES = ["That came from your {names} {note}.", "It is from your {names} {note}.", "I took it from your {names} {note}."]
_SOURCE_NONE = ["That was my own wording rather than a quote from a note.", "No note sits behind that one; it was my own line."]
_NOTHING_YET = ["There is nothing before that to check yet. Ask me something and I will tell you where it comes from.", "We have not got that far: ask me something first, then I can say where it came from."]
_MUSE_LINES = ["Take your time. Ask whenever you like.", "Fair enough. I am here when you want to dig into it.", "No rush. Say the word if you want more on that.", "Mm. Tell me if you want me to look further."]
_DETAIL_LINES = ["That is everything I have on it here. The note itself has the rest: {links}.", "I have shown all of it that I can sum up. For the full text, open {links}."]
_DETAIL_NONE = ["That is all I have on it. Ask about a particular part and I will look.", "There is no more to add from my side. Name a detail and I will look for it."]


def _sources(history: list[dict] | None) -> list[str]:
    """The notes the last answer rests on, named as it names them: links, bold
    citations, "from your X note"."""
    said = _last_answer(history)
    names = [m.group(1) for m in _LINK.finditer(said)] + [m.group("t") or m.group("b") for m in _CITED.finditer(said)]
    return list(dict.fromkeys(n.strip() for n in names if n and n.strip()))


def _named(names: list[str]) -> tuple[str, str]:
    quoted = [f"“{n}”" for n in names[:3]]
    joined = quoted[0] if len(quoted) == 1 else ", ".join(quoted[:-1]) + " and " + quoted[-1]
    return joined, "note" if len(quoted) == 1 else "notes"


def _first_question(history: list[dict] | None) -> str:
    first = next((str(t.get("question") or "") for t in (history or []) if str(t.get("question") or "").strip()), "")
    return f"The earliest question I can see here is “{first.strip()}”." if first else "You have not asked me anything yet in this chat."


def _more_detail(said: str, history: list[dict] | None, seed: str) -> str:
    links = ", ".join(dict.fromkeys(m.group(0) for m in _LINK.finditer(_last_answer(history))))
    return _lead(_DETAIL_LINES, said, history, seed).format(links=links) if links else _lead(_DETAIL_NONE, said, history, seed)


def _about_sources(said: str, history: list[dict] | None, seed: str, lines: list[str], none: list[str]) -> str:
    """"Are you sure" and "where did you get that": the notes the answer rests on, named."""
    if not _last_answer(history):
        return _lead(_NOTHING_YET, said, history, seed)
    names = _sources(history)
    if not names:
        return _lead(none, said, history, seed)
    joined, noun = _named(names)
    return _lead(lines, said, history, seed).format(names=joined, note=noun)


def _react(said: str, history: list[dict] | None, seed: str) -> str | None:
    """A doubt, a musing or a question about where the answer came from, answered
    from the answer before; None when the text is none of these."""
    if _RE_FIRST.match(said):
        return _first_question(history)
    if _RE_DETAIL.match(said):
        return _more_detail(said, history, seed)
    if _RE_DOUBT.match(said):
        return _about_sources(said, history, seed, _SURE_LINES, _SURE_NONE)
    if _RE_SOURCE.match(said):
        return _about_sources(said, history, seed, _SOURCE_LINES, _SOURCE_NONE)
    return _lead(_MUSE_LINES, said, history, seed) if _RE_MUSE.match(said) else None


# --- a no -----------------------------------------------------------------------------------------

_NO = re.compile(rf"^(?:oh )?(?:no|nope|nah|no thanks|no thank you|no thank u|not now|not right now|not really|no need|no it'?s fine|it'?s fine|i'?m good|im good|maybe later|not today)(?:,? (?:thanks|thank you|it'?s fine|really))*{_END}")
_OFFER_LEAD = re.compile(
    r"^(?:shall i|should i|want me to|would you like me to|remind you|set a reminder|want a nudge|save it as|gather them|track your|note the|start a list|try one)\b", re.I
)
_DROPPED = ["No problem, I will leave it.", "All right, leaving it there.", "Fine by me. Ask whenever you like.", "Okay, no reminder then.", "Understood. It stays as it is."]
_DROPPED_OTHER = ["No problem, I will leave it.", "All right, leaving it there.", "Fine by me. Ask whenever you like.", "Understood. It stays as it is."]
_ACKED = ["All right.", "Okay. I am here if you need anything.", "No problem. Ask whenever you like.", "Sure thing. Just say if something comes up."]


def _offer_pending(history: list[dict] | None) -> str:
    lines = [ln.strip(" *_") for ln in _last_answer(history).splitlines() if ln.strip()]
    return lines[-1] if lines and lines[-1].endswith("?") and _OFFER_LEAD.match(lines[-1]) else ""


def declined(question: str, history: list[dict] | None, seed: str = "") -> str | None:
    """"No thanks" after an offer drops it, in one line and with no second offer; a
    "no" after an ack (a thanks, a feeling line) is no complaint about it. A "no"
    after an ordinary answer is left to the repair reader."""
    said = _clean(question)
    if not history or not _NO.match(said):
        return None
    if offer := _offer_pending(history):
        return _lead(_DROPPED if offer.lower().find("remind") >= 0 else _DROPPED_OTHER, said, history, seed)
    last = history[-1]
    asked = str(last.get("question") or "")
    if asked and not _last_answer(history).rstrip().endswith("?") and (social(asked, None) or _THANKS_ASK.match(_clean(asked).rstrip("?!. "))):
        return _lead(_ACKED, said, history, seed)
    return None


_THANKS_ASK = re.compile(r"^(?:ok(?:ay)?|thanks?|thank you|ty|cheers|thx|cool|great|nice|got it|noted|perfect|lovely|good|alright|all right)(?: (?:thanks|thank you|a lot|so much|mate))*$")


#: The state people give back to "how are you getting on?" (F13 k): heard as the
#: answer it is, not as a thanks ("fine thanks" got "My pleasure").
_STATE = re.compile(
    r"^(?:i(?:'m| am) |im |not |pretty |quite |really |very |so )*(?P<what>fine|good|great|well|ok|okay|alright|not bad|tired|busy|stressed|knackered|exhausted|bored|rough|so so|could be better|can't complain)"
    r"(?: (?:today|so far|at the moment|really))?(?: (?:thanks|thank you|ty|and you|you))*$"
)
_STATE_GLAD = {"fine", "good", "great", "well", "ok", "okay", "alright", "not bad", "can't complain"}
_STATE_GLAD_LINES = ["Good to hear. Anything you want to jot down or find?", "Glad to hear it. What shall we look at?"]
_STATE_HARD_LINES = ["Sorry, {what} is no fun. Want me to pull out just one small thing to start with?", "That sounds like a lot. I can keep it to one task if that helps."]


def answered_how(question: str, history: list[dict] | None, seed: str = "") -> str | None:
    """A reply to the "how are you getting on?" this app just asked."""
    if not history or not any(_last_answer(history).startswith(line) for line in _HOW_LINES_ASKING):
        return None
    said = _clean(question).rstrip("?!. ")
    found = _STATE.match(said)
    if not found or len(said.split()) > 8:
        return None
    what = found.group("what")
    lines = _STATE_GLAD_LINES if what in _STATE_GLAD else _STATE_HARD_LINES
    return _lead(lines, said, history, seed).format(what=what)


def reply(question: str, history: list[dict] | None, seed: str = "") -> str | None:
    """Whatever the readers make of this turn, or None to search."""
    return answered_how(question, history, seed) or declined(question, history, seed) or meta(question, history, seed) or compare(question, history, seed) or social(question, history, seed) or reaction(question, history, seed)


def reaction(question: str, history: list[dict] | None, seed: str = "") -> str | None:
    said = _clean(question).rstrip("?!. ")
    return _react(said, history, seed) if said and len(said.split()) <= 8 else None


def feeling_subject(question: str) -> str:
    """"the exam" in "i'm stressed about the exam", for a chip; "" when none."""
    found = _FEEL.match(_clean(question).rstrip("?!. ")) or _MISS.match(_clean(question).rstrip("?!. "))
    return (found.groupdict().get("about") or found.groupdict().get("who") or "").strip() if found else ""
