"""The app's social replies with no model: `SOCIAL`, greetings and thanks,
the invitation after them, and a call to the app by name.

Moved whole from `composer.py` (audit AR3, gods-1101): the code is unchanged,
and `composer` re-exports every name here that anything reads, so
`composer.social` still works. Imports run one way, down
the layer list in `composer.py`'s docstring, never back to `composer`.
"""

from __future__ import annotations

import hashlib
import re

from tessellate.ai import composer_compose, composer_lines, composer_parts, composer_replies, composer_tables, phrasing, question_noise
from tessellate.ai.composer_answer import _SESSION
from tessellate.ai.composer_ask import subject_terms
from tessellate.ai.composer_body import _asked_span
from tessellate.ai.composer_quote import _pick


# --- small talk, in the app's own voice ----------------------------------------

#: What the composer says to "hi", "thanks", "how are you", "bye" and "what
#: can you do" when no model is running (INBOX 741, the owner: "more social,
#: more engaging"). Warm and brief, Atlas's voice by default (CHAT_PLAN
#: decision 26); each kind has several, chosen by the message, so the same
#: greeting twice in a row is not answered word for word the same. Nothing
#: here says anything about the notes: these are the app's own words.
SOCIAL: dict[str, tuple[str, ...]] = {
    "morning": (
        "Good morning. What would you like to look up?",
        "Morning. Your notes are ready when you are.",
        "Morning. Ask me about anything you have jotted down.",
    ),
    "how": (
        "All good here, and your notes are in order. What can I find for you?",
        "Doing well, thanks for asking. What would you like to know?",
        "Fine, thank you. Anything you want to look up?",
        "Everything is excellent. How can I assist you with your notes?",
        "I am well, thanks. Let's dig into your records.",
    ),
    "sorry": (
        "No need to apologise. What would you like to try?",
        "Not at all. Ask it another way and I will look again.",
        "It's completely fine. What can I do for you?",
        "Don't worry about it. Let's try again.",
        "That's okay. What are you looking for?",
        "It is no trouble. Let me know what you need.",
        "All good. Let's find what you need in your notes.",
    ),
    "laugh": (
        "Glad something made you smile. Anything else I can find?",
        "Ha. What next?",
        "Good to hear. Ask whenever you like.",
        "Haha, very nice. What should we look up now?",
        "Glad you found that funny. Ready for the next question?",
        "Heh. Let me know if you need to search anything else.",
    ),
    "reaction": (
        "I know. Anything you want to look up about it?",
        "Quite something. What next?",
        "Fair reaction. Want me to find anything else?",
        "Absolutely. Shall we search for something else?",
        "Totally. Let me know what to look up.",
        "Understood. Anything more to check?",
        "I hear you loud and clear. What next?",
        "Indeed. Let me know if you have another question.",
    ),
    "confused": (
        "Sorry, that was not clear. Ask it another way, or say “tell me more” for the rest of what I found.",
        "Let me try again: put it in other words, or name the note you mean.",
        "My answer may have missed. Which part should I look at again?",
        "Apologies, I didn't get that. Mind rephrasing your question?",
        "I seem to be a bit confused. Can you try asking in a different way?",
        "I'm not quite following. Can you tell me exactly what note to look for?",
        "Could you clarify? Let's try searching one more time.",
    ),
    "ack": (
        "Good. Anything else?",
        "All right. What next?",
        "Noted. Ask whenever you like.",
        "Got it. What else can I find?",
        "Understood. Ready when you are.",
        "Okay. Let me know if you need more.",
        "Acknowledged. Let's move on to the next search.",
        "Sure thing. What is next on the list?",
    ),
    "who": (
        "I am the notebook's assistant. With no model running I answer from your notes in their own words.",
        "I am here to find things in your notes and say what they say.",
        "I am a search assistant designed to retrieve exactly what you have written in your notes.",
        "I am your dedicated notebook assistant. Ask a question and I'll find it in your records.",
    ),
    "about_app": (
        "I answer from your notes: ask when something is, who said what, what the latest is on a project, or what you know about a subject. Connecting a model adds writing, summaries in its own words and tools.",
        "Ask me about anything you wrote down: a date, a decision, a list, how a project is going. Two questions in one message work too. Connecting a model adds writing and tools.",
        "I'm built to read your notes and report back exactly what you recorded. Try asking about a specific event or task.",
        "I help you comb through your notes without needing to summarize them. Ask me when something happened or who said what.",
    ),
    "joke": (
        "I have no jokes of my own: I only say what is in your notes. If you saved one, ask me for it.",
        "Jokes are not something I make up. If one of your notes has a good one, I can find it.",
    ),
    "unclear": (
        "I could not read that one. Ask about a note, a date or a list, or say what you want to do.",
        "That did not read as words to me. What would you like to find?",
    ),
    "compliment": (
        "I am glad to hear that. What can I find for you next?",
        "That's kind of you. What else should we search for?",
        "Much appreciated. Anything else in your notes to find?",
        "Glad I could be of service. Let me know what else you need.",
    ),
    "insult": (
        "Apologies. Let's try rephrasing the question.",
        "My apologies. I will try to get it right next time.",
        "I am sorry if I let you down. How can I improve this search?",
        "Sorry about that. Could you try asking in a different way?",
        "My bad. I'm limited to exact matches in your notes, so try a different wording.",
        "Apologies for the frustration. What should we look for instead?",
    ),
    "emotion": (
        "I understand. What can I help you find?",
        "Okay. I am here when you need to search your notes.",
        "I hear you. Take your time, and let me know what you need.",
        "Got it. Whenever you are ready, I can search your notes.",
        "I'm sorry to hear that. What can I look up for you?",
        "That's totally fair. Let's focus on what we can find in your notes.",
        "Understood. I am here to assist with any searches you need.",
        "I can imagine. Let me know what you want to review in your notes.",
    ),
}


