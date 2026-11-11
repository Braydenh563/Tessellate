"""The standing breath (INBOX 1719 b, E3): the pace of the stand's 24-picture idle cycle follows the walk and the mood, as the sit's and the
floater's breath do (`vitals.breath`). Pure: the engine hands in what it knows and gets a scale of the cycle's 4 s back."""

from __future__ import annotations

from . import vitals

#: The scale is held to this range of the 4 s, so the tail that is baked into the frames never whips and never drags.
STAND_BREATH = (0.88, 1.25)


def scale(mood: str, since_walk: float) -> float:
    """The scale of the idle cycle that begins `since_walk` seconds after the last walk, hop or carry, in `mood`: a sleepy or bored mood
    slows it, the walk's exertion quickens it and eases back (the vitals' 14 s half-life), and a plain happy or curious mood leaves the
    4 s as it was (that mood's own speed-up belongs to the floater's and the rest's breath, not to every stand)."""
    calm = vitals.breath(mood, 0.0)
    wanted = max(1.0, calm) * vitals.breath(mood, vitals.exertion(since_walk)) / calm
    return max(STAND_BREATH[0], min(STAND_BREATH[1], wanted))
