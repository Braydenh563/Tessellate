"""The Guide's lines for questions outside the app, with no model (L-chat-38).

The owner, 2026-11-13: "respond like a chatbot with the composer when an ai
model isnt there". The world's questions ("what's the weather", "how do I cook
rice?") get one honest line instead of the open tab's blurb or a "Did you
mean" menu of topics that share a stray word; a sum is worked out; "are you an
AI?" is answered. Moved out of `help_chat` whole (its line cap); it reads only
the topic table and the leaf word helpers, so it sits below `help_chat`.
"""

from __future__ import annotations

import functools
import re

from tessellate.ai import AI_NAME, guide_lead
from tessellate.ai.help_topics_core import HELP_TOPICS

#: How-to forms that are about the app whatever else they name.
HOW_TO_APP = re.compile(r"^\s*(?:how (?:do|can|should|would|to)|where (?:do|can|is|are)|can i|is there a way|what can i do|what does|why (?:is|does|can't|won't))\b|^\s*help(?: me)?[\s?.!]*$", re.I)


#: A request for writing or a performance, never a question about the app.
CREATIVE = re.compile(r"^\s*(?:please\s+)?(?:tell me (?:a|an|some) \w+|write|compose|draft|sing|recite|translate|give me (?:a|an) \w+|make me (?:a|an) \w+)\b", re.I)


#: The help's own words, as stems: a how-to that shares none of them is about
#: the world ("how do I cook rice?"), not the open tab (L-chat-38).
_WORLD_SKIP = frozenset(
    "how do does did can could should would will to i we you me my it a an the of for in on at with and or "
    "make get go put take be is are way best good some any".split()
)


@functools.lru_cache(maxsize=1)
def help_stems() -> frozenset[str]:
    words: set[str] = set()
    for topic in HELP_TOPICS:
        words.update(guide_lead._stems(f"{topic['body']} {' '.join(topic['keywords'])}"))
    return frozenset(words)


def world_how_to(question: str) -> bool:
    """A how-to whose every word but the asking ones is foreign to the help."""
    found = HOW_TO_APP.match(question)
    if not found:
        return False
    rest = [w for w in guide_lead._stems(question[found.end():]) if w not in _WORLD_SKIP]
    return bool(rest) and not any(w in help_stems() for w in rest)


#: "are you an AI?", "is this a bot?", "am I talking to a person?" (L-chat-38).
WHAT_ARE_YOU = re.compile(
    r"^\W*(?:are you|is (?:this|atlas|it)|am i (?:talking|speaking|chatting) (?:to|with)) (?:an? |the |real |actual )*"
    r"(?:ai|a\.i\.?|bot|robot|chat ?bot|human|person|real person|machine|llm|language model|computer|program)\W*$",
    re.I,
)
WHAT_ARE_YOU_REPLY = (
    f"I'm {AI_NAME}, the app's guide, and I'm software, not a person. My answers come from "
    "Tessellate's own help: where a feature lives, what a setting does and how to do something."
)


#: A sum asked as one ("what is 2+2", "12 x 3"): worked out, not a miss (L-chat-38).
_SUM = re.compile(
    r"^\W*(?:what(?:'s| is)|calculate|work out|compute)?\s*(-?\d{1,12}(?:\.\d{1,6})?)\s*([-+*/x×÷])\s*(-?\d{1,12}(?:\.\d{1,6})?)\s*[=?.!]*\s*$",
    re.I,
)
_SIGN = {"+": "+", "-": "-", "*": "×", "x": "×", "X": "×", "×": "×", "/": "÷", "÷": "÷"}
_WEATHER = re.compile(r"\b(?:weather|forecast|temperature|raining|rain|snow|news|headlines?)\b", re.I)
OUTSIDE_REPLY = "That is outside the app: I only know Tessellate's own help{why}. Ask me how something here works, or browse Settings, Help."


def worked_sum(question: str) -> str | None:
    found = _SUM.match(question)
    if not found:
        return None
    a, sign, b = float(found.group(1)), _SIGN[found.group(2)], float(found.group(3))
    if sign == "÷" and b == 0:
        return None
    value = {"+": a + b, "-": a - b, "×": a * b, "÷": a / b if b else 0.0}[sign]
    said = f"{round(value, 6):g}" if abs(value) < 1e15 else f"{value:.6g}"
    return f"{found.group(1)} {sign} {found.group(3)} is {said}."


def about_the_world(question: str) -> bool:
    """The world's questions and requests, not an injection or the person's own
    record; "where do they show up" with nothing before it is a miss, not the world."""
    from tessellate.ai import personal

    return bool(CREATIVE.match(question) or _WEATHER.search(question) or world_how_to(question) or (personal.general(question) and not guide_lead._PRONOUN.search(question)))


def outside_reply(question: str) -> str:
    """One line for the world's questions: what the Guide is, and where to go next."""
    if CREATIVE.match(question):
        why = ", so jokes, poems and stories are beyond me"
    elif _WEATHER.search(question):
        why = ", so I can't see the weather or the news"
    else:
        why = ""
    return OUTSIDE_REPLY.format(why=why)


def summed(question: str) -> dict | None:
    """A sum's reply in `offline_answer`'s shape, or None."""
    said = worked_sum(question)
    return None if said is None else {"content": said, "badges": [], "sources": [], "social": True}
