"""A probability for every tool, from the words of the question (O10 rest;
BACKLOG "Composer ranks the tools the model is offered").

`toolwords.focus_detail` scores *groups*: the board group is sixteen tools
with one score, so when a small window could not hold them all, the cut
inside the group was the table's order and "add a node to my mind map" could
lose `add_map_node` to `read_whiteboard`. This scores each tool, from the
question after type repair, and `tools.within_budget` keeps the likeliest.

Evidence, combined as a noisy-or (each piece is an independent reason the
tool is wanted, so two weak ones beat one):

- the **core** and anything the turn must keep (web asked, a plan asked): sure;
- the **group** the focus fired for the question: a shared 0.35, more when the
  sentence argued harder for it;
- the **name's words**: "delete" and "tag" in `delete_tag`; a word every tool
  carries ("note") counts for little, the verb and the object for a lot;
- the **description's words** and the **argument names**, a little each;
- the **previous turn's tools**: a follow-up often wants the same ones again.

A question *about* a capability ("how do I delete a tag") halves its write
tools: the same rule `toolwords.looks_like_a_question_about` applies to the
groups. Nothing here decides: it orders, and `within_budget` cuts from the
bottom. Pure functions of their arguments, so the fixture test needs no app.
"""

from __future__ import annotations

import math
import re

#: The evidence weights; tuned on the fixtures in tests/test_toolrank.py.
SURE = 0.97
GROUP_BASE = 0.35
GROUP_PER_SCORE = 0.1
GROUP_CAP = 0.6
NAME_WORD = 0.5
GENERIC_NAME_WORD = 0.08
DESCRIPTION_WORD = 0.04
DESCRIPTION_CAP = 0.2
ARGUMENT_WORD = 0.08
RECENT = 0.25
READING = 0.25
ASKED_ABOUT = 0.5

#: Words in nearly every tool's name: matching them says little.
_GENERIC = frozenset({"note", "notes", "get", "list", "search", "find", "read", "all", "my", "the", "user", "item"})

_STOP = frozenset(
    "a an and are as at be by can do does for from has have how i if in into is it its me my of on or our so that the "
    "their them then there these this those to up was we what when where which who why will with you your please "
    "just also any some all about like need want make get give show tell let would could should".split()
)

#: A question that opens on one of these is asking to be told, not to have
#: something done, so the tools named for reading gain on the ones named for
#: doing: "what reminders do I have" is `list_reminders`, not `set_reminder`.
_ASKS_TO_BE_TOLD = re.compile(
    r"^\s*(?:what|which|who|whom|when|where|how (?:many|much)|show|list|do i|did i|have i|is there|are there)\b", re.I
)
_READING_VERBS = frozenset({"list", "get", "count", "search", "find", "read", "overview", "show"})

_WORD = re.compile(r"[a-z][a-z0-9']+")


def stem(word: str) -> str:
    """Enough of a stem for "tags" to meet "tag" and "deleted" to meet
    "delete"; not a linguist's, a matcher's."""
    word = word.lower().strip("'")
    for ending, keep in (("ies", "y"), ("ing", ""), ("ed", ""), ("es", ""), ("s", "")):
        if word.endswith(ending) and len(word) - len(ending) >= 3:
            word = word[: -len(ending)] + keep
            break
    if word.endswith("e") and len(word) > 3:
        word = word[:-1]
    if len(word) > 3 and word[-1] == word[-2]:
        word = word[:-1]
    return word


def words(text: str) -> set[str]:
    return {stem(w) for w in _WORD.findall((text or "").lower()) if w not in _STOP}


def repaired(text: str) -> str:
    """The question with its slips put right; the text itself when the
    speller is unavailable."""
    try:
        from tessellate.ai import question_noise

        return question_noise.repair(question_noise.tidy(" ".join((text or "").split())))
    except Exception:  # noqa: BLE001
        return text or ""


def _any(*chances: float) -> float:
    """Noisy-or: the chance at least one reason holds."""
    miss = 1.0
    for chance in chances:
        miss *= 1.0 - max(0.0, min(1.0, chance))
    return 1.0 - miss


def _argument_names(spec: dict) -> set[str]:
    props = ((spec.get("function") or {}).get("parameters") or {}).get("properties") or {}
    return {stem(part) for key in props for part in str(key).split("_")}


def _word_evidence(spec: dict, asked: set[str], reading: bool = False) -> list[float]:
    function = spec.get("function") or {}
    name_parts = [stem(p) for p in str(function.get("name", "")).split("_") if p]
    chances = [GENERIC_NAME_WORD if part in _GENERIC else NAME_WORD for part in name_parts if part in asked]
    if reading and name_parts and name_parts[0] in _READING_VERBS:
        chances.append(READING)
    described = words(function.get("description", "")) & asked
    if described:
        chances.append(min(DESCRIPTION_CAP, DESCRIPTION_WORD * len(described)))
    chances.extend(ARGUMENT_WORD for part in _argument_names(spec) if part in asked and part not in _GENERIC)
    return chances


def _group_chance(score: float) -> float:
    return min(GROUP_CAP, GROUP_BASE + GROUP_PER_SCORE * score)


def rank(
    question: str,
    specs: list[dict],
    *,
    core: list[str],
    groups: list[tuple[tuple[str, ...], tuple[str, ...]]],
    ranked_groups: list[tuple[int, float]],
    kept_first: list[str] | None = None,
    writes: frozenset[str] | set[str] = frozenset(),
    asking_about: bool = False,
    recent_tools: tuple[str, ...] = (),
) -> list[tuple[str, float]]:
    """`(tool name, probability it is wanted)`, likeliest first, every tool once.
    Ties keep the registry's order, so the result is deterministic."""
    fixed = repaired(question)
    asked = words(fixed)
    reading = bool(_ASKS_TO_BE_TOLD.match(fixed))
    group_of: dict[str, float] = {}
    for index, score in ranked_groups:
        for name in groups[index][0]:
            group_of[name] = max(group_of.get(name, 0.0), _group_chance(score))
    sure = set(core) | set(kept_first or ())
    scored: list[tuple[str, float]] = []
    for spec in specs:
        name = spec["function"]["name"]
        chances = _word_evidence(spec, asked, reading)
        if name in sure:
            chances.append(SURE)
        if name in group_of:
            chances.append(group_of[name])
        if name in recent_tools:
            chances.append(RECENT)
        chance = _any(*chances)
        if asking_about and name in writes and name not in sure:
            chance *= ASKED_ABOUT
        scored.append((name, round(chance, 3)))
    return sorted(scored, key=lambda pair: -pair[1])


def line(offered: list[str], held_back: list[str], chances: dict[str, float], limit: int = 8) -> str:
    """The log line for a turn: what was offered and what the window held
    back, each with its score, "offered a 97%, b 60%; held back c 12%"."""

    def show(names: list[str]) -> str:
        shown = ", ".join(f"{n} {math.floor(chances.get(n, 0.0) * 100)}%" for n in names[:limit])
        return shown + ("…" if len(names) > limit else "")

    out = f"tool ranking: offered {show(offered)}"
    return out + (f"; held back {show(held_back)}" if held_back else "")
