"""Out-of-domain answers (CHAT_PLAN step 11, U18, A25): a question neither the
notes nor the app can answer is told so plainly, a note it shows is called the
closest, and one line says what the app can do (generated from the act
registry, `act_registry.capability_short`).

Two kinds are out of domain. An act the app has no tool for ("call my mum",
"order me a pizza"): a phone assistant's verb, not one of the registry's. And
a question about the world rather than the notebook, said in no one's own
words (no I, my, we, you) and naming none of the notebook's nouns: one whose
typed name the notes shown do not hold ("what's the temperature in Perth"),
a "who did" whose verb no sentence shown says ("who wrote Hamlet"), or a
world topic with nothing found ("who won the football"). A no-answer keeps its
question back last; any other answer keeps its words as they were.
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
    r"(?:call(?! me\b)|phone|ring|text|e-?mail|message|send|order|book|buy|purchase|play|stream|"
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

#: Topics only the world knows (live scores, trivia): with no name typed, these say a question is about the world.
_WORLD_TOPIC = lazy_compile(
    r"\b(?:football|soccer|cricket|rugby|tennis|league|world cup|olympics|scores?|results? of the|planets?|"
    r"capital of|population of|how (?:tall|high|old|far|big) is|president of|prime minister|stock price|headlines|news today)\b",
    re.I,
)

#: The lines are phrases (`PHRASES`), so the composer's evals read them as its own templates.
PHRASES.update({
    "ood_act": "That is not something this app can do.",
    "ood_world": "Nothing in these notes answers that.",
    "ood_closest": "The closest note I found is this one.",
    "ood_capability": act_registry.capability_short(),
})


def _shown_text(result: dict, notes: list[dict]) -> str:
    ids = {str(g.get("note_id")) for g in result.get("grounding") or []}
    said = " ".join(str(g.get("sentence") or "") for g in result.get("grounding") or [])
    return (said + " " + " ".join(str(n.get("content") or "") for n in notes if str(n.get("id")) in ids)).lower()


def _names(question: str) -> list[str]:
    """The names typed in the question ("Perth", "Arsenal"), not its first word."""
    return [m.group(0).lower() for m in _CAPITAL.finditer(question)]


def _verb_unsaid(result: dict, question: str, shown: str) -> bool:
    """A "who did" question whose verb no sentence shown says: "who wrote Hamlet"
    shown "it was Hamlet at the old theatre" (and "who asked for an API" shown
    "three people asked for one" is an answer)."""
    found = _WHO_DID.match(question)
    verb = found.group(0).split()[1].lower() if found else ""
    return bool(verb) and bool(result.get("grounding")) and not re.search(rf"\b{re.escape(verb)}", shown)


def kind(question: str, result: dict, notes: list[dict]) -> str:
    """"act", "world" or "" for an answer that stays as it was."""
    asked = " ".join((question or "").split()).strip(" ?.!")
    if NOT_AN_ACT.match(asked):
        return "act"
    if ("phrase", "utility_weather") in (result.get("parts") or []) or result.get("text") == PHRASES["utility_weather"]:
        return "world"
    if result.get("shape") == "utility" or _PERSONAL.search(asked) or _NOTEBOOK.search(asked) or not _QUESTION.match(asked):
        return ""
    shown = _shown_text(result, notes)
    unnamed = [n for n in _names(asked) if n not in shown]
    if _verb_unsaid(result, asked, shown):
        return "world"
    #: A name the notes shown do not hold, or a topic only the world knows, with nothing shown or only a decoy.
    if unnamed or (_WORLD_TOPIC.search(asked) and not result.get("grounding")):
        return "world"
    return ""


def framed(question: str, result: dict, notes: list[dict]) -> dict:
    """The answer, framed as out of domain when it is (see the module's text)."""
    found = kind(question, result, notes)
    if not found or not result.get("parts"):
        return result
    shown = bool(result.get("grounding"))
    parts = list(result["parts"])
    closest = [("template", " "), ("template", PHRASES["ood_closest"]), ("template", "\n\n")] if shown else []
    if found == "act":
        parts = [("template", PHRASES["ood_act"]), *closest, *parts] if shown else [("template", PHRASES["ood_act"])]
    elif shown:
        parts = [("template", PHRASES["ood_world"]), *closest, *parts]
    line = [("template", "\n\n" if shown else " "), ("template", PHRASES["ood_capability"])]
    #: A no-answer still ends on its question back ("Could it be under another name?").
    asks_back = not shown and found == "world" and len(parts) > 1 and str(parts[-1][1]).rstrip().endswith("?")
    parts = [*parts[:-1], ("template", PHRASES["ood_capability"]), ("template", " "), parts[-1]] if asks_back else [*parts, *line]
    return {**result, "parts": parts, "text": "".join(p[1] for p in parts), "out_of_domain": found}
