"""Turns put to the assistant itself, or said to end or begin a chat, in other people's words.

CLINC150's small-talk intents (CC BY 3.0, `tests/fixtures/composer/SOURCES.md`) showed the
reply was a notes search for anything the phrase tables did not hold: "what's your full
name" was looked up in the notes, "it was nice chatting with you" answered with "I did
not catch what it was after". A turn is the assistant's own when it speaks to "you" about
what the assistant is (its name, age, boss, kind), thanks it, greets it or says goodbye in
a short message that points at no note: `kind` names which of the stored families
answers it. Free of project imports so `question_noise` can ask it first.
"""

from __future__ import annotations

import re
from tessellate.core.lazyre import lazy_compile

#: What makes a message about the person's own notes, whatever else it says.
_NOTE_ANCHOR = lazy_compile(r"\b(?:my|mine|notes?|wrote|written|saved|noted|reminders?|todo|entries|entry|last (?:week|month)|yesterday)\b")
#: A question that wants something found, not a remark to the assistant.
_WANTS_FOUND = lazy_compile(r"\b(?:what|when|where|which|who|how many|how much)\b")

_ATTRIBUTE = r"(?:name|age|birthday|birth ?date|boss|employer|employeer|manager|supervisor|creator|maker|owner|parents?|gender|company)"
_SELF = lazy_compile(
    rf"\b(?:your|ur) (?:(?:full|real|first|last|actual|legal) )?{_ATTRIBUTE}\b"
    r"|\bhow (?:old|many (?:years|months|days|weeks) old) (?:are|r) (?:you|u)\b|\bhow old you (?:are|r)\b|\byou (?:are|r|re) how old\b"
    r"|\bhow (?:old|long ago) (?:were|was) (?:you|u) (?:born|made|created|built)\b|\bwhen (?:were|was|did) (?:you|u) (?:born|made|created|built)\b|\bwhen (?:you|u) (?:were|was) (?:born|made|created|built)\b"
    r"|\b(?:who|what) (?:made|created|built|programmed|designed|trained|owns|employs|gave) (?:you|u|your)\b"
    r"|\b(?:you|u|ya)(?: \w+){0,3} (?:work|works|working|toil|employed)\b(?! (?:out|on|with|it|well|properly)\b)"
    r"|\bwork(?:s|ing)? for (?:you|u)\b|\b(?:do|did) (?:you|u) have (?:another |a )?job\b"
    r"|\b(?:(?:are|r) (?:you|u)|you (?:are|r|re)) (?:really |actually |just )?(?:an? )?(?:real |actual )?(?:person|human|human being|bot|robot|ai|machine|computer)\b"
    r"|\bwhen (?:did|do) (?:you|u) (?:come to )?exist\b|\bwhat age (?:is|are) (?:the ai|you|u|atlas)\b|\bhow long (?:have|has) (?:you|u|the ai) been (?:around|on|alive|here|working|running)\b|\bhow many years have (?:you|u) been\b"
    r"|\bwhat name (?:do|would|did) (?:you|u)\b|\bwhen did (?:your|ur) (?:training|learning|education) (?:finish|end|stop|start|begin)\b"
    r"|\b(?:consider|classify|classified|categori[sz]e|categori[sz]ed|call)\b.*\b(?:yourself|you|u)\b.*\b(?:bot|human|robot|ai|person|computer|machine)\b"
    r"|\bhuman or (?:a )?(?:computer|machine|bot|robot|ai)\b|\byourself\b.{0,24}\b(?:bot|human|robot|ai|person)\b"
    r"|\b(?:call|refer to|address) (?:you|u)\b|\byour attention\b"
)
_QUESTION_FRAME = lazy_compile(r"^(?:what|who|how|is|are|do|does|did|can|could|should|would|tell|please|provide|which|for|don't|i|ai|atlas|hey|and|so|may|your|you|when)\b")
_THANKS = lazy_compile(r"\b(?:thank you|thanks|thankyou|much obliged|many thanks|gratitude|i appreciate|appreciated)\b")
_BYE = lazy_compile(
    r"\b(?:good ?bye|talk to you (?:later|soon)|(?:nice|great|good|lovely|a pleasure) to (?:have|had) (?:this|our|a) (?:conversation|chat)|see you (?:soon|later|around|next time|tomorrow)|say goodbye|goodbye|"
    r"(?:was|been|is) (?:so |really )?(?:nice|great|enjoyable|lovely|good|a pleasure)(?: to)? (?:chat|chatting|talk|talking|speak|speaking)|"
    r"(?:nice|good|great) (?:chatting|talking|speaking)|later,? (?:gator|alligator)|sayonara|syonara|adios|farewell|until next time|catch you later|"
    r"glad we got to talk)\b"
)
_HOW = lazy_compile(r"\bhow(?:'?s| is| are) (?:everything|things|you)\b|\bis everything (?:going )?(?:okay|ok|good|fine|alright|well)\b")
_HELLO = lazy_compile(r"^(?:(?:why|well|oh) )?(?:hello|hi|hey)(?: there)?$|^(?:ahoy|ello|g'?day|greetings|salutations|howdy)\b")
#: "tell me a joke about cats" stays a notes question first (C31: "tell me a joke about the scarecrow" is the saved one).
_JOKE = lazy_compile(r"\b(?:tell|say|hear|give|crack|share|recite|know|got|make)\b.*\b(?:jokes?|something funny|one liners?|giggle|laugh|smile)\b(?! about\b)|^what(?:'s| is) a (?:good |funny )?joke$|^what (?:funny |good )?jokes do you know$")


def _words(message: str) -> str:
    return " ".join(re.split(r"[^\w']+", (message or "").lower())).strip()


def kind(message: str) -> str | None:
    """The stored reply family for a turn that is the assistant's own, else None."""
    text = re.sub(r"\bmy (?:friend|dear|man|love|lad|dude|good friend)\b", " ", _words(message))
    words = text.split()
    #: "no thanks" declines; it does not thank.
    if not 1 < len(words) <= 12 or _NOTE_ANCHOR.search(text) or text.startswith(("no thank", "nope thank", "nah thank")):
        return None
    if _SELF.search(text) and _QUESTION_FRAME.match(text):
        return "who"
    for name, pattern in _SHORT:
        if pattern.search(text) and (name == "joke" or not _WANTS_FOUND.search(text)):
            return name
    return None


_SHORT = (("bye", _BYE), ("thanks", _THANKS), ("how", _HOW), ("greeting", _HELLO), ("joke", _JOKE))
