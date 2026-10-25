"""The composition layer: a reply is built from slots, not picked whole.

The owner, 2026-10-26 (CHAT_PLAN 1353): "make sure all preformed responses
have an insane amount of variations but I want the responses to be composed,
not just selecting from large preformed responses ... the best ones should
be picked based on context, meaning, user detected emotion, keywords".

**Four slots.** A reply is `opener + frame + closer`, with a `bridge` (a
connective) joining the parts of a list. Each slot is a pool of candidates
(`composer_lines.py`); each candidate is scored against a `Mood`:

- the **voice** (warm, terse, playful, formal): a candidate tagged for other
  voices is out, so a voice changes wording, sentence length and rhythm, not
  only the opener (a terse frame is a fragment, a formal one a full sentence);
- the **emotion** read from the person's own words (`read_emotion`, a small
  lexicon: stressed, rushed, upset, upbeat, neutral), which also sets how
  much is said around the facts (a rushed person gets the frame alone);
- the **keywords** of the question, matched against a candidate's keyword tags;
- the **history**: a surface the conversation already said is passed over;
- a **seed**, so a turn is reproducible and a new turn differs.

**Facts stay exact.** A frame names the facts it carries as `{placeholders}`
and only frames that hold every fact passed are eligible, so a voice can
reword the joining words but never drop or change a quote, a count or a date.
The caller passes the facts already quoted or computed; nothing here says
anything about the world.
"""

from __future__ import annotations

import functools
import hashlib
import re
import string
from dataclasses import dataclass, field

from tessellate.ai import composer_lines as lines

#: Voice names the rest of the app uses (the `composer_voice` preference and
#: the composer's two registers) mapped onto the four voices written here.
VOICE_OF = {
    "natural": "warm", "warm": "warm", "professional": "formal", "formal": "formal",
    "playful": "playful", "plain": "terse", "terse": "terse",
}
VOICES = ("warm", "terse", "playful", "formal")
DEFAULT_VOICE = "warm"

EMOTIONS = ("stressed", "rushed", "upset", "upbeat", "neutral")

#: Word stems per emotion. Matched as word prefixes, so "stress" holds
#: "stressed" and "stressful".
_LEXICON: dict[str, tuple[str, ...]] = {
    "stressed": ("stress", "overwhelm", "panic", "anxious", "anxiety", "worri", "nervous", "cram", "swamped", "behind on", "too much",
                 "drowning", "deadline", "exam tomorrow", "scared", "freaking", "dread"),
    "rushed": ("quick", "asap", "hurry", "urgent", "fast", "tldr", "tl;dr", "briefly", "right now", "in a rush", "short version", "real quick"),
    "upset": ("frustrat", "annoy", "angry", "hate", "useless", "broken", "terrible", "awful", "ugh", "wtf", "not working", "again?", "sick of",
              "wrong", "stupid", "worst", "damn", "sad", "upset"),
    "upbeat": ("great", "thank", "awesome", "love", "nice", "cool", "happy", "excited", "amazing", "yay", "brilliant", "perfect", "fantastic", "wonderful"),
}
_WORD = re.compile(r"[a-z0-9']+")
_STOP = frozenset("the a an of to and or is are was were my me i you it in on for with about what when how do does did can could please this that".split())


#: One alternation per emotion, compiled at import: a read is four scans.
_LEXICON_RE = {e: re.compile("|".join(re.escape(x) for x in stems)) for e, stems in _LEXICON.items()}
_EMPHASIS = re.compile(r"[!?]{2,}")


def voice_for(name: str | None) -> str:
    """The voice a preference or register name speaks in (warm when unknown)."""
    return VOICE_OF.get(str(name or "").strip().lower(), DEFAULT_VOICE)


_PERSONA_CUES: tuple[tuple[str, tuple[str, ...]], ...] = (
    ("terse", ("terse", "concise", "brief", "minimal", "blunt", "laconic", "direct", "short")),
    ("playful", ("playful", "fun", "witty", "cheeky", "quirky", "whimsical", "humor", "humour", "jokes", "pirate", "bubbly")),
    ("formal", ("formal", "professional", "scholar", "academic", "butler", "librarian", "precise", "polite", "diplomat")),
    ("warm", ("warm", "friendly", "kind", "gentle", "caring", "supportive", "encouraging", "coach", "mentor")),
)


def voice_for_persona(prompt: str | None, fallback: str = "natural") -> str:
    """The voice a persona's description asks for, by its own words: "a witty
    pirate" is playful, "a precise archivist" formal. A persona with no cue
    keeps the voice the person picked in Settings."""
    low = str(prompt or "").lower()
    best, best_hits = "", 0
    for voice, cues in _PERSONA_CUES:
        hits = sum(1 for cue in cues if cue in low)
        if hits > best_hits:
            best, best_hits = voice, hits
    return best or voice_for(fallback)


