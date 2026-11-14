"""Out-of-domain answers (CHAT_PLAN step 11, U18, A25): a question neither the
notes nor the app can answer is told so plainly, a note it shows is called the
closest, and one line says what the app can do (generated from the act
registry, `act_registry.capability_short`).

Two kinds are out of domain. An act the app has no tool for ("call my mum",
"order me a pizza"): a phone assistant's verb, not one of the registry's. And
a question about the world rather than the notebook ("who wrote Hamlet",
"what's the temperature in Perth"): said in no one's own words (no I, my, we,
you), and either nothing was found or the notes found miss a word it asks
about. A question the notes answer whole, or one in the person's own words,
keeps its answer as it was.
"""

from __future__ import annotations

import re

from tessellate.ai import act_registry
from tessellate.ai.composer_phrases import PHRASES
from tessellate.core.lazyre import lazy_compile

#: Verbs a phone assistant runs and this app has no act for (the registry's
#: verbs are remind, tick, tag, move, make, pin, link...): checked against
#: `act_registry.ACTS` by `tests/test_composer_eval_1113.py`.
NOT_AN_ACT = lazy_compile(
    r"^(?:(?:please|can you|could you|would you|will you|go and|just)\s+)*"
    r"(?:call|phone|ring|text|e-?mail|message|send|order|book|buy|purchase|play|stream|"
    r"turn (?:on|off)|switch (?:on|off)|post|tweet|navigate|drive|pay|transfer)\b",
    re.I,
)
#: Said in the person's own words: about their notebook, not the world.
_PERSONAL = lazy_compile(r"\b(?:i|i'm|i've|i'd|me|my|mine|myself|we|we're|our|ours|us|you|your)\b", re.I)
#: The notebook's own nouns: a question naming one is about the notebook ("how many notes are there").
_NOTEBOOK = lazy_compile(r"\b(?:notes?|notebook|tags?|categor(?:y|ies)|reminders?|boards?|documents?|tasks?|todos?|lists?|meetings?|chats?|atlas|tessellate)\b", re.I)
_QUESTION = lazy_compile(r"^(?:who|what|what's|whats|when|where|which|how|is|are|was|were|will|do|does|did)\b", re.I)
#: "Who wrote Hamlet" asks for a person; "who is Sam" asks about one the notes may name.
_WHO_DID = lazy_compile(r"^who\s+(?!(?:is|was|are|were|am)\b)\w+", re.I)
_CAPITAL = re.compile(r"(?<!^)(?<![.!?]\s)\b[A-Z][\w']+")

_ACT_LEAD = "That is not something this app can do."
_WORLD_LEAD = "Nothing in these notes answers that."
_CLOSEST = "The closest note I found is this one."


def _shown_text(result: dict, notes: list[dict]) -> str:
    ids = {g.get("note_id") for g in result.get("grounding") or []}
    return " ".join(str(n.get("content") or "") for n in notes if n.get("id") in ids).lower()


def _misses_a_word(question: str, result: dict, notes: list[dict], terms: list[str]) -> bool:
    """The notes shown leave out a word the question asks about, or a "who did"
    question is answered by sentences that name no one but what was asked."""
    shown = _shown_text(result, notes)
    if any(t not in shown for t in terms):
        return True
    if _WHO_DID.match(question):
        sentences = [g.get("sentence", "") for g in result.get("grounding") or []]
        asked = {t.lower() for t in terms}
        return not any(m.group(0).lower() not in asked for s in sentences for m in _CAPITAL.finditer(s))
    return False


def kind(question: str, result: dict, notes: list[dict], terms: list[str]) -> str:
    """"act", "world" or "" for an answer that stays as it was."""
    asked = " ".join((question or "").split()).strip(" ?.!")
    if NOT_AN_ACT.match(asked):
        return "act"
    if ("phrase", "utility_weather") in (result.get("parts") or []) or result.get("text") == PHRASES["utility_weather"]:
        return "world"
    if result.get("shape") == "utility" or _PERSONAL.search(asked) or _NOTEBOOK.search(asked) or not _QUESTION.match(asked):
        return ""
    #: Nothing shown is nothing found, however it was worded ("Nothing I found was written last night").
    if not result.get("grounding") or _misses_a_word(asked, result, notes, terms):
        return "world"
    return ""


def framed(question: str, result: dict, notes: list[dict], terms: list[str]) -> dict:
    """The answer, framed as out of domain when it is (see the module's text)."""
    found = kind(question, result, notes, terms)
    if not found or not result.get("parts"):
        return result
    shown = bool(result.get("grounding"))
    parts = list(result["parts"])
    if found == "act":
        lead = [("template", _ACT_LEAD + (" " + _CLOSEST if shown else ""))]
        parts = [*lead, ("template", "\n\n"), *parts] if shown else lead
    elif shown:
        parts = [("template", f"{_WORLD_LEAD} {_CLOSEST}"), ("template", "\n\n"), *parts]
    parts += [("template", "\n\n" if shown else " "), ("template", act_registry.capability_short())]
    return {**result, "parts": parts, "text": "".join(p[1] for p in parts), "out_of_domain": found}
