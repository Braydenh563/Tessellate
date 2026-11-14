"""Presence spells (INBOX 1692, the owner 2026-11-08: "think the abi toads and lofi girl in how they are there and present and
like companions but not in the way"). Technique only, never anyone's art or look.

A spell is a few minutes of one quiet thing the companion does in place, by the hour and its mood: tea in the morning,
reading or a journal by day, fishing, knitting a strand of starlight or the stars in the evening, a nap under a blanket at night, and a plant at any
hour. Pure data and one pure pick (`pick_spell`): no clock, no randomness of its own; the engine passes its seeded
`rng`. The engine starts it as one long prop act (`Engine._start_spell`), and between two spells it travels by a seen
move (`travel.VISIBLE`), never a long walk.
"""

from __future__ import annotations

import random
from typing import NamedTuple


class Spell(NamedTuple):
    #: The act it runs (a prop act in `props`).
    act: str
    #: The hours it suits (0 to 23).
    hours: tuple[int, ...]
    #: Seconds it lasts: the least and the most.
    seconds: tuple[float, float]
    weight: float
    #: The moods that make it likelier (x1.6).
    moods: tuple[str, ...] = ()


def _span(a: int, b: int) -> tuple[int, ...]:
    """Hours from `a` up to (not including) `b`, wrapping midnight."""
    return tuple(h % 24 for h in range(a, b if b > a else b + 24))


SPELLS: dict[str, Spell] = {
    "tea": Spell("sip_tea", _span(5, 12), (120.0, 270.0), 3.0, ("sleepy", "content")),
    "read": Spell("read_book", _span(9, 19), (150.0, 420.0), 3.0, ("curious", "focus")),
    "doodle": Spell("write_journal", _span(10, 20), (120.0, 360.0), 2.5, ("curious", "happy")),
    "fish": Spell("go_fishing", _span(16, 22), (180.0, 480.0), 2.5, ("sleepy", "bored")),
    "stars": Spell("watch_stars", _span(19, 4), (150.0, 420.0), 3.0, ("curious", "sleepy")),
    "doze": Spell("blanket_nap", _span(21, 6), (180.0, 480.0), 3.5, ("sleepy",)),
    "knit": Spell("knit_starlight", _span(17, 22), (120.0, 300.0), 2.0, ("content", "curious")),
    "plant": Spell("water_plant", _span(0, 24), (100.0, 220.0), 1.0, ("happy", "proud")),
}


def spells_for(hour: int) -> list[str]:
    """The spells that suit `hour`."""
    return [name for name, s in SPELLS.items() if hour % 24 in s.hours]


def pick_spell(rng: random.Random, hour: int, mood: str, recent: list[str]) -> str:
    """One spell for the hour and mood, never the one it just did (unless it is the only one that suits)."""
    names = spells_for(hour)
    live = [n for n in names if not recent or n != recent[-1]] or names
    weights = [SPELLS[n].weight * (1.6 if mood in SPELLS[n].moods else 1.0) for n in live]
    roll = rng.random() * sum(weights)
    for n, w in zip(live, weights):
        roll -= w
        if roll < 0:
            return n
    return live[-1]


def length_of(rng: random.Random, name: str) -> float:
    lo, hi = SPELLS[name].seconds
    return rng.uniform(lo, hi)


#: A beat inside a spell (L-ui-modernisation-99, INBOX 1832: "a visible beat in a spell every 20 to 40 s"), by the act's
#: own picture: the picture of the beat and its least and most seconds (`engine_beats`).
SPELL_BEAT_EVERY = (20.0, 40.0)
SPELL_BEATS = {
    "sit": (("look", 3.2, 5.6), ("meditate", 4.8, 8.0)),
    "stand": (("look", 3.2, 5.6),),
    "look": (("stand", 3.2, 5.6),),
}