def read_emotion(text: str) -> str:
    """stressed, rushed, upset, upbeat or neutral, from the person's words.
    The strongest lexicon hit wins; ties go in that order (stress first, so a
    worried "quick" question is met calmly, not hurried)."""
    low = " " + " ".join(str(text or "").lower().split()) + " "
    scores = {e: len(rx.findall(low)) for e, rx in _LEXICON_RE.items()}
    if _EMPHASIS.search(low):
        scores["upset"] += 1 if scores["upset"] else 0
        scores["stressed"] += 1 if scores["stressed"] else 0
    letters = [c for c in str(text or "") if c.isalpha()]
    if len(letters) >= 8 and sum(c.isupper() for c in letters) / len(letters) > 0.7:
        scores["upset"] += 1
    top = max(scores.values())
    return next((e for e in EMOTIONS[:4] if scores[e] == top), "neutral") if top else "neutral"


def _stable(*parts: object) -> float:
    """A number in [0, 1) fixed by `parts`."""
    digest = hashlib.sha256("|".join(str(p) for p in parts).encode()).digest()
    return int.from_bytes(digest[:4], "big") / 2**32


@dataclass(frozen=True)
class Mood:
    """What a slot is scored against."""

    voice: str = DEFAULT_VOICE
    emotion: str = "neutral"
    words: frozenset[str] = frozenset()
    seed: str = ""
    said: str = ""
    intent: str = ""
    extras: tuple[str, ...] = field(default=())


def mood_of(question: str = "", *, voice: str | None = None, seed: str = "", said: str | list | tuple = "", intent: str = "") -> Mood:
    """The mood of one turn: its voice, the emotion in `question`, its
    keywords, and `said`, the conversation's earlier replies."""
    words = frozenset(w for w in _WORD.findall(str(question or "").lower()) if w not in _STOP and len(w) > 2)
    text = said if isinstance(said, str) else "\n".join(str(s) for s in said)
    return Mood(voice_for(voice), read_emotion(question), words, str(seed), text, intent)


def _score(cand: lines.Cand, slot: str, mood: Mood) -> float:
    score = 0.0
    if cand.voices:
        score += 3.0 if mood.voice in cand.voices else -6.0
    if cand.emotions:
        score += 2.0 if mood.emotion in cand.emotions else -3.0
    if cand.keys:
        score += sum(1.0 for k in cand.keys if any(w.startswith(k) for w in mood.words))
    return score


def _fresh(text: str, mood: Mood) -> bool:
    return not mood.said or text.strip() not in mood.said


def pick(pool: tuple[lines.Cand, ...], slot: str, mood: Mood, render=None) -> lines.Cand | None:  # noqa: ANN001
    """The best candidate of `pool` for this mood: scored on voice, emotion
    and keywords, a surface already said in the conversation set aside, ties
    and near-ties broken by the seed. None when nothing is eligible."""
    best: tuple[float, lines.Cand] | None = None
    for cand in pool:
        shown = render(cand.text) if render else cand.text
        score = _score(cand, slot, mood) + _stable(mood.seed, slot, cand.text) * 1.8 - (0 if _fresh(shown, mood) else 5.0)
        if score > -3 and (best is None or score > best[0]):
            best = (score, cand)
    return best[1] if best else None


#: How much is said around the facts: the share of turns that get an opener
#: and a closer, by voice, and the emotions that take neither.
_AROUND = {"warm": (0.75, 0.55), "terse": (0.12, 0.08), "playful": (0.8, 0.65), "formal": (0.45, 0.4)}
_BARE = frozenset({"rushed"})


def _slot_on(mood: Mood, slot: str) -> bool:
    if mood.emotion in _BARE:
        return False
    share = _AROUND[mood.voice][0 if slot == "opener" else 1]
    if mood.emotion in ("stressed", "upset"):
        share = max(share, 0.7)  # a person who is struggling is acknowledged
    return _stable(mood.seed, slot, "on", mood.intent) < share


@functools.lru_cache(maxsize=4096)
def _fields(text: str) -> frozenset[str]:
    return frozenset(f for _lit, f, _spec, _conv in string.Formatter().parse(text) if f)


def frame(ability: str, mood: Mood, **facts: object) -> str:
    """The frame of `ability` with `facts` filled in. Only frames that hold
    every fact given are eligible, so no fact is ever dropped."""
    have = {k for k, v in facts.items() if v not in (None, "")}
    pool = tuple(c for c in lines.FRAMES[ability] if have <= _fields(c.text) and _fields(c.text) <= facts.keys())
    if not pool:
        raise KeyError(f"no frame of {ability!r} holds {sorted(have)}")
    chosen = pick(pool, f"frame:{ability}", mood, lambda t: t.format(**facts))
    return (chosen or pool[0]).text.format(**facts)


#: Abilities whose frames carry their own greeting or are clauses of one:
#: a generic "Sure." before "Good morning." would be wrong.
_NO_AROUND = frozenset({"hello", "welcome_new", "w_due", "w_last", "w_streak", "w_quiet"})


