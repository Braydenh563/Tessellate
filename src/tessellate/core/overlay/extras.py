"""The desk figure's own life beyond the roaming engine (INBOX 1683 asks M4 to M7, B9 quality): the small acts it
does while it stands (a prop act, a plain one), a face that changes with them, the way it answers the pointer (a
pat, a rub, a poke by mood, a flip, a flinch from a fast swipe, a warm look when hovered) and the way it answers
what happens on the screen (a window opening or closing, the foreground app changing, the person coming back, the
hour, a download, the battery).

It is one object per engine (`Engine.ex`) so the engine's own file stays about moving: the engine asks it for the
prop and the face to draw (`view`), for how soon to look again (`wake_ms`) and hands it the pointer (`pointer`) and
the screen's events (`react`). It draws on its own random stream, so the engine's other choices do not shift for a
seed, and everything is a function of the clock the engine is given: deterministic, no Win32.
"""

from __future__ import annotations

import math
import random
from collections import deque
from typing import Any, NamedTuple

from . import behaviour as bh
from . import faces, gaze, props, windspirit

#: In-place acts while it stands: one every this many seconds, in the mind's own weighing (`mind.pick`).
LIFE_EVERY = (50.0, 130.0)
MIN_WAKE_MS = 16
#: Seconds after one of its acts before the next blink or look may come.
AFTER_ACT_QUIET = 2.0
#: An act whose pose swings less than this is drawn at the rest pace.
CALM_AMPLITUDE = 0.1
#: A small plain stand act is calm only under this: a stretch (0.09, the largest of the small ones) visibly moves, so it keeps its pose's own frames.
SMALL_AMPLITUDE = 0.08
#: A gap in the ticks longer than this is a stall (a suspend, a test's clock jump): the next act is re-timed. And the
#: least wait after the figure was busy with something else.
LIFE_STALL, LIFE_SETTLE = 10.0, 8.0
#: A catch in the air is answered once it stands within this many seconds (a long carry has forgotten it).
CATCH_WAIT = 12.0
#: The pointer is watched at this pace while it is near the figure (a gesture needs 15 samples a second).
WATCH_MS = 100
WATCH_REACH = 3.0  # box widths
#: ... and for this long after it last moved (a hover has to be seen as still, a rub as it begins).
WATCH_FOR = 0.7
SAMPLE_KEEP = 1.6
#: Gesture thresholds, logical px (scaled by the figure's size) and seconds.
PAT_DIP, PAT_REVERSALS, PAT_WINDOW, HEAD_ZONE = 11.0, 2, 1.0, 0.42
RUB_SWING, RUB_REVERSALS, RUB_WINDOW, RUB_FLAT = 14.0, 3, 1.4, 0.7
#: A tickle (catalogue `int.tickle`) is a fast small rub on the body below the head: `TICKLE_REVERSALS` turns of at
#: least `TICKLE_SWING` px inside `TICKLE_WINDOW` s, over no more than `TICKLE_SPAN` px across and flatter than `TICKLE_FLAT`
#: (a hand's tremor turns as often, but as far up as across). A boop (`int.boop_nose`) is a jab whose tip lands on the
#: nose: within `NOSE_HALF` of the box's width about its middle, between `NOSE_TOP` and the head's lower edge.
TICKLE_SWING, TICKLE_REVERSALS, TICKLE_WINDOW, TICKLE_SPAN, TICKLE_FLAT = 5.0, 5, 1.2, 18.0, 0.6
NOSE_HALF, NOSE_TOP = 0.2, 0.18
#: A poke is a jab: in at `POKE_SPEED`, at most `POKE_DWELL` s inside, back out the way it came, answered within
#: `POKE_LEFT` s of leaving. An arrival that stays is a hover (INBOX 1692: "it gets instantly mad every time i hover").
POKE_SPEED, POKE_WINDOW, POKE_DWELL, POKE_LEFT = 800.0, 0.4, 0.6, 0.3
SWIPE_SPEED, FLINCH_REACH = 1500.0, 150.0
HOVER_FOR, HOVER_STILL = 1.2, 80.0
#: A stroke's travel over its distance: more than this is a tremor, not a pat.
STROKE_WASTE = 1.3
#: States a reaction may break into, and the few more a touch may.
SCREEN_FREE = ("stand", "act", "notice", "wave", "land")
TOUCH_FREE = (*SCREEN_FREE, "sit", "sleep", "startle")
#: A carried shake: this many direction flips inside `SHAKE_WINDOW` s, each after a stroke of `SHAKE_SWING` px along the
#: motion's main axis (a drag with a wobble travels away; a shake goes back and forth about a point; catalogue
#: `int.shake_dizzy`, INBOX 1696 kk). The dizzy sway after the drop lasts `DIZZY_FOR` s.
SHAKE_FLIPS, SHAKE_WINDOW, SHAKE_SWING, DIZZY_FOR = 3, 0.6, 22.0, (2.5, 4.0)
#: The shake is read in this many directions, over points averaged per `SHAKE_BUCKET` s when there are more than `SHAKE_RAW`; the motion across the axis
#: may be at most `SHAKE_ACROSS` times the motion along it.
SHAKE_AXES, SHAKE_BUCKET, SHAKE_ACROSS, SHAKE_RAW, SHAKE_EVERY = 12, 0.015, 1.5, 48, 0.01
#: A pet this soon after waking is shy; the third pet inside `LOVE_STREAK` s is loved.
SHY_FOR, LOVE_STREAK, LOVE_PETS = 8.0, 30.0, 3
FACE_STATES = ("stand", "act", "notice", "startle", "wave", "land", "sit")


class Reaction(NamedTuple):
    #: The act it plays ("" for a face alone), the face it wears and for how long, the mood it leaves.
    act: str
    face: str
    seconds: float
    feel: str = ""
    cooldown: float = 6.0
    touch: bool = False
    #: B5: 1 waits for a free moment; 2 or more also breaks a sit, a sleep and a walk, and a running reaction of lower priority.
    prio: int = 1
    #: A face alone that may be worn while the person is working (it asks nothing of them).
    busy_ok: bool = False