for _kind, _more in composer_tables.SOCIAL_NATURAL_EXTRA.items():
    SOCIAL[_kind] = SOCIAL[_kind] + _more


SOCIAL_PROFESSIONAL = composer_tables.SOCIAL_PROFESSIONAL


#: **The engine is Atlas** (CHAT_PLAN decision 36; the owner: "Composer
#: doesn't know it is atlas"): who it is and what it does are said in its
#: name, in both voices, with no model and with one.
SOCIAL["who"] = (
    "This is Atlas's assistant speaking. With no model running I answer from your notes in their own words.",
    "Atlas's assistant, that's me. I find things in your notes and say what they say.",
    "Atlas's assistant, at your service: I answer from your notes, and to talk to Atlas itself you can connect a model.",
    "Think of me as Atlas's assistant: ask me when something is, what you decided or what you did last week.",
)


SOCIAL["about_app"] = (
    "I'm Atlas's assistant. I answer from your notes: when something is, who said what, what the latest is on a project. "
    "I also set reminders, tag, pin and move notes, and work out sums and conversions. Connecting a model adds writing in its own words.",
    "Atlas's assistant here. Ask about anything you wrote down: a date, a decision, a list, how a project is going or what you did "
    "last week. Say \"remind me to...\" and I set it. Connecting a model adds writing and tools.",
    "I'm Atlas's assistant, and I read your notes for you: ask when something happened or who said what, or tell me to pin, tag or delete a note.",
)


#: Eight phrasings or more in every family, of more than one shape
#: (`composer_replies`; the owner: "can it have more varied responses??").
for _kind, _more in composer_replies.SOCIAL_NATURAL.items():
    SOCIAL[_kind] = SOCIAL.get(_kind, ()) + _more


for _kind, _more in composer_replies.SOCIAL_PROFESSIONAL.items():
    SOCIAL_PROFESSIONAL[_kind] = SOCIAL_PROFESSIONAL.get(_kind, ()) + _more


#: A hello, a thanks and a goodbye are a head and a tail chosen as a pair
#: (`composer_parts`), not a stored line said whole.
SOCIAL.update(composer_parts.lines("natural"))


SOCIAL_PROFESSIONAL.update(composer_parts.lines("professional"))


_SOCIAL_KIND = (
    ("morning", re.compile(r"\bgood (?:morning|afternoon|evening|day)\b|^morning\b", re.I)),
    ("thanks", re.compile(r"\b(?:thanks?|thank you|ta|cheers|nice one|appreciated?)\b", re.I)),
    ("how", re.compile(r"\bhow(?:'?s| is| are)(?: it going| things| you|you)\b|\bwhat'?s up\b|\bare you (?:ok|okay|there|awake|alive)\b", re.I)),
    ("bye", re.compile(r"\b(?:bye|goodbye|good night|night|see (?:ya|you)|later|cya)\b|\bthat'?s all\b|\bleave it there\b|\bcall it a day\b", re.I)),
    ("sorry", re.compile(r"\b(?:sorry|my bad)\b", re.I)),
    ("who", re.compile(r"\bwho are you\b|\byour name\b|\bare you (?:an? )?(?:ai|bot|robot|human|real|person|real person)\b", re.I)),
    ("greeting", re.compile(r"^\W*(?:hi|hey|hello|hiya|yo|sup|howdy)\b", re.I)),
    ("joke", re.compile(r"\b(?:joke|jokes|something funny|make me laugh)\b", re.I)),
    ("unclear", re.compile(r"^\W*\w*(?:asdf|sdfg|dfgh|fghj|ghjk|hjkl|qwer|wert|erty|rtyu|tyui|yuio|uiop|zxcv|xcvb|cvbn|vbnm|fdsa|lkjh|poiu|rewq)\w*\W*$", re.I)),
)


