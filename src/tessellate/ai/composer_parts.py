"""Replies composed from parts (O5; INBOX 904 B07, the owner: replies should
vary and feel alive, not be a stored line said whole).

A hello, a thanks and a goodbye were 19, 18 and 18 stored sentences a voice;
a person who says "thanks" a dozen times in a session heard the same few. Each
is now a head (the greeting word, "You are welcome.", "Take care.") and a tail
(the offer, the reassurance), chosen as a pair, so ten heads and ten tails say
a hundred and ten different things, every one of them reading as a sentence
somebody would say. `SOCIAL` holds the pairs and `phrasing.choose` picks one
unlike the last three replies, exactly as it picks a stored line, so nothing
else in the route moved. Every head ends on a full stop and every tail starts
with a capital, so any pair joins.
"""

from __future__ import annotations

import re

_SENTENCES = re.compile(r"(?<=[.?])\s+")

#: Per voice and kind: (heads, tails). No head asks; a tail may.
PARTS: dict[str, dict[str, tuple[tuple[str, ...], tuple[str, ...]]]] = {
    "natural": {
        "greeting": (
            (
                "Hello.",
                "Hi there.",
                "Hey.",
                "Hello again.",
                "Hi.",
                "Greetings.",
                "Hey there.",
                "Hi again.",
                "Hello, good to see you.",
                "Hey, I'm ready.",
            ),
            (
                "What would you like to find in your notes?",
                "Ask me anything about your notes and I will answer from what you wrote.",
                "I can tell you when something is, what you decided, or what the latest is on a project.",
                "What is on your mind?",
                "What can I look up for you today?",
                "Just let me know what you need from your records.",
                "Your notes are all here, so ask away.",
                "Want to look something up?",
                "I'm here whenever you want to look something up, plan the day or tidy a few notes.",
                "What should we search for?",
            ),
        ),
        "thanks": (
            (
                "You are welcome.",
                "Glad that helped.",
                "Happy to help.",
                "No problem at all.",
                "Any time.",
                "My pleasure.",
                "You got it.",
                "Sure thing.",
                "Glad to help.",
                "You bet.",
                "Of course.",
                "Not a problem.",
            ),
            (
                "Anything else?",
                "What else can we find?",
                "Ask again whenever you need something from your notes.",
                "Let me know if you need more.",
                "If anything else comes up, just ask and I'll dig it out of your notes.",
                "What's next?",
                "Anything more you want to check?",
                "Ask away whenever you like.",
                "Your notes are right here if you need them.",
                "I can look something else up if you like.",
            ),
        ),
        "bye": (
            (
                "Bye for now.",
                "See you soon.",
                "Take care.",
                "Goodbye.",
                "Catch you later.",
                "Farewell.",
                "Talk soon.",
                "See you next time.",
                "Until next time.",
                "Have a good one.",
                "Take it easy.",
                "Off you go then.",
            ),
            (
                "Your notes will be here.",
                "Everything you wrote is saved.",
                "Feel free to return when you need me.",
                "I'll keep your notes safe.",
                "Come back whenever you need to check something.",
                "Your notes aren't going anywhere.",
                "I'll be here if you need me.",
                "Good luck with the rest of your day.",
                "Let me know if you need anything else later.",
                "Nothing you wrote is lost while you're away.",
                "Is there anything you want to look up before you go?",
                "Everything you wrote is saved on this device, and it will all be here whenever you come back.",
            ),
        ),
    },
    "professional": {
        "greeting": (
            (
                "Hello.",
                "Good day.",
                "Welcome back.",
                "Hello again.",
                "Greetings.",
                "Hi.",
                "Welcome.",
                "Good to see you.",
                "Hi again.",
                "Hello there.",
            ),
            (
                "How may I help you with your notes?",
                "What would you like to look up in your notes?",
                "I can answer questions from what you have recorded.",
                "What would you like to review?",
                "Your notes are all here and ready to search.",
                "What can I find for you?",
                "Ask me anything about your notes.",
                "How may I assist?",
                "What are we looking for today?",
                "Please ask whenever you are ready.",
            ),
        ),
        "thanks": (
            (
                "You are welcome.",
                "Certainly.",
                "Glad to be of help.",
                "Of course.",
                "My pleasure.",
                "Not at all.",
                "Happy to help.",
                "You are most welcome.",
            ),
            (
                "Is there anything else you would like to review?",
                "Please ask again whenever you need something from your notes.",
                "Please ask whenever you need something further.",
                "Let me know if you need anything more.",
                "I am available whenever you need to look something up.",
                "What else would you like to review?",
                "Your notes remain available.",
                "Please continue whenever you are ready.",
            ),
        ),
        "bye": (
            (
                "Goodbye.",
                "Until next time.",
                "Thank you, and goodbye for now.",
                "Have a good day.",
                "Farewell.",
                "Take care.",
                "Good day.",
                "Thank you.",
            ),
            (
                "Your notes remain saved.",
                "Everything you recorded is saved.",
                "Your notes and reminders are saved.",
                "I will be available whenever you return.",
                "Please return whenever you need me.",
                "Nothing you recorded will be lost.",
                "Your records will be here when you return.",
                "Please ask again whenever you need something.",
                "Your notes and reminders are kept safe, and I will be here whenever you wish to return to them.",
            ),
        ),
    },
}


def lines(voice: str) -> dict[str, tuple[str, ...]]:
    """Every reply the parts of `voice` can make, per kind: each head alone,
    then each head with each tail."""
    out: dict[str, tuple[str, ...]] = {}
    for kind, (heads, tails) in PARTS[voice].items():
        out[kind] = (*heads, *(f"{head} {tail}" for head in heads for tail in tails))
    return out


def repeats_tail(line: str, recent) -> bool:  # noqa: ANN001
    """Whether `line` ends on a sentence one of `recent` ended on (a line of
    one sentence has no tail to repeat)."""
    sentences = _SENTENCES.split(line)
    if len(sentences) < 2:
        return False
    return any(_SENTENCES.split(r)[-1] == sentences[-1] for r in recent if r)