REACTIONS: dict[str, Reaction] = {
    # the pointer
    "pat": Reaction("pat_happy", "joy", 2.2, "happy", 3.0, True),
    "rub": Reaction("rub_purr", "content", 3.4, "happy", 6.0, True),
    "poke_giggle": Reaction("poke_giggle", "smile", 1.6, "happy", 4.0, True),
    "poke_miffed": Reaction("poke_miffed", "miffed", 2.0, "startled", 4.0, True),
    "poke_curious": Reaction("poke_curious", "curious", 1.8, "", 4.0, True),
    "flip": Reaction("flip_twirl", "joy", 1.6, "happy", 5.0, True),
    "flinch": Reaction("flinch", "worried", 1.2, "startled", 5.0, True),
    "hover": Reaction("", "smile", 3.0, "happy", 25.0, True),
    "tickle": Reaction("tickle_squirm", "laughing", 2.4, "happy", 8.0, True),
    "boop": Reaction("boop_sneeze", "surprised", 1.1, "", 5.0, True),
    # the faces confused, sad, shy and love (catalogue B4): a poke while the person works, a refused request, a pet
    # right after waking, a long run of pets
    "confused": Reaction("", "confused", 1.8, "", 20.0, True, 1, True),
    "refused": Reaction("", "sad", 2.4, "", 10.0, True),
    # a menu request it cannot do now (L-ui-modernisation-22): its own cooldown, so a lonely sad face just before
    # does not swallow the answer, and rank 2 so a sit or a walk still shows it
    "declined": Reaction("", "sad", 2.4, "", 1.0, True, 2),
    "pat_shy": Reaction("pat_happy", "shy", 2.2, "happy", 3.0, True),
    "rub_shy": Reaction("rub_purr", "shy", 3.4, "happy", 6.0, True),
    "pat_love": Reaction("pat_happy", "love", 2.6, "happy", 3.0, True),
    "rub_love": Reaction("rub_purr", "love", 3.6, "happy", 6.0, True),
    # a shake while carried: it is left dizzy on the ground (`Extras.dizzy`)
    "dizzy": Reaction("dizzy_sway", "dizzy", 3.2, "startled", 8.0, True, 2),
    # the screen
    "window_opened": Reaction("glance_window", "curious", 2.0, "", 8.0),
    "window_closed": Reaction("relief", "content", 1.8, "", 10.0),
    "app_switched": Reaction("glance_screen", "curious", 1.4, "", 10.0),
    "idle_return": Reaction("welcome_back", "smile", 2.2, "happy", 60.0),
    "hour_chime": Reaction("chime_nod", "smile", 2.0, "", 3000.0),
    "battery_low": Reaction("shiver", "worried", 3.0, "startled", 600.0),
    "download_done": Reaction("cheer", "joy", 2.0, "happy", 15.0),
    "toast": Reaction("perk_up", "surprised", 1.6, "", 20.0),
    "window_dragged": Reaction("watch_drag", "curious", 2.0, "", 10.0),
    "window_maximised": Reaction("perk_up", "surprised", 1.6, "", 10.0),
    "window_restored": Reaction("relief", "content", 1.8, "", 10.0),
    # the day and the desk (INBOX 1719 b, 1696 j): dusk, the morning's first input, back from behind a full-screen app,
    # a long run of typing come to rest (`screenwatch`)
    "night_falls": Reaction("dusk_stretch", "content", 3.0, "", 3000.0),
    "morning_hello": Reaction("morning_wave", "smile", 2.6, "happy", 3000.0),
    "fullscreen_app": Reaction("peek_back", "curious", 1.8, "", 30.0),
    "typing_burst": Reaction("nod_done", "smile", 1.6, "happy", 300.0),
    # what the app's server notes (W31, `core.companion_events`, read on the screen poll): the in-app companion's reactions
    # to its own page, with the in-app cooldowns. Each plays a pose the desk already ships (look, stand, wave).
    "graph_laid": Reaction("glance_screen", "curious", 2.4, "", 60.0),
    "long_note": Reaction("read_glasses", "curious", 5.0, "", 180.0),
    "note_binned": Reaction("wince", "worried", 1.4, "", 30.0),
    "private_note": Reaction("cover_eyes", "shy", 2.4, "", 45.0),
    "remark": Reaction("remark_say", "smile", 2.4, "", 600.0),
    "reminder_bell": Reaction("bell_ring", "surprised", 2.6, "", 5.0),
    "search_nothing": Reaction("puzzle_tilt", "confused", 2.0, "", 45.0),
    "search_found": Reaction("nod_done", "smile", 1.4, "", 45.0),
    # the note count passed a round number (`companion_events.counted`): the cheer the downloads use, a face to match
    "note_milestone": Reaction("cheer", "joy", 2.0, "happy", 3600.0),
    # pressed while falling, then standing again (`Extras.watch_catch`, I21 `int.catch_midair`): wide eyes, a clutch, relief
    "caught": Reaction("clutch_relief", "surprised", 1.4, "happy", 20.0),
}
#: A poke by mood, as the app's: a happy one giggles, a tired or cross one is miffed, the rest are curious.
POKE_BY_MOOD = {"happy": "poke_giggle", "proud": "poke_giggle", "sleepy": "poke_miffed", "startled": "poke_miffed", "bored": "poke_curious", "curious": "poke_curious"}


def _k(*rows: tuple[float, float, float, float]) -> bh.Keys:
    return rows


