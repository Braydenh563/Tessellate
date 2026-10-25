"""The composer's voice when no model runs: how long, and what comes next.

The 22-10 bug doc: replies read cold and the same, with nothing said about
what to do next. Two small things, both the app's own wording around measured
facts:

- `length`: the dock's Length picker (quick, normal, detailed) already exists
  for the model; the composer follows it. Quick keeps the lead sentence,
  normal and detailed keep the whole answer.
- `closing`: one line after a composed answer that points at the next step
  from what the notebook shows, the newest note's title: "I can see you've
  been working on “X”. Ask me what is left on it." Which wording is the
  seed's (the chat, the day and Ask again), so a replayed answer says the
  same and a new one does not.

A persona is a prompt for a model. With none running it changes nothing here
(the help says so), because the composer has one voice and quotes the notes.
"""

from __future__ import annotations

import hashlib

PHRASES: dict[str, str] = {
    "voice_close_a1": "I can see you've been working on “{t}”. Ask me what is left on it, or when it is due.",
    "voice_close_a2": "Your latest note is “{t}”. Want a summary of it, or what is left to do?",
    "voice_close_a3": "Since you've been in “{t}” lately, I can list what is still open there.",
    "voice_close_a4": "Next, I can open “{t}” or pull out its dates.",
    "voice_close_a5": "If it helps, ask me who is involved in “{t}”, your newest note.",
    "voice_close_a6": "Most recently you wrote “{t}”. Say the word and I will go through it with you.",
}

_ORDER = tuple(PHRASES)


def length(mode: str | None) -> str:
    """short, normal or long, from the Length picker's mode (unknown is normal)."""
    return {"quick": "short", "detailed": "long"}.get(str(mode or "").strip().lower(), "normal")


def fit(text: str, size: str) -> str:
    """Quick keeps the lead paragraph; the rest is for the longer modes."""
    if size != "short":
        return text
    lead = text.split("\n\n", 1)[0].strip()
    return lead or text


def closing(*, recent: list[str], seed: str) -> str:
    """One next-step line from the newest note's title, or empty with no notes."""
    titles = [t for t in recent if t]
    if not titles:
        return ""
    title = titles[0]
    key = hashlib.sha256(f"{seed}:{title}".encode()).digest()[0]
    return PHRASES[_ORDER[key % len(_ORDER)]].replace("{t}", title)
