"""The engine's answer: which frame, face, tail and flow to draw for a state (audit-1028 K24, moved whole out of engine.py).

`FramesMixin` holds the methods `Engine` inherits that turn the state into a picture (`_frame` and its state, blink, idle, lower-body and tail helpers). It reads
only `engine_consts` and the sibling behaviour modules; the time-keeping that reads `IDLE_SIT` stays in `engine.py`."""

from __future__ import annotations

import math
from . import behaviour as bh, standing, wisps
from .engine_consts import (
    BLINK_PHASES,
    CARD_SWAP,
    CARD_WALK_SWAP,
    DRIFT_BREATH_S,
    FLOW_FROZEN,
    FLOW_TICK_MS,
    FRAME_OF,
    HOP_RISE,
    IDLE_FPS,
    IDLE_FRAMES,
    IDLE_SLOWEST,
    IDLE_SPREAD,
    NOTICE_NEAR,
    REST_LIFE,
    STRIDE,
    TAIL_LAYER_MS,
    TAIL_TOUCHED_FOR,
    WALK_FRAMES,
    WALK_SPEED,
    WAVE_FPS,
)


class FramesMixin:
    # --- the answer ------------------------------------------------------------------------------------

    def _fixed_frame(self, s: str) -> str:
        if s == "held":
            return self._held_frame()
        if s == "pressed" and self.pre_press == "hang":
            return "hang"  # a press on a hanger keeps the hang pose until it is dragged (INBOX 1690 c)
        return FRAME_OF[s]

    def _frame(self, now: float) -> str:
        name = self._state_frame(now)
        #: A wave swings its arm (INBOX 1696: one held frame read as a salute), wherever it is drawn: the wave
        #: state, an act that waves, a dance.
        if name == "wave" and self.wave_frames:
            return f"wave{int(now * WAVE_FPS + 1e-6) % self.wave_frames}"
        return self._extra_name(name, now)

    def _state_frame(self, now: float) -> str:
        s = self.state
        if s in ("card", "walk", "drift"):
            return self._step_frame(now, s)
        if s == "act":
            return bh.activity_frame(bh.ACTIVITIES[self.act or "breathe"], (now - self.act_started) / max(0.01, self.act_len))
        if s == "crouch":
            return "land"
        if s == "warp" and self.warp is not None and self.warp["kind"] == "edge":
            return self._edge_warp_frame(now)
        if s in FRAME_OF:
            return self._fixed_frame(s)
        if s == "fly":
            return self._flying_frame(now)
        if s in ("rise", "peek"):
            return self._edge_frame(now)
        if s == "stand":
            return self._stand_frame(now)
        if s == "sit" and self.flash:
            return self._sit_frame(now)
        return s  # sit, sleep, wave, fall, land

    def _edge_warp_frame(self, now: float) -> str:
        """Off one side and on at the other: a floater flows on its idle cycle, a walker steps."""
        if self.gait == "float":
            return self._stream_frame(now)
        return f"walk{int((now - self.warp['t0']) / (0.75 / self.walk_frames)) % self.walk_frames}"

    def _flying_frame(self, now: float) -> str:
        """A bonk shows the startled hop only when the figure is not turning: a picture swap in the middle of a
        spin was the snap (INBOX 1683); the contact is felt in the turn rate instead."""
        return "hop" if now < self.bonk_until and self.laid else self._fly_frame()

    def _step_frame(self, now: float, s: str) -> str:
        if s == "card":
            return f"card{int(now / CARD_SWAP) % 2}"
        if self.card is not None:
            return f"card{int((now - self.walk_started) / CARD_WALK_SWAP) % 2}"
        if self.gait == "float":
            return self._stream_frame(now)
        if self.hopping and self.hop_lift > 0.35 * HOP_RISE * self.size[1]:
            return "hop"  # tucked while it is in the air, the stride on the ground
        return f"walk{int(self.travel / (STRIDE * WALK_FRAMES / self.walk_frames * self._scale())) % self.walk_frames}"

    def _stream_frame(self, now: float) -> str:
        """A floater on the move: its idle cycle (tail and streams flowing, eyes open), never the walk cycle, whose
        shipped Atlas frames shut the eyes on every other step and bob the body (INBOX 1692: "it still looks like it
        hobbles along and its eyes blick ferociously ... it floats like a wind spirit")."""
        if self.idle_frames <= 0:
            return "stand"
        return f"idle{int(now * IDLE_FPS + 1e-6) % self.idle_frames}"

    def _edge_frame(self, now: float) -> str:
        if self.state == "rise":
            frame = "hop" if self.gait == "walk" else self._stream_frame(now)
            if self.then == "peek_top" or (self.then == "hang" and self._rise_drawn(now) + self._box(frame)[1] < self.current_monitor().area[1]):
                return "hang"  # its head would pass the top of the screen: hands up, in the pose that fits
            return frame
        if self.peek_edge == "top":
            return "spin24" if self.peek_flip else "hang"
        if self.peek_edge in ("left", "right") and "lean" in self.extra_frames:
            return "lean"  # the side edge, arm up on it (L-ui-modernisation-41)
        return "stand" if self.sink < self.sink_max * 0.5 or now - self.peek_started < 0.8 else "look"

    def _blink_step(self, now: float) -> tuple[int | None, float]:
        """The phase of the blink under way: `(step, next_change)`, step 1 or 2 for a light or a half lid drawn over the open
        picture, 0 for the shut one, None when no blink shows (or a motion cannot draw a lid: reduced, or no face layer)."""
        if not self.flash or self.flash[0] != "blink":
            return None, math.inf
        span = self.blink_for
        u = (now - (self.flash[1] - span)) / span
        k = max(i for i, (at, _s) in enumerate(BLINK_PHASES) if u >= at - 1e-9) if u > 0 else 0
        nxt = BLINK_PHASES[k + 1][0] if k + 1 < len(BLINK_PHASES) else 1.0
        return BLINK_PHASES[k][1], self.flash[1] - span + nxt * span

    def _blink_face(self, now: float, frame: str, face: tuple[str, int] | None) -> tuple[str, int] | None:
        """`face` with the blink's lids over it: the light and half lids are drawn over the open picture, over an expression too
        (`kind|step`, `faces.draw`); the shut step of a plain blink is the shipped picture, so no face."""
        lid = self._blink_step(now)[0] if frame in ("sit", "stand") or frame.startswith("idle") else None
        if lid is None or not (lid or face):
            return face
        return (f"{face[0]}|{lid or 3}", face[1]) if face else ("blink", lid)

    def _sit_frame(self, now: float) -> str:
        """A sit: its own picture, or its lids over the sat figure's eyes (`SpriteSet` derives the shut frame)."""
        step = self._blink_step(now)[0]
        return "sit" if not self.flash or step or (step == 0 and self.ex.view(now)[1]) else "sitblink"

    def _flash_due(self, now: float) -> float:
        """When the picture next changes for a blink or a look under way."""
        return min(self._blink_step(now)[1], self.flash[1]) if self.flash else math.inf

    def _stand_frame(self, now: float) -> str:
        if self.flash:
            step = self._blink_step(now)[0]
            if step or (step == 0 and self.flash[0] == "blink" and self.ex.view(now)[1]):  # a lid over the open picture (`_output`)
                return f"idle{self._idle_index(now)}" if self._idling() else "stand"  # (shut too, under an expression: it keeps its mouth)
            return self.flash[0]
        return f"idle{self._idle_index(now)}" if self._idling() else "stand"

    def _idling(self) -> bool:
        """Standing with life in its parts: not reduced, frames present. Typing keeps it in
        place, not lifeless (INBOX 1670: "it is also not animated")."""
        return self.state == "stand" and not self.reduced and self.idle_frames > 0

    def _idle_fps(self) -> float:
        """Frames a second: a shipped set of fewer frames plays slower, so the cycle stays 4 s."""
        return IDLE_FPS * max(1, self.idle_frames) / IDLE_FRAMES

    def _idle_cycle(self, now: float) -> tuple[float, float]:
        """(start, length) of the idle cycle `now` is in. Each cycle runs a little faster or slower than
        the last, from its own seeded stream, so the breath and sway never line up twice (research A7)."""
        t = max(0.0, now - self.idle_start)
        nominal = max(1, self.idle_frames) / self._idle_fps()
        while self._edges[-1] <= t:
            self._edges.append(self._edges[-1] + nominal * standing.scale(self.mind.mood(self.idle_start + self._edges[-1], self.hour), self.idle_start + self._edges[-1] - self.exerted_at) / (1.0 + self.idle_rng.uniform(-IDLE_SLOWEST, IDLE_SPREAD)))
        k = next(i for i in range(len(self._edges) - 1, 0, -1) if self._edges[i - 1] <= t)
        return self.idle_start + self._edges[k - 1], self._edges[k] - self._edges[k - 1]

    def _idle_index(self, now: float) -> int:
        start, length = self._idle_cycle(now)
        return min(self.idle_frames - 1, int((now - start) / length * self.idle_frames + 1e-6)) % self.idle_frames

    def _idle_next(self, now: float) -> float:
        """When the idle picture next changes."""
        start, length = self._idle_cycle(now)
        step = length / self.idle_frames
        return start + (math.floor((now - start) / step + 1e-6) + 1) * step

    def _lower_state(self, now: float, face: tuple[str, int] | None) -> str:
        """What the lower body is doing, for `bh.FLOW_LOWER` (atlascat-1108 C4, C5): the base state (`_lower_base`) read
        with the act, the speed and how long it has lasted (`_lower_spell`); "" for the frame's own row."""
        return self._lower_spell(now, self._lower_base(now, face))

    def _lower_spell(self, now: float, base: str) -> str:
        """A state of the lower body's own beyond the base ones (atlascat-1108 C5): a twirl's spiral (and its 2.5 s unwinding),
        a glad act's hem kick, a seated act's coil, a fast glide's billow, and at rest a tired heaviness, an excited flutter,
        a long sit spread flat (a pool), a calm stand's slow ripple."""
        s, act = self.state, self.act if self.state == "act" else ""
        if act in bh.TWIRL_ACTS:
            self._twirl_at = now
        if now - self._twirl_at < bh.SPIRAL_FOR:
            return "spiral"
        if act in bh.HEM_ACTS:
            return "hem_kick"
        if act in bh.COIL_ACTS:
            return "coil"
        if base == "glide":
            fast = self.mode == "dash" or abs(self.vx_px) >= bh.BILLOW_SPEED * WALK_SPEED * self._scale()
            return "billow" if fast else base
        return self._lower_rest(now, base) if s in ("stand", "sit") else base

    def _lower_rest(self, now: float, base: str) -> str:
        """The resting spells: sleepy is heavy, a glad reaction flutters, a sit of `POOL_AFTER` s is a pool, and a calm stand
        ripples for `RIPPLE_FOR` s of every `RIPPLE_EVERY` once `RIPPLE_AT` s in. A sad or startled figure keeps its own."""
        if base in ("sad", "startle"):
            return base
        if self._mood(now) == "sleepy":
            return "heavy"
        if self.mind.event == "happy" and 0.0 <= now - self.mind.event_at < bh.FLUTTER_FOR:
            return "flutter"
        held = now - self.state_at
        if self.state == "sit":
            return "pool" if held >= bh.POOL_AFTER else base
        return "ripple_calm" if base == "" and bh.RIPPLE_AT <= held % bh.RIPPLE_EVERY < bh.RIPPLE_AT + bh.RIPPLE_FOR else base

    def _lower_base(self, now: float, face: tuple[str, int] | None) -> str:
        """What the lower body is doing, for `bh.FLOW_LOWER` (atlascat-1108 C4): lying in a nap, thinking, sad, startled,
        lounging in a long sit, gliding on the move; "" for the frame's own row."""
        s = self.state
        if s != self._seen_state:
            self._seen_state, self.state_at = s, now  # read here, not in `_enter`: a sit counts from its first picture
        if s == "sleep":
            return "lie" if self.nap_until else ""
        over = self.ex.over[0] if self.ex.over is not None else None  # the reaction's face, the signal the startle reads
        if s == "startle" or over in ("surprised", "worried"):
            return "startle"
        if over == "sad" or (face is not None and face[0] == "sad"):
            return "sad"
        if s == "act" and self.act in bh.THINK_ACTS:
            return "think"
        if s == "sit":
            return "lounge" if now - self.state_at >= bh.LOUNGE_AFTER else ""
        if s in ("walk", "drift"):
            return "glide"
        return ""

    def _tail_view(self, now: float, frame: str) -> tuple[int, ...] | None:
        """The layered tail's view over a stand-family or sit frame, or None (no layer: another frame, reduced motion, a
        walker, a figure the person has hold of)."""
        if self.gait != "float" or self.reduced or self.state not in ("stand", "sit") or frame.rstrip("0123456789") not in bh.TAIL_FRAMES:
            return None
        state, mood = self._tail_cue(now)
        self.tail_layer.choose(state, mood, now)
        return self.tail_layer.view(now)

    def _tail_cue(self, now: float) -> tuple[str, str]:
        """What the tail picks its pose by (atlascat-1108 C2, C3): the state, with a window's top as `perch` (balance) and a
        long sit as `lounge`; the mood, with a sad reaction as `sad` (tuck) and a glad one looked at as `playful` (loop8)."""
        state, mood = self.state, self._mood(now)
        if self.perch is not None and state == "stand":
            state = "perch"
        elif state == "sit" and now - self.state_at >= bh.LOUNGE_AFTER:
            state = "lounge"
        over = self.ex.over[0] if self.ex.over is not None else None
        if over == "sad" and mood != "startled":
            mood = "sad"
        elif mood in ("happy", "proud") and self._tail_fast(now):
            mood = "playful"
        return state, mood

    def _mood(self, now: float) -> str:
        """`Mind.mood`, kept for half a second (the needs move over minutes; an event shows at once): not worked out per tick."""
        at, ev, kept = self._mood_kept
        if 0.0 <= now - at < 0.5 and ev == self.mind.event_at:
            return kept
        kept = self.mind.mood(now, self.hour)
        self._mood_kept = (now, self.mind.event_at, kept)
        return kept

    def _tail_fast(self, now: float) -> bool:
        """The tail is being looked at: the pointer near, a touch just now. (A glad mood's wag at rest is drawn at the rest
        pace too: glad is the usual mood, and it would hold the whole hour at the active pace.)"""
        if now - self.last_click < TAIL_TOUCHED_FOR:
            return True
        p = self.pointer
        return p is not None and math.hypot(p[0] - self.x - self.size[0] / 2, p[1] - self.y - self.size[1] / 2) <= NOTICE_NEAR * self._scale()

    def _tail_ms(self, now: float) -> int:
        return TAIL_LAYER_MS if self._tail_fast(now) else FLOW_TICK_MS

    def _flow_view(self, now: float, frame: str = "", lower: str = "") -> tuple[int, ...] | None:
        """What the wisps and streams are doing at `now`; under reduced motion a slow drift only. While the
        person has hold of it or it is thrown or falling the last view is kept (review of 1683: a new flow is a
        new picture, and a warp a frame on the drag is the lag the owner complained of); a tumble frame takes
        none (its picture is the same with any)."""
        if frame.startswith("spin"):
            return None
        if self.state in FLOW_FROZEN:
            return self._flow_held
        if self._flow_held is not None and self._tail_ticks() and self._tail_fast(now) and 0.0 <= now - self._flow_at < 1.5 * TAIL_LAYER_MS / 1000.0:
            return self._flow_held  # while fast, every other tail tick reuses the body picture: only the tail is redrawn between two warps
        self._flow_at = now
        self._flow_held = self.flow.view(now, calm=self.reduced, frame=frame or "stand", lower=lower, side=-float(self.facing), breath=self._breath_phase(frame, now))
        return self._flow_held

    def _breath_phase(self, frame: str, now: float) -> float | None:
        """The body's breath phase for the lower body (`wisps.phase`); an act in place breathes at a sit's pace; none under reduced motion."""
        if self.reduced:
            return None
        life = self._rest_life()
        period = life[0] if life else REST_LIFE["sit"][0] * self.rest_breath if self.state == "act" else None
        return wisps.phase(self.state, frame, now, period, self.idle_frames, DRIFT_BREATH_S)

    def _tail_ticks(self) -> bool:
        """The layered tail sets the pace of the redraws now (a stand or a sit of a floater, not reduced)."""
        return self.gait == "float" and not self.reduced and self.tail_layer_on and self.state in ("stand", "sit")