_TURN2 = _k((0, 1, 1, 0), (0.12, 1, 1.1, 0), (0.3, 0.14, 1.1, 0), (0.45, 1, 1.12, 0), (0.6, 0.14, 1.1, 0), (0.75, 1, 1.05, 0), (0.9, 1.03, 0.9, 0), (1, 1, 1, 0))
#: Acts only a reaction plays (`where` "react" keeps them out of the mind's own choice).
REACT_ACTS: dict[str, bh.Activity] = {
    "pat_happy": bh.Activity("stand", (1.8, 2.2), _k((0, 1, 1, 0), (0.15, 1.02, 0.9, 0.02), (0.3, 1, 1.03, 0), (0.5, 1.02, 0.92, 0.02), (0.7, 1, 1.02, 0), (1, 1, 1, 0)), (("play", -0.2),), where="react"),
    "rub_purr": bh.Activity("stand", (2.8, 3.6), _k((0, 1, 1, 0), (0.2, 1, 0.97, 0.05), (0.45, 1, 0.97, -0.05), (0.7, 1, 0.97, 0.05), (1, 1, 1, 0)), (("play", -0.15), ("rest", -0.05)), where="react"),
    "poke_giggle": bh.Activity("hop", (1.0, 1.4), _k((0, 1, 1, 0), (0.2, 1.04, 0.86, 0), (0.45, 0.96, 1.12, 0), (0.7, 1.03, 0.9, 0), (1, 1, 1, 0)), (("play", -0.2),), where="react"),
    "poke_miffed": bh.Activity("stand", (1.2, 1.6), _k((0, 1, 1, 0), (0.15, 1, 1.02, 0.06), (0.3, 1, 1.02, -0.06), (0.5, 1, 1.02, 0.04), (0.7, 1, 1, -0.02), (1, 1, 1, 0)), (), where="react"),
    "poke_curious": bh.Activity("look", (1.5, 2.0), _k((0, 1, 1, 0), (0.25, 0.97, 1.02, 0.04), (0.8, 0.97, 1.02, 0.04), (1, 1, 1, 0)), (("curiosity", -0.1),), where="react"),
    "flip_twirl": bh.Activity(((0, "hop"), (0.85, "land")), (1.2, 1.5), _TURN2, (("play", -0.4),), turns=(0.3, 0.6), where="react"),
    # a clutch (squashed small, leaning in), then a long breath out
    "clutch_relief": bh.Activity("stand", (1.2, 1.6), _k((0, 1, 1, 0), (0.12, 1.05, 0.88, 0.04), (0.4, 1.04, 0.9, 0.03), (0.65, 1, 1.07, 0), (0.85, 1, 0.97, 0), (1, 1, 1, 0)), (("rest", -0.05),), where="react"),
    "flinch": bh.Activity("look", (0.9, 1.2), _k((0, 1, 1, 0), (0.12, 0.96, 1.05, -0.07), (0.7, 0.97, 1.03, -0.05), (1, 1, 1, 0)), (), where="react"),
    "glance_window": bh.Activity("look", (2.0, 2.6), _k((0, 1, 1, 0), (0.15, 0.94, 1.09, 0.1), (0.45, 0.94, 1.09, 0.1), (0.55, 0.94, 1.09, -0.08), (0.85, 0.96, 1.04, -0.08), (1, 1, 1, 0)), (("curiosity", -0.1),), turns=(0.5,), where="react"),
    "relief": bh.Activity("stand", (1.6, 2.0), _k((0, 1, 1, 0), (0.3, 1.02, 1.07, 0), (0.6, 1.01, 0.94, 0), (1, 1, 1, 0)), (("rest", -0.05),), where="react"),
    "glance_screen": bh.Activity("look", (1.4, 1.8), _k((0, 1, 1, 0), (0.25, 0.96, 1.06, 0.08), (0.8, 0.96, 1.06, 0.08), (1, 1, 1, 0)), (), where="react"),
    "welcome_back": bh.Activity("wave", (1.8, 2.4), _k((0, 1, 1, 0), (0.2, 1, 1.02, 0.02), (0.8, 1, 1.02, 0.02), (1, 1, 1, 0)), (("play", -0.1),), where="react"),
    "chime_nod": bh.Activity("stand", (1.6, 2.0), _k((0, 1, 1, 0), (0.25, 1.01, 0.95, 0.02), (0.5, 1, 1, 0), (0.7, 1.01, 0.97, 0.02), (1, 1, 1, 0)), (), where="react"),
    "shiver": bh.Activity("stand", (2.4, 3.0), _k((0, 1, 1, 0), (0.1, 1, 0.98, 0.05), (0.2, 1, 1, -0.05), (0.3, 1, 0.98, 0.05), (0.4, 1, 1, -0.05), (0.55, 1, 0.98, 0.04), (0.7, 1, 1, -0.03), (1, 1, 1, 0)), (), where="react"),
    "cheer": bh.Activity("hop", (1.6, 2.2), _k((0, 1, 1, 0), (0.15, 1.04, 0.86, 0), (0.3, 0.96, 1.12, 0), (0.5, 1.04, 0.88, 0), (0.65, 0.96, 1.12, 0), (0.85, 1.02, 0.94, 0), (1, 1, 1, 0)), (("play", -0.3),), where="react"),
    "watch_drag": bh.Activity("look", (2.0, 2.8), _k((0, 1, 1, 0), (0.15, 0.96, 1.05, 0.09), (0.4, 0.96, 1.05, -0.09), (0.65, 0.96, 1.05, 0.09), (0.9, 0.97, 1.03, -0.05), (1, 1, 1, 0)), (("curiosity", -0.1),), where="react"),
    "dizzy_sway": bh.Activity("stand", (2.5, 4.0), _k((0, 1, 1, 0), (0.12, 1, 1.02, 0.08), (0.3, 1, 1.0, -0.08), (0.5, 1, 1.02, 0.07), (0.7, 1, 1.0, -0.07), (0.85, 1, 1.01, 0.04), (1, 1, 1, 0)), (), where="react"),
    "tickle_squirm": bh.Activity("hop", (1.5, 3.0), _k((0, 1, 1, 0), (0.08, 1.03, 0.94, 0.05), (0.16, 0.97, 1.04, -0.05), (0.24, 1.03, 0.94, 0.05), (0.32, 0.97, 1.04, -0.05), (0.4, 1.03, 0.94, 0.05), (0.48, 0.97, 1.04, -0.05), (0.6, 1.02, 0.96, 0.03), (0.75, 0.99, 1.02, -0.02), (1, 1, 1, 0)), (("play", -0.3),), where="react"),
    "boop_sneeze": bh.Activity("stand", (0.8, 1.4), _k((0, 1, 1, 0), (0.25, 1, 1.05, -0.1), (0.45, 1, 1.07, -0.12), (0.55, 1.03, 0.9, 0.08), (0.75, 1, 0.98, 0.02), (1, 1, 1, 0)), (), where="react"),
    "dusk_stretch": bh.Activity("stand", (2.8, 3.4), _k((0, 1, 1, 0), (0.2, 1.03, 0.94, 0), (0.5, 0.96, 1.1, 0), (0.7, 0.97, 1.08, 0.03), (0.85, 1.01, 0.97, 0), (1, 1, 1, 0)), (("rest", -0.1),), where="react"),
    "morning_wave": bh.Activity(((0, "wave"), (0.6, "blink"), (0.9, "stand")), (2.4, 3.0), _k((0, 1, 1, 0), (0.2, 1, 1.02, 0.02), (0.55, 1, 1.02, 0.02), (0.75, 0.98, 1.06, 0), (1, 1, 1, 0)), (("play", -0.1),), where="react"),
    "read_glasses": bh.Activity("look", (4.6, 5.4), _k((0, 1, 1, 0), (0.2, 0.95, 1.04, 0.12), (0.75, 0.95, 1.04, 0.12), (1, 1, 1, 0)), (("curiosity", -0.1),), where="react"),
    "remark_say": bh.Activity("stand", (2.2, 2.6), _k((0, 1, 1, 0), (0.15, 1.01, 0.97, 0.02), (0.8, 1.01, 0.97, 0.02), (1, 1, 1, 0)), (), where="react"),
    "peek_back": bh.Activity("look", (1.6, 2.0), _k((0, 1, 1, 0), (0.2, 0.95, 1.04, 0.12), (0.6, 0.95, 1.04, 0.12), (0.8, 0.98, 1.02, -0.03), (1, 1, 1, 0)), (("curiosity", -0.1),), where="react"),
    "nod_done": bh.Activity("stand", (1.4, 1.8), _k((0, 1, 1, 0), (0.2, 1.01, 0.95, 0.02), (0.4, 1, 1, 0), (0.6, 1.01, 0.95, 0.02), (0.8, 1, 1.01, 0), (1, 1, 1, 0)), (), where="react"),
    # a reminder falls due: the wave pose, a short shake at its top (the bell it rings is the app's; the card carries the other)
    "bell_ring": bh.Activity("wave", (2.4, 2.8), _k((0, 1, 1, 0), (0.12, 1, 1.03, 0.06), (0.22, 1, 1.03, -0.06), (0.32, 1, 1.03, 0.06), (0.42, 1, 1.03, -0.06), (0.52, 1, 1.03, 0.05), (0.64, 1, 1.02, -0.04), (0.8, 1, 1.01, 0.02), (1, 1, 1, 0)), (("play", -0.1),), where="react"),
    # the app's wince, its covered eyes and its puzzled head tilt, on the look and stand poses (no frame of their own)
    "wince": bh.Activity("look", (1.0, 1.4), _k((0, 1, 1, 0), (0.12, 0.96, 1.04, -0.06), (0.35, 0.97, 1.03, -0.04), (0.6, 0.98, 1.02, -0.02), (1, 1, 1, 0)), (), where="react"),
    "cover_eyes": bh.Activity("stand", (2.0, 2.6), _k((0, 1, 1, 0), (0.2, 1.01, 0.95, 0.03), (0.8, 1.01, 0.95, 0.03), (1, 1, 1, 0)), (), where="react"),
    "puzzle_tilt": bh.Activity("look", (1.6, 2.2), _k((0, 1, 1, 0), (0.25, 0.97, 1.02, 0.07), (0.55, 0.97, 1.02, 0.07), (0.75, 0.97, 1.02, -0.04), (1, 1, 1, 0)), (), where="react"),
    "perk_up": bh.Activity("look", (1.2, 1.6), _k((0, 1, 1, 0), (0.15, 0.97, 1.06, 0.02), (0.8, 0.98, 1.03, 0.02), (1, 1, 1, 0)), (), where="react"),
}
for _kind, _prio in {"flinch": 3, "poke_miffed": 2, "battery_low": 2, "idle_return": 2, "morning_hello": 2, "download_done": 2, "toast": 2, "reminder_bell": 2}.items():
    REACTIONS[_kind] = REACTIONS[_kind]._replace(prio=_prio)