#: The kinds of turn after which the reply may offer the next step on what
#: was being talked about ("Say “tell me more” for more on “sync rewrite”.").
_NEXT_STEP_KINDS = ("ack", "thanks", "laugh", "reaction")


NEXT_STEPS = (
    "Say “tell me more” for more on “{subject}”.",
    "I can say more about “{subject}” if you like.",
    "Want the latest on “{subject}” next?",
    *composer_tables.NEXT_STEPS_EXTRA,
)


NEXT_STEPS_PROFESSIONAL = composer_tables.NEXT_STEPS_PROFESSIONAL


#: **A greeting composed from parts, one of them the person's own** (O5;
#: INBOX 904 B07, the owner: replies should vary and feel alive; CHAT_PLAN
#: decision 76's rundown is composed the same way). After a stored opener, a
#: hello, a test or an unclear turn gets an invitation built on a word of
#: the newest note (`invite`, the route's), so the same "hi" reads
#: differently as the notebook changes, and the ask it offers is one the
#: notes answer.
_INVITE_KINDS = ("greeting", "morning", "test", "unclear")


INVITES = {
    "natural": (
        "Your newest note mentions {subject}: ask “what did I write about {subject}” to pick up from there.",
        "Lately you've been writing about {subject}; ask me “what did I write about {subject}” to pick that back up.",
        "Your last note was about {subject}, so ask “what did I write about {subject}” to start there.",
        "Picking up where you left off: ask “what did I write about {subject}”.",
        "The last thing you wrote touched on {subject}. Ask me “what did I write about {subject}” and I'll find the notes.",
        "If it helps, ask me “what did I write about {subject}” and I will bring back your newest note.",
        "Your notes most recently turned to {subject}; ask me “what did I write about {subject}” and I'll go through them with you.",
        "Carry on from your latest note: ask “what did I write about {subject}”.",
    ),
    "professional": (
        "The most recent note concerns {subject}; ask “what did I write about {subject}” to review it.",
        "The latest entry mentions {subject}; ask “what did I write about {subject}” to bring up the notes.",
        "Your most recent entry refers to {subject}; ask “what did I write about {subject}” to review it.",
        "To continue, ask “what did I write about {subject}”.",
        "The newest note relates to {subject}; ask “what did I write about {subject}” to return to it.",
        "Recent entries mention {subject}; ask “what did I write about {subject}” to retrieve them.",
        "To see the most recent entry, ask “what did I write about {subject}”.",
        "The last entry recorded was about {subject}; ask “what did I write about {subject}” to see it.",
    ),
}


def social_kind(message: str, intent: str = "smalltalk") -> str:
    """The kind of conversational turn `message` is: one of `SOCIAL`."""
    if intent == "about_app":
        return "about_app"
    from tessellate.ai import intent as intent_module

    if intent_module.is_mash(message):
        return "unclear"
    if intent_module.is_test(message):
        return "test"
    return question_noise.social_kind(message) or next(
        (name for name, pattern in _SOCIAL_KIND if pattern.search(message or "")), "ack"
    )


def social(
    message: str,
    intent: str = "smalltalk",
    previous: str = "",
    last_question: str = "",
    voice: str = composer_tables.DEFAULT_VOICE,
    recent: list[str] | tuple = (),
    seed: str = "",
    invite: str = "",
) -> str:
    """The app's reply to a conversational turn with no model running (INBOX
    741: "any and all conversational messages"): warm, short, of the turn's
    kind, opening unlike any of the last three replies (`recent`, oldest
    first; `previous` alone when that is all there is) and shaped unlike the
    last (`phrasing.choose`), and after an acknowledgement or thanks, a next
    step on what was being talked about. `seed` is the conversation's: the
    same seed and turns give the same words. `invite` is a word of the
    newest note: a hello, a test or an unclear turn ends on an ask about it
    (`INVITES`) when its opener offered none."""
    #: A repair is worded by the route, which has the turn before
    #: (`composer_social.repair`); anywhere else it is confusion.
    kind = social_kind(message, intent).replace("repair", "confused")
    line = _social_line(message, kind, previous, last_question, voice, recent, seed)
    if invite and kind in _INVITE_KINDS and "“" not in line and not line.endswith("?"):
        line = f"{line} {invitation(message, invite, voice, seed)}"
    return line


def invitation(message: str, subject: str, voice: str, seed: str) -> str:
    """The invitation built on a word of the newest note (`INVITES`)."""
    said = "professional" if composer_tables.voice_of(voice) == "professional" else "natural"
    return _pick(f"{message}|{subject}", f"invite:{seed}", list(INVITES[said])).format(subject=subject)