#: Abilities that take only their own openers and closers (an act's
#: confirmation or question, where "Let me see." would read wrong).
_OWN = frozenset({"act_done", "act_ask", "act_baddate", "act_none"})


def opener(mood: Mood, ability: str = "") -> str:
    """One opening, or empty when this turn gets none."""
    if ability in _NO_AROUND or not _slot_on(mood, "opener"):
        return ""
    pool = lines.ABILITY_OPENERS.get(ability, ()) + (() if ability in _OWN else lines.OPENERS)
    chosen = pick(pool, "opener", mood)
    return chosen.text if chosen else ""


def closer(mood: Mood, ability: str = "") -> str:
    """One closing line, or empty when this turn gets none."""
    if ability in _NO_AROUND or not _slot_on(mood, "closer"):
        return ""
    pool = lines.ABILITY_CLOSERS.get(ability, ()) + (() if ability in _OWN else lines.CLOSERS)
    chosen = pick(pool, "closer", mood)
    return chosen.text if chosen else ""


def bridge(mood: Mood, salt: object = "") -> str:
    """A connective that joins two clauses ("Also,", "Then", "And")."""
    chosen = pick(lines.BRIDGES, f"bridge:{salt}", mood)
    return chosen.text if chosen else "Also,"


def join_facts(items: list[str], mood: Mood) -> str:
    """`items` read as one phrase: "a, b and c" (warm, formal), "a, b, c"
    (terse), "a, b, plus c" (playful). The items themselves are untouched."""
    items = [i for i in items if i]
    if len(items) <= 1:
        return "".join(items)
    last = {"terse": ", ", "playful": ", plus ", "formal": " and ", "warm": " and "}[mood.voice]
    return ", ".join(items[:-1]) + last + items[-1]


def head(ability: str, mood: Mood, **facts: object) -> str:
    """A lead line for a reply that goes on with a list or a card: the
    opener (when this turn takes one) and the frame."""
    lead = opener(mood, ability)
    body = frame(ability, mood, **facts)
    return f"{lead} {body}".strip() if lead else body


def tail(ability: str, mood: Mood) -> str:
    """The closing line for a reply, or empty."""
    return closer(mood, ability)


def say(ability: str, mood: Mood, **facts: object) -> str:
    """A whole one-paragraph reply: opener, frame, closer."""
    return " ".join(p for p in (head(ability, mood, **facts), tail(ability, mood)) if p)


def span_phrase(span: str) -> str:
    """A time span as an adverbial phrase: "the last 7 days" takes "in",
    "this week", "yesterday" and "in october" stand as they are."""
    span = span.strip()
    return f"in {span}" if span.lower().startswith(("the ", "a ", "an ")) else span


def sentence_case(text: str) -> str:
    return text[:1].upper() + text[1:] if text else text


def _clause(lead: str, text: str) -> str:
    """`text` after a connective: lower-cased after a comma-ended or bare
    one ("Also, your last note"), left alone after a colon."""
    if lead and (lead.endswith(",") or lead[-1].isalpha()) and text[:1].isupper() and not text[1:2].isupper():
        text = text[0].lower() + text[1:]
    return f"{lead} {text}".strip()


def time_of_day(hour: int) -> str:
    """morning, afternoon, evening or night, from the user's local hour."""
    return "morning" if 5 <= hour < 12 else "afternoon" if 12 <= hour < 17 else "evening" if 17 <= hour < 22 else "night"


def welcome(mood: Mood, *, hour: int = 9, due: int | None = None, last: str = "", streak: int = 0, notes: int = 1) -> str:
    """A greeting built from what the app knows: the time of day, what is due
    today (`due`, None when unknown), the title of the last note (`last`) and
    the streak in days. No note yet is the empty welcome. Each known fact is
    one clause; which come, in what order and joined how is the mood's."""
    if notes <= 0:
        new = frame("welcome_new", mood)
        return new if _stable(mood.seed, "tod") < 0.5 else f"{frame('hello', mood, tod=time_of_day(hour))} {new}"
    parts = [frame("hello", mood, tod=time_of_day(hour))]
    clauses: list[tuple[str, str]] = []
    if due:
        clauses.append(("due", frame("w_due", mood, due=f"{due} reminder{'s' if due != 1 else ''}")))
    elif due == 0:
        clauses.append(("due", frame("w_quiet", mood)))
    if last:
        clauses.append(("last", frame("w_last", mood, last=f"“{last}”")))
    if streak >= 2:
        clauses.append(("streak", frame("w_streak", mood, streak=f"{streak} days")))
    clauses.sort(key=lambda kv: _stable(mood.seed, "order", kv[0]))
    keep = len(clauses) if mood.voice != "terse" else min(len(clauses), 2)
    for n, (_name, text) in enumerate(clauses[:keep]):
        lead = bridge(mood, n) if n and mood.voice != "terse" and _stable(mood.seed, "bridge", n) < 0.6 else ""
        parts.append(_clause(lead, text))
    return " ".join(parts)