#: The priority of the reaction each reaction-only act belongs to.
REACT_PRIO: dict[str, int] = {r.act: r.prio for r in REACTIONS.values() if r.act}
_REGISTERED: set[str] = set()


def register() -> None:
    """Add the prop and the plain acts and the reactions' own to the mind's tables, once."""
    if _REGISTERED:
        return
    _REGISTERED.add(__name__)
    props.register()
    for name, act in REACT_ACTS.items():
        bh.ACTIVITIES[name] = act
        bh.AMPLITUDE[name] = bh._amplitude(act.keys)
    for r in REACTIONS.values():
        if r.act:
            faces.ACT_FACES[r.act] = r.face


def _in_box(s: tuple[float, float, float], box: tuple[float, float, float, float], pad: float) -> bool:
    return box[0] - pad <= s[1] <= box[2] + pad and box[1] - pad <= s[2] <= box[3] + pad


def _seg_dist(x: float, y: float, a: tuple[float, float, float], c: tuple[float, float, float]) -> float:
    """Distance from (x, y) to the segment between two samples."""
    dx, dy = c[1] - a[1], c[2] - a[2]
    span = dx * dx + dy * dy
    u = 0.0 if span == 0 else max(0.0, min(1.0, ((x - a[1]) * dx + (y - a[2]) * dy) / span))
    return math.hypot(a[1] + u * dx - x, a[2] + u * dy - y)