def greeting_ask(message: str, voice: str, seed: str) -> str:
    """A plain offer to end a welcome that already names the last note (the
    invitation would say it twice, audit 1030 Z51)."""
    mood = composer_compose.voice_for(composer_tables.voice_of(voice))
    pool = [x.text for x in composer_lines.SOCIAL_TAILS["*"] if not x.emotions and mood in x.voices and x.text.endswith("?")]
    return _pick(message, f"greeting_ask:{seed}", pool) if pool else ""


def _social_line(message: str, kind: str, previous: str, last_question: str, voice: str, recent, seed: str) -> str:  # noqa: ANN001
    """The stored opener of `kind`, and a next step after an acknowledgement."""
    recent = [r for r in recent if r] or ([previous] if previous else [])
    professional = composer_tables.voice_of(voice) == "professional"
    if f"social_{kind}" in composer_lines.FRAMES:
        #: Composed in the voice and mood of the turn (CHAT_PLAN 1353).
        mood = composer_compose.mood_of(message, voice=voice, seed=f"{seed or _SESSION.get()}|{message}")
        line = phrasing.choose(composer_compose.eligible(f"social_{kind}", mood), f"social:{kind}:{message}", recent, seed or _SESSION.get())
    else:
        line = _stored_social(message, kind, professional, recent, seed)
    subject = _talked_about(last_question)
    if kind in _NEXT_STEP_KINDS and subject and len(subject) <= 40:
        line = f"{line} {_next_step(line, message, subject, professional)}"
    return line


def _talked_about(last_question: str) -> str:
    """What the turn before asked about, for a next step, or "" when it asked
    nothing of the notes: "fuck" after "yooooo" once offered more on
    “yooooo” (INBOX 1459). Whether its notes matched is the caller's to
    say: the chat passes `last_question` only for a turn that named notes."""
    from tessellate.ai import intent as intent_module

    if not last_question or intent_module.classify(last_question) != intent_module.NOTES:
        return ""
    return _asked_span(last_question, subject_terms(last_question))


def social_surfaces(kind: str, professional: bool = False) -> list[str]:
    """Every line `social` can say for `kind`: the stored ones, and for the
    kinds the composition layer words every sentence it can build."""
    built = [x.text for x in composer_compose.surfaces(f"social_{kind}")] if f"social_{kind}" in composer_lines.FRAMES else []
    return [*(SOCIAL_PROFESSIONAL if professional else SOCIAL)[kind], *built]


def _stored_social(message: str, kind: str, professional: bool, recent: list[str], seed: str) -> str:
    lines = (SOCIAL_PROFESSIONAL if professional else SOCIAL)[kind]
    #: A composed line never ends on a sentence one of the last few ended on.
    lines = [x for x in lines if not composer_parts.repeats_tail(x, recent[-phrasing.RECENT:])] or lines
    return phrasing.choose(lines, f"social:{kind}:{message}", recent, seed or _SESSION.get())


def _next_step(line: str, message: str, subject: str, professional: bool) -> str:
    """Never two questions back to back: after a line that asks, the next
    step is said, not asked."""
    steps = [n for n in (NEXT_STEPS_PROFESSIONAL if professional else NEXT_STEPS) if not (line.endswith("?") and n.endswith("?"))]
    return _pick(f"{message}|{subject}", "social:next", steps).format(subject=subject)


def call(names: list[str] | str, recent: list[str] | tuple = (), seed: str = "", voice: str = composer_tables.DEFAULT_VOICE) -> str:
    """The reply to a message that only called the assistant ("yo
    brotatockiibidyrizzler", `vocative.py`): here, and what it can do. A
    line that says the name back is one of several, so a nickname is
    acknowledged now and then, never every time, and never "Ha" at its own
    name."""
    name = names if isinstance(names, str) else (names[0] if names else "")
    lines = composer_replies.CALL[composer_tables.voice_of(voice)]
    own = name.lower() in ("atlas", "")
    usable = [line for line in lines if "{name}" not in line or not (own and line.startswith("Ha"))]
    if not name:
        usable = [line for line in usable if "{name}" not in line]
    line = phrasing.choose(usable, f"call:{name}", [r for r in recent if r], seed or _SESSION.get())
    return line.replace("{name}", name[:1].upper() + name[1:])


def call_asks(seed: str = "", count: int = 3) -> list[str]:
    """What a call offers next: `count` of `composer_replies.CALL_ASKS`,
    a different few for a different conversation."""
    asks = list(composer_replies.CALL_ASKS)
    start = int(hashlib.sha1(f"asks|{seed}".encode()).hexdigest(), 16) % len(asks)
    return [asks[(start + i) % len(asks)] for i in range(count)]
