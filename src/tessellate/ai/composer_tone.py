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

A persona is a prompt for a model, but with none running its own words still
pick the composer's voice (`composer_compose.persona_cue`: "a witty pirate" is
playful) unless a voice was chosen in Settings. It changes wording and
rhythm, never a fact (CHAT_PLAN 1353).
"""

from __future__ import annotations

from tessellate.ai import composer_compose as compose


def length(mode: str | None) -> str:
    """short, normal or long, from the Length picker's mode (unknown is normal)."""
    return {"quick": "short", "detailed": "long"}.get(str(mode or "").strip().lower(), "normal")


def fit(text: str, size: str) -> str:
    """Quick keeps the lead paragraph; the rest is for the longer modes."""
    if size != "short":
        return text
    lead = text.split("\n\n", 1)[0].strip()
    return lead or text


def closing(*, recent: list[str], seed: str, avoid: tuple[str, ...] | list[str] = (), voice: str = "natural", question: str = "", newest: bool = True) -> str:
    """One next-step line from the newest note's title, or empty with no notes.

    Composed (`composer_compose`, frame `close_next`) in the person's voice
    and for the mood of their words; `avoid` is the last replies of this
    conversation, and a wording any of them already holds is passed over."""
    titles = [t for t in recent if t]
    if not titles:
        return ""
    mood = compose.mood_of(question, voice=voice, seed=f"{seed}:{titles[0]}", said=list(avoid))
    #: A note title is the person's opening words, often typed small; said back
    #: inside quotes it opens with a capital like any title.
    title = titles[0]
    if title.split()[0].islower():  # "iPhone" keeps its own shape
        title = title[:1].upper() + title[1:]
    #: `newest` False: the title is a note the answer cited, not the
    #: notebook's newest, so the line may not call it newest or latest.
    return compose.frame("close_next" if newest else "close_cited", mood, t=title)