class Pointer:
    """A classifier of the pointer's last second and a half: the gesture it just made, if any."""

    def __init__(self) -> None:
        self.samples: deque[tuple[float, float, float]] = deque()
        self.inside_since: float | None = None

    def feed(self, now: float, x: float, y: float) -> None:
        if not self.samples or (x, y) != self.samples[-1][1:] or now - self.samples[-1][0] > 0.2:
            self.samples.append((now, x, y))
        while self.samples and now - self.samples[0][0] > SAMPLE_KEEP:
            self.samples.popleft()

    def clear(self) -> None:
        self.samples.clear()
        self.inside_since = None

    def speed(self, now: float, over: float) -> float:
        """Path length a second over the last `over` seconds."""
        pts = [s for s in self.samples if now - s[0] <= over]
        if len(pts) < 2:
            return 0.0
        path = sum(math.hypot(b[1] - a[1], b[2] - a[2]) for a, b in zip(pts, pts[1:]))
        return path / max(0.016, pts[-1][0] - pts[0][0])

    @staticmethod
    def reversals(pts: list[tuple[float, float, float]], axis: int, swing: float) -> int:
        """Turns of direction along an axis (1 x, 2 y), each after a stroke of at least `swing` px that went there
        fairly straight (the travel at most `STROKE_WASTE` times the distance), so a hand's tremor does not count."""
        n, direction, anchor, travel = 0, 0, pts[0][axis] if pts else 0.0, 0.0
        for prev, p in zip(pts, pts[1:]):
            travel += abs(p[axis] - prev[axis])
            d = p[axis] - anchor
            if abs(d) >= swing:
                sign = 1 if d > 0 else -1
                if travel <= STROKE_WASTE * abs(d):
                    n += 1 if direction and sign != direction else 0
                    direction = sign
                anchor, travel = p[axis], 0.0
            elif direction and d * direction > 0:
                anchor, travel = p[axis], 0.0
        return n

    def classify(self, now: float, box: tuple[float, float, float, float], k: float, mood: str) -> str | None:
        """`pat`, `rub`, `poke`, `flip`, `flinch`, `hover` or None, from the samples and the figure's drawn box."""
        if len(self.samples) < 2:
            return None
        pad = 6.0 * k
        last = self.samples[-1]
        if self._flipped(now, box, k):
            return "flip"
        if not _in_box(last, box, pad):
            self.inside_since = None
            return self._poke(now, box, k, pad) or self._flinch(now, box, k, last)
        self.inside_since = self.inside_since if self.inside_since is not None else last[0]
        return self._stroke(now, box, k, pad) or self._hover(now, k)

    def _flipped(self, now: float, box: tuple[float, float, float, float], k: float) -> bool:
        """A fast swipe straight across the figure, from outside one side to outside the other."""
        lx, t, r, b = box
        quick = [s for s in self.samples if now - s[0] <= 0.3]
        if self.speed(now, 0.3) < SWIPE_SPEED * k or len(quick) < 2:
            return False
        xs = [s[1] for s in quick]
        return min(xs) < lx and max(xs) > r and all(t <= s[2] <= b for s in quick if lx <= s[1] <= r)

    def _flinch(self, now: float, box: tuple[float, float, float, float], k: float, last: tuple[float, float, float]) -> str | None:
        """A fast swipe that went past the figure: its path came within reach and went on. An approach that stops
        beside it ends at its nearest point, so it is not one (INBOX 1692)."""
        lx, t, r, b = box
        if not self._swipe_ended(now, k):
            return None
        cx, cy = (lx + r) / 2, (t + b) / 2
        pts = [s for s in self.samples if now - s[0] <= 0.4]
        near = min((_seg_dist(cx, cy, a, c) for a, c in zip(pts, pts[1:])), default=math.inf)
        reach = FLINCH_REACH * k + (r - lx) / 2
        if near <= reach and math.hypot(last[1] - cx, last[2] - cy) >= near + FLINCH_REACH * k * 0.5:
            return "flinch"
        return None

    def _poke(self, now: float, box: tuple[float, float, float, float], k: float, pad: float) -> str | None:
        """A jab: in fast, a moment inside, and back out the way it came. Read once the pointer has left."""
        pts = list(self.samples)
        j = len(pts) - 1
        while j >= 0 and not _in_box(pts[j], box, pad):
            j -= 1
        if j < 1 or j == len(pts) - 1 or now - pts[j + 1][0] > POKE_LEFT:
            return None
        i = j
        while i > 0 and _in_box(pts[i - 1], box, pad):
            i -= 1
        if i == 0 or pts[j][0] - pts[i][0] > POKE_DWELL:
            return None
        into = (pts[i][1] - pts[i - 1][1], pts[i][2] - pts[i - 1][2])
        out = (pts[j + 1][1] - pts[j][1], pts[j + 1][2] - pts[j][2])
        if into[0] * out[0] + into[1] * out[1] >= 0:  # straight on through is a pass, not a jab
            return None
        peak = max((self._leg(a, c) for a, c in zip(pts[: i + 1], pts[1 : i + 1]) if pts[i][0] - c[0] <= POKE_WINDOW), default=0.0)
        return self._jab(peak >= POKE_SPEED * k, pts[i : j + 1], box, pts[i - 1])

    def _jab(
        self, fast: bool, inside: list[tuple[float, float, float]], box: tuple[float, float, float, float], came_from: tuple[float, float, float]
    ) -> str | None:
        """A jab that was fast enough: a boop when its tip landed on the nose, else a poke. The tip is the point inside
        farthest from where the jab came in (its turning point), not any point it passed on the way."""
        if not fast:
            return None
        tip = max(inside, key=lambda p: math.hypot(p[1] - came_from[1], p[2] - came_from[2]))
        return "boop" if self._on_nose(tip, box) else "poke"

    @staticmethod
    def _on_nose(p: tuple[float, float, float], box: tuple[float, float, float, float]) -> bool:
        """Whether the point `p` is on the nose: the middle of the face, between `NOSE_TOP` and the head's lower edge."""
        lx, t, r, b = box
        h = b - t
        return abs(p[1] - (lx + r) / 2) <= NOSE_HALF * (r - lx) and t + NOSE_TOP * h <= p[2] <= t + HEAD_ZONE * h

    def _stroke(self, now: float, box: tuple[float, float, float, float], k: float, pad: float) -> str | None:
        """Strokes on the figure: dips on the head are a pat, sweeps along the body a rub."""
        lx, t, r, b = box
        inside = [s for s in self.samples if _in_box(s, box, pad)]
        head = [s for s in inside if now - s[0] <= PAT_WINDOW and s[2] <= t + HEAD_ZONE * (b - t)]
        if len(head) >= 4 and self.reversals(head, 2, PAT_DIP * k) >= PAT_REVERSALS and self._spread(head, 1) <= (r - lx):
            return "pat"
        if self._tickled(inside, now, box, k):
            return "tickle"
        body = [s for s in inside if now - s[0] <= RUB_WINDOW]
        if len(body) >= 6 and self.reversals(body, 1, RUB_SWING * k) >= RUB_REVERSALS and self._spread(body, 2) <= RUB_FLAT * (b - t):
            return "rub"
        return None

    def _tickled(self, inside: list[tuple[float, float, float]], now: float, box: tuple[float, float, float, float], k: float) -> bool:
        """A fast small rub on the body below the head (see `TICKLE_SWING`)."""
        _lx, t, _r, b = box
        low = [s for s in inside if now - s[0] <= TICKLE_WINDOW and s[2] > t + HEAD_ZONE * (b - t)]
        across = self._spread(low, 1)
        return (
            len(low) >= 8
            and self.reversals(low, 1, TICKLE_SWING * k) >= TICKLE_REVERSALS
            and across <= TICKLE_SPAN * k
            and self._spread(low, 2) <= TICKLE_FLAT * across
        )

    def _hover(self, now: float, k: float) -> str | None:
        if self.inside_since is not None and now - self.inside_since >= HOVER_FOR and self.speed(now, HOVER_FOR) <= HOVER_STILL * k:
            return "hover"
        return None

    def _swipe_ended(self, now: float, k: float) -> bool:
        """A fast swipe that has just slowed to a stop: the leg's peak over the last 0.4 s was a swipe, now it is slow."""
        pts = [s for s in self.samples if now - s[0] <= 0.4]
        peak = max((self._leg(a, c) for a, c in zip(pts, pts[1:])), default=0.0)
        return peak >= SWIPE_SPEED * k * 0.9 and self.speed(now, 0.12) <= peak * 0.5

    @staticmethod
    def _leg(a: tuple[float, float, float], c: tuple[float, float, float]) -> float:
        return math.hypot(c[1] - a[1], c[2] - a[2]) / max(0.016, c[0] - a[0])

    @staticmethod
    def _spread(pts: list, axis: int) -> float:
        vals = [p[axis] for p in pts]
        return max(vals) - min(vals) if vals else 0.0


