"""Speaker labels behind the model gate (WORLD_CLASS 28.5 row 11; ANALYSIS
keeps diarisation out of the offline core).

Two passes, and only the second needs a model. **Turns** are cut by timing
alone (`core/transcript.turns`: a pause over 1.5 s or a new paragraph).
**Names** are the model's reading of what is said, never of the audio: "Thanks
Sam" before a turn and "Priya, the venue?" before the next are the clues a
person uses too. With no model nothing is labelled and nothing is shown, so
a label is never a guess dressed as a fact. A reply that names fewer than
half the turns is not used at all.
"""

from __future__ import annotations

import re

from tessellate.ai import presets
from tessellate.core import transcript

#: About twenty minutes of speech; past that the last turns go unlabelled
#: rather than a small model losing the instructions.
MAX_PROMPT_CHARS = 16_000
MAX_TURN_CHARS = 600

SYSTEM = (
    "You are given a meeting transcript cut into numbered turns, each spoken "
    "by one person. Say who speaks each turn, judging only from what is said: "
    "names used, who is addressed, who answers. Reply with one line per turn "
    "and nothing else, as: <number> | <first name>. When a turn's speaker "
    "cannot be told, use Speaker A, Speaker B and so on, the same label for "
    "the same person."
)

_LINE = re.compile(r"^\s*(\d{1,4})\s*[|:.)\-]\s*(.+?)\s*$")
_NAME = re.compile(r"[^\w .'-]")


def _prompt(segments: list[dict], groups: list[list[int]], people: list[str]) -> str:
    lines = []
    if people:
        lines.append("People at the meeting: " + ", ".join(people[:20]) + ".\n")
    used = 0
    for n, group in enumerate(groups, 1):
        said = " ".join(segments[i]["text"] for i in group)[:MAX_TURN_CHARS]
        used += len(said)
        if used > MAX_PROMPT_CHARS:
            break
        lines.append(f"{n}. {said}")
    return "\n".join(lines)


def parse_names(reply: str, count: int) -> dict[int, str]:
    """`{turn number: name}` from the reply's lines; a number outside the
    transcript or a name longer than three words is skipped."""
    names: dict[int, str] = {}
    for raw in str(reply or "").splitlines():
        found = _LINE.match(raw.strip().lstrip("-*• "))
        if not found:
            continue
        turn = int(found.group(1))
        name = " ".join(_NAME.sub("", found.group(2)).split())[: transcript.MAX_SPEAKER]
        if 1 <= turn <= count and name and len(name.split()) <= 3:
            names.setdefault(turn, name)
    return names


def label(segments: list[dict], people: list[str], model_manager, ollama) -> list[dict]:  # noqa: ANN001
    """The segments with `speaker` set from the model's names for their
    turns; unchanged when there is one turn or the reply names too few.
    Raises what the client raises; the caller keeps the segments as they
    were."""
    groups = transcript.turns(segments)
    if len(groups) < 2:
        return segments
    reply = ollama.chat(
        model_manager.utility_model(),
        [{"role": "system", "content": SYSTEM}, {"role": "user", "content": _prompt(segments, groups, people)}],
        mode=presets.BACKGROUND_MODE,
    )
    names = parse_names(reply.get("content", ""), len(groups))
    if len(names) * 2 < len(groups):
        return segments
    out = [dict(seg) for seg in segments]
    for n, group in enumerate(groups, 1):
        for index in group:
            out[index]["speaker"] = names.get(n)
    return out