def _bucketed(pts: list[tuple[float, float, float]]) -> list[tuple[float, float, float]]:
    """The window's points averaged over `SHAKE_BUCKET` s: a 1000 Hz mouse's pixel jitter averages out, and a few dozen
    points are left to read whatever the pointer's rate."""
    out: list[list[float]] = []
    first, slot = pts[0][0], -1
    for t, x, y in pts:
        n = int((t - first) / SHAKE_BUCKET)
        if n != slot:
            out.append([0.0, 0.0, 0.0, 0.0])
            slot = n
        b = out[-1]
        b[0] += t
        b[1] += x
        b[2] += y
        b[3] += 1.0
    return [(b[0] / b[3], b[1] / b[3], b[2] / b[3]) for b in out]


def shake_flips(trail: list[tuple[float, float, float]], now: float, k: float) -> int:
    """Direction flips of a carried figure's pointer over the last `SHAKE_WINDOW` s along the best of `SHAKE_AXES`
    directions: how hard it was shaken. `trail` is `(time, x, y)`, at any pointer rate. A shake goes back and forth
    about a point, so the motion across its axis stays small beside the motion along it; a drag with a wobble
    travels far across the wobble's axis and is not one. Strokes under `SHAKE_SWING` px (scaled by `k`) are tremor."""
    raw = [p for p in trail if now - p[0] <= SHAKE_WINDOW]
    if len(raw) < 4:
        return 0
    pts = _bucketed(raw) if len(raw) > SHAKE_RAW else raw
    best = 0
    for a in range(SHAKE_AXES):
        ux, uy = math.cos(math.pi * a / SHAKE_AXES), math.sin(math.pi * a / SHAKE_AXES)
        along = [(p[0], p[1] * ux + p[2] * uy, 0.0) for p in pts]
        flips = Pointer.reversals(along, 1, SHAKE_SWING * k)
        if flips <= best:
            continue
        across = [p[2] * ux - p[1] * uy for p in pts]
        if max(across) - min(across) <= SHAKE_ACROSS * (max(q[1] for q in along) - min(q[1] for q in along)):
            best = flips
    return best


def ease(t: float, length: float) -> int:
    """The step (0 to 3) of a face's ease at `t` seconds into `length`: up over a quarter second, down over the last."""
    if t < 0.0 or t >= length:
        return 0
    rest = length - t
    up = 1 if t < 0.12 else 2 if t < 0.26 else 3
    down = 1 if rest < 0.15 else 2 if rest < 0.3 else 3
    return min(up, down)


def ease_marks(start: float, length: float) -> list[float]:
    return [start + 0.12, start + 0.26, start + length - 0.3, start + length - 0.15, start + length]


class Extras:
    """Everything the desk figure adds to the engine's roaming (one per engine)."""

    def __init__(self, engine: Any) -> None:
        register()
        self.e = engine
        self.rng = random.Random(engine.life_rng.getstate()[1][1])
        self.micro = faces.Micro(random.Random(engine.life_rng.getstate()[1][2]), 0.0)
        self.saccade = gaze.Saccade(random.Random(engine.life_rng.getstate()[1][3]))  # its own stream: no other draw moves
        self.pointer_state = Pointer()
        self.wind = windspirit.Wind()
        #: When the next in-place act may start; `inf` stops them (tests that want a still stand).
        self.seen_at = 0.0
        self.act_ready: float | None = None  # set on the first stand it sees: the engine's clock starts when it is first updated
        self.cool: dict[str, float] = {}
        self.over: tuple[str, float, float] | None = None
        self.hold: float | None = None
        self.last: list[str] = []
        self.pets: list[float] = []  # when the last pats and rubs began
        self.near = False
        #: Where the pointer was last and when it last moved: it is watched finely only while it moves near the figure.
        self.seen: tuple[int, int] | None = None
        self.moved_at = -1e9
        #: When a press arrived on a fall or a flight (None: none owed): it clutches once it stands again.
        self.caught_at: float | None = None

    # --- what to draw ------------------------------------------------------------------------

    def view(self, now: float) -> tuple[tuple[str, int, int] | None, tuple[str, int] | None]:
        """`(prop, face)` to draw now (the engine's `Output.prop` and `Output.face`)."""
        e = self.e
        if e.reduced:
            return None, None
        self.watch_catch(now)
        wind = self.wind.view(e, now)  # E5: a floater's ride (windspirit.py); an act's own prop wins where both are due
        if e.state not in FACE_STATES:
            return wind, None
        prop = None
        face = self._override(now)
        if e.state == "act" and e.act:
            length = max(0.01, e.act_len)
            t = now - e.act_started
            prop = props.view(e.act, t / length, t, length)
            kind = faces.ACT_FACES.get(e.act)
            if face is None and kind and (lv := ease(t, length)):
                face = (kind, lv)
        if face is None and e.state in ("stand", "sit"):
            self.micro.tick(now, e.mind.mood(now, e.hour), self._free_for_micro())
            face = self.micro.view(now)
        return prop or wind, gaze.worn(face, self.saccade.tick(now, self._attending()))

    def watch_catch(self, now: float) -> None:
        """A press that arrives while it falls or flies is a catch (`int.catch_midair`): once it stands again within
        `CATCH_WAIT` s it clutches and is relieved (`caught`). Seen on the draw, since nothing else ticks while it is held."""
        e = self.e
        if e.state == "pressed":
            self.caught_at = now if e.pre_press in ("fall", "fly") else None
        elif self.caught_at is not None and e.state in ("stand", "sit"):
            late = now - self.caught_at > CATCH_WAIT
            self.caught_at = None
            if not late:
                self.fire("caught", now)

    def _attending(self) -> bool:
        """Holding its eyes on something: a look between two blinks, or an act drawn on the look frame (`gaze.ATTEND_ACTS`)."""
        e = self.e
        if not self._free_for_micro():
            return False
        return e.state == "act" and e.act in gaze.ATTEND_ACTS or e.state == "stand" and bool(e.flash) and e.flash[0] == "look"

    def _free_for_micro(self) -> bool:
        e = self.e
        return not (e.quiet or e.busy or e.card is not None)

    def _override(self, now: float) -> tuple[str, int] | None:
        if self.over is None:
            return None
        kind, start, length = self.over
        lv = ease(now - start, length)
        if not lv:
            self.over = None
            return None
        return kind, lv

    @staticmethod
    def calm(act: str | None) -> bool:
        """A prop or plain act whose pose barely moves (a breath, a page turn): it is drawn at the rest pace
        (`REST_DRAW_MS`), not at the walk's, so a minute of reading costs what a minute of standing does."""
        if bh.AMPLITUDE.get(act, 1.0) >= CALM_AMPLITUDE:
            return False
        # A small stand act with no turn (dust_off: 1 s, a 0.06 shake) is calm too: at the walk's pace it drew 14 to 16 a second.
        small = act in bh.ACTIVITIES and bh.ACTIVITIES[act].frame == "stand" and not bh.ACTIVITIES[act].turns and bh.AMPLITUDE[act] < SMALL_AMPLITUDE
        return act in props.PROP_ACTS or act in props.PLAIN_ACTS or act in props.SPELL_ACTS or small

    def _marks(self, now: float) -> list[float]:
        """The moments after `now` a reaction's face next steps. The micro-expressions' and the acts' own steps are
        0.2 s or more apart and the streams' tick (`FLOW_TICK_MS`) already looks six times a second, so they ride it
        and cost no wake of their own (measured: +50 wakes a minute when each had one)."""
        if self.over is None:
            return []
        return [m for m in ease_marks(self.over[1], self.over[2]) if m > now]

    def wake_ms(self, now: float) -> int | None:
        """How soon to look again for the sake of the face, the prop and the pointer, or None."""
        if self.e.reduced:
            return None
        soon = self._marks(now)
        ms = None if not soon else max(MIN_WAKE_MS, int(math.ceil((min(soon) - now) * 1000)) + 1)
        swirl = self.wind.next_step(now)  # an eddy or a spiral still turning
        if swirl is not None:
            ms = max(MIN_WAKE_MS, int(math.ceil(swirl * 1000)) + 1) if ms is None else min(ms, max(MIN_WAKE_MS, int(math.ceil(swirl * 1000)) + 1))
        if self.near and now - self.moved_at < WATCH_FOR:
            ms = WATCH_MS if ms is None else min(ms, WATCH_MS)
        return ms

    # --- the pointer -------------------------------------------------------------------------

    def pointer(self, now: float, pointer: tuple[int, int]) -> bool:
        """Feed the pointer; True when a gesture was answered (the caller then skips the plain look)."""
        e = self.e
        frame = e._frame(now)
        x, y, _clip = e._display(frame)
        lx, t, r, b = e._box(frame)
        box = (x + lx, y + t, x + r, y + b)
        k = e._scale()
        w = box[2] - box[0]
        self.near = (box[0] - WATCH_REACH * w <= pointer[0] <= box[2] + WATCH_REACH * w
                     and box[1] - WATCH_REACH * w <= pointer[1] <= box[3] + WATCH_REACH * w)
        if not self.near:
            self.pointer_state.clear()
            return False
        if pointer != self.seen:
            self.seen, self.moved_at = pointer, now
        self.pointer_state.feed(now, float(pointer[0]), float(pointer[1]))
        if e.state not in TOUCH_FREE and not self.hanging():
            return False
        kind = self.pointer_state.classify(now, box, k, e.mind.mood(now, e.hour))
        if kind is None:
            return False
        if e.quiet or e.busy:  # it does not play for someone who is working, but a poke puzzles it
            return kind == "poke" and self.fire("confused", now, toward=pointer[0])
        if kind == "poke":
            kind = POKE_BY_MOOD.get(e.mind.mood(now, e.hour), "poke_curious")
        if self.fire(self._warmed(kind, now), now, toward=pointer[0]):
            if kind in ("pat", "rub"):
                self.pets = [*(p for p in self.pets if now - p <= LOVE_STREAK), now]
            self.pointer_state.clear()
            return True
        return False

    def _warmed(self, kind: str, now: float) -> str:
        """A pat or rub right after waking is shy, and the third inside `LOVE_STREAK` s is loved."""
        if kind not in ("pat", "rub"):
            return kind
        if sum(1 for p in self.pets if now - p <= LOVE_STREAK) + 1 >= LOVE_PETS:
            return f"{kind}_love"
        return f"{kind}_shy" if now - self.e.woke_at <= SHY_FOR else kind

    # --- reactions ---------------------------------------------------------------------------

    def _allowed(self, r: Reaction | None, kind: str, now: float) -> bool:
        """Whether a reaction may start now: the state, the cooldown, nobody typing, no card, no running reaction."""
        e = self.e
        if r is None or e.reduced or ((e.busy if r.touch else e.quiet) and not r.busy_ok) or e.card is not None or now < self.cool.get(kind, -1e9):
            return False
        free = TOUCH_FREE if r.touch else SCREEN_FREE
        if r.prio >= 2:
            free = (*free, "sit", "sleep", "walk")
        if e.state not in free:
            return False
        if e.state == "act" and e.act in REACT_ACTS:  # a screen event of the same rank never breaks a reaction
            return r.touch or r.prio > REACT_PRIO.get(e.act or "", 1)
        return True

    def fire(self, kind: str, now: float, toward: float | None = None, seconds: float | None = None) -> bool:
        """Play a reaction if it is allowed now (state, cooldown, nobody typing). True when it started. `seconds`
        replaces the reaction's own length (a dizzy sway is drawn per shake)."""
        e = self.e
        r = REACTIONS.get(kind)
        base = kind.rsplit("_", 1)[0] if kind.endswith(("_shy", "_love")) else kind  # a face of a pat is still a pat
        if e.state == "hang":
            return self._fire_hanging(r, base, kind, now, toward)
        if r is None or not self._allowed(r, base, now):
            return False
        self.cool[base] = now + r.cooldown
        self.last = [*self.last[-7:], kind]
        if r.feel:
            e.mind.feel(r.feel, now)
        e.last_active = now
        if toward is not None and r.touch:
            e.facing = -1 if toward < e.x + e.size[0] / 2 else 1
        length = r.seconds if seconds is None else seconds
        self.over = (r.face, now, length)
        if r.act:
            self._play(r.act, length, now)
        return True

    def hanging(self) -> bool:
        """Holding an edge with nothing in hand: not scrabbling, pulling up, winding up a swing or letting go."""
        e = self.e
        return e.state == "hang" and e.pulling is None and e.swing_to is None and not e.releasing and not e.reduced

    def _fire_hanging(self, r: Reaction | None, base: str, kind: str, now: float, toward: float | None) -> bool:
        """A reaction while hanging (INBOX 1721 a: a pat and a typing burst went unanswered). An act would drop the grip,
        so the hang-safe answer is the reaction's face, a kick of the swing and a look toward the pointer; it stays
        on the edge. Screen events are answered the same way (not queued: a hang lasts minutes, longer than the runner
        keeps an event). Only a hang that is changing (scrabble, pull-up, swing, letting go) leaves one to the runner's
        queue, which gives it up after `SCREEN_WAIT` s."""
        e = self.e
        if r is None or not self.hanging() or ((e.busy if r.touch else e.quiet) and not r.busy_ok) or e.card is not None:
            return False
        if now < self.cool.get(base, -1e9):
            return False
        self.cool[base] = now + r.cooldown
        self.last = [*self.last[-7:], kind]
        if r.feel:
            e.mind.feel(r.feel, now)
        e.last_active = now
        if toward is not None and r.touch:
            e.facing = -1 if toward < e.x + e.size[0] / 2 else 1
        e.hang_kick_at = now
        self.over = (r.face, now, r.seconds)
        return True

    def _play(self, name: str, seconds: float, now: float) -> None:
        e = self.e
        if self.hold is None and e.state in ("stand", "sit"):
            self.hold = e.state_until
        if e.state in ("sleep", "sit"):
            e._enter("stand", now)
        e.mind.did(name, now)
        e.act = name
        e._enter("act", now)
        e.act_var = bh.vary(e.var_rng)
        e.act_len = seconds
        e.state_until = now + seconds

    def after_act(self, now: float) -> None:
        """An act ended and the stand began again: the stand's own end (a trip, a climb) is not pushed back."""
        if self.hold is not None:
            e = self.e
            if e.state == "stand" and self.hold > now:
                e.state_until = min(e.state_until, self.hold)
            e.next_ambient = max(e.next_ambient, now + AFTER_ACT_QUIET)  # no blink on the heels of a short act
            self.hold = None

    # --- life while it stands ----------------------------------------------------------------

    def _free(self) -> bool:
        """Standing with nothing else going on: no trip, card, caret, typing or turn."""
        e = self.e
        if e.state != "stand" or e.reduced or e.quiet or e.busy or e.card is not None or e.turn_to:
            return False
        return not (e.trip or e.target is not None or e.caret is not None or e.pending is not None)

    def life(self, now: float) -> None:
        """Now and then, while it stands with nothing else to do, it does something in place. Asked every tick: a
        tick that is not a free stand (a trip, a card, a stall of the clock) holds the next one back, so an act never
        starts the instant the figure is free again."""
        e = self.e
        if self.act_ready is None or now - self.seen_at > LIFE_STALL:
            self.act_ready = now + self.rng.uniform(*LIFE_EVERY)
        self.seen_at = now
        if not self._free():
            self.act_ready = max(self.act_ready, now + LIFE_SETTLE)
            return
        if now < self.act_ready:
            return
        self.act_ready = now + self.rng.uniform(*LIFE_EVERY)
        name = e.mind.pick(self.rng, now, e.gait, e.hour, "perch" if e.perch else "")
        if self.hold is None:
            self.hold = e.state_until
        kept = e.rng.getstate()  # the act's own length is drawn from the engine's stream: put it back, so a seed's trips are unchanged
        e._start_act(name, now)
        e.rng.setstate(kept)
