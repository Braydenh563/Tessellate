"""INBOX 1589, the owner, on Atlas's acts: the map "is like behind half
atlas's body and it doesnt even look at the map", the beanbag "still looks
like standing", the star hand "still has starts permanently coming from it",
a cheer "spawns a 3rd arm", the chair "doesnt look like sitting", and the arms
go "in like opposite directions but like fully extended or ... inverted in
front of it like it is trying to cross its arms".

The class, not the case: every act's arm count, every prop's paint order and
anchor, and every resting arm's turn, read from the code that draws them. The
live figures were measured in the large view in both looks and both themes
(a Playwright sweep of every act reading each arm's hand in the rig's units,
each prop's layer and its distance to the hands or the hips): two arms in
every act, the held props in front with the hands on them, the seats behind
with the hips on them.
"""

from __future__ import annotations

import math
import re
from pathlib import Path
from tests._js_scope import unwrapped
from tests._css_paths import FORMER_08, sheets

ROOT = Path(__file__).resolve().parent.parent
CSS_DIR = ROOT / "frontend" / "css"
JS_DIR = ROOT / "frontend" / "js"
CSS08 = sheets(*FORMER_08)
LAZY = (CSS_DIR / "atlas-lazy.css").read_text(encoding="utf-8")
ATLAS = (JS_DIR / "atlas.js").read_text(encoding="utf-8")
MICRO = (JS_DIR / "atlas-micro.js").read_text(encoding="utf-8")
AVATARS = unwrapped((JS_DIR / "avatars.js").read_text(encoding="utf-8"))

#: The acts that leave the arms as the mood has them: the faceless ones
#: (every other act sets `nmb-arms`, avatars.js).
QUIET = set(re.findall(r'"(\w+)"', re.search(r"const NMB_FACELESS_ACTS = \[([^\]]*)\];", AVATARS).group(1)))
#: The shoulders (atlas.js `shoulders`, `armPivots`) and the arm's length to the hand.
#: Intent moved (INBOX 1607 b): his shoulders came in by 1 each side with his arms, so his pivots did too.
PIVOTS = {"masculine": {"l": (25.6, 41.0), "r": (36.4, 41.0)}, "feminine": {"l": (26.4, 40.6), "r": (35.6, 40.6)}}
ARM = {"masculine": 20.4, "feminine": 20.8}
MIDDLE = 31.0


def _acts() -> list[str]:
    start = AVATARS.index("const NAME_MARK_BUDDY_ACTS = {")
    body = AVATARS[start : AVATARS.index("\n};", start)]
    return re.findall(r"^  (\w+): \{", body, re.M)


def _rules(css: str) -> list[tuple[int, str, str]]:
    """Every flat rule: (offset, selector, declarations), comments removed."""
    flat = re.sub(r"/\*.*?\*/", lambda m: " " * len(m.group(0)), css, flags=re.S)
    return [(m.start(), m.group(1).strip(), m.group(2)) for m in re.finditer(r"(?:(?<=[{}])|\A)([^{}]+)\{([^{}]*)\}", flat)]


RULES = _rules(CSS08)
#: Atlas's acts' gaze, seats and fold are in the lazy sheet, after 08 (boot CSS budget).
BOTH = CSS08 + LAZY


def _split(selector: str) -> list[str]:
    """A selector list split at its top-level commas (not inside `:is()`)."""
    parts, depth, start = [], 0, 0
    for i, ch in enumerate(selector):
        depth += ch == "("
        depth -= ch == ")"
        if ch == "," and depth == 0:
            parts.append(selector[start:i].strip())
            start = i + 1
    return [*parts, selector[start:].strip()]


def _names(selector: str, act: str) -> bool:
    return re.search(rf"\.nmb-act-{act}\b", selector) is not None


def _set(act: str, part: str, prop: str, value: str) -> bool:
    """Some rule for this act sets `prop: value` on this part."""
    for _, sel, decls in RULES:
        for one in _split(sel):
            if _names(one, act) and re.search(rf"\.{part}(?![\w-])", one) and re.search(rf"(?<![\w-]){prop}:\s*{re.escape(value)}\s*(;|$)", decls.strip()):
                return True
    return False


def _arms_shown(act: str) -> int:
    holds = _set(act, "nmb-hold", "opacity", "1")
    rigged_off = _set(act, "nmb-arm", "opacity", "0")
    chin = _set(act, "atl-chin-hand", "opacity", "1")
    right_off = rigged_off or _set(act, "nmb-arm-r", "opacity", "0")
    return (2 if holds else 0) + (0 if rigged_off else 1) + (0 if right_off else 1) + (1 if chin else 0)


def test_no_act_draws_more_than_two_arms() -> None:
    """A hold's raised arms replace the rigged ones, the chin hand replaces
    the right arm, and the mood's chin hand gives way to every act that moves
    the arms (it outranked the holds' hide and was the cheer's third arm)."""
    acts = _acts()
    assert len(acts) > 40
    counts = {act: _arms_shown(act) for act in acts}
    assert all(n == 2 for n in counts.values()), {a: n for a, n in counts.items() if n != 2}
    for act in ("cheer", "stretch", "yawn", "startle", "wake"):
        assert _set(act, "nmb-hold", "opacity", "1") and _set(act, "nmb-arm", "opacity", "0"), act
    chin = [sel for _, sel, decls in RULES if ".atl-chin-hand" in sel and "var(--atl-chin)" in decls]
    arm_r = [sel for _, sel, decls in RULES if ".nmb-arm-r" in sel and "calc(1 - var(--atl-chin))" in decls]
    assert chin and arm_r
    for sel in chin + arm_r:
        assert ".nmb-arms)" in sel, "the mood's hand gives way to the acts"
        for flag in ('[data-pose="hang"]', '[data-pose="sit"]', '[data-travel="climb"]', ".nm-buddy-dragging"):
            assert flag in sel, flag
    # The class is on with every act but the faceless ones, and off when the
    # last such act's class is (whichever of two blends lands first).
    act = AVATARS[AVATARS.index("function nameMarkBuddyAct(") :][:9000]
    assert 'buddy.classList.add(`nmb-act-${act}`, ...(NMB_FACELESS_ACTS.includes(act) ? [] : ["nmb-arms"]))' in act
    assert 'if (![...buddy.classList].some((c) => c.startsWith("nmb-act-") && !NMB_FACELESS_ACTS.includes(c.slice(8)))) buddy.classList.remove("nmb-arms");' in act
    assert len(QUIET) >= 8
    # The quiet acts really leave the arms be: none of them names an arm.
    for act in QUIET:
        for _, sel, _decls in RULES:
            if _names(re.sub(r":not\((?:[^()]|\([^()]*\))*\)", "", sel), act):
                assert not re.search(r"\.(nmb-arm|nmb-hold|atl-chin-hand)\b", sel), (act, sel)


def test_every_act_s_arm_turn_comes_after_the_poses_and_never_crosses() -> None:
    """The pose arms (sit, float) are as specific as an act's and came later,
    so in the large view (which floats) an act kept the pose's arms. Every
    act's arm turn is after them now, and none turns a hand past the middle."""
    # Atlas's pose arms (`.atl-figure`, as specific as an act's); the companion's
    # own, one class less, went to characters-lazy.css with UI plan 13b.
    pose_at = max(at for at, sel, decls in RULES if re.search(r'\[data-pose="(sit|float)"\]', sel) and ".atl-figure" in sel and re.search(r"\.nmb-arm-[lr]\b", sel) and "transform:" in decls)
    turns = []
    for at, sel, decls in RULES:
        for one in _split(sel):
            if "nmb-act-" in one and ".atl-figure" in one and re.search(r"\.nmb-arm-[lr]\b", one):
                turn = re.search(r"transform:\s*rotate\((-?[\d.]+)deg\)", decls)
                if turn:
                    turns.append((at, one, float(turn.group(1))))
    assert len(turns) >= 20
    for at, sel, deg in turns:
        if ".nm-figure" in sel:
            # The companion's own turn, shared: Atlas's rule for the act and side is later, or the arm is hidden.
            act, side = re.search(r"nmb-act-(\w+)", sel).group(1), re.search(r"\.nmb-arm-([lr])\b", sel).group(1)
            later = any(a > pose_at and _names(o, act) and f".nmb-arm-{side}" in o and ".nm-figure" not in o for a, sl, _ in RULES for o in _split(sl))
            assert later or _set(act, f"nmb-arm-{side}", "opacity", "0"), sel
            continue
        assert at > pose_at, sel
        side = re.search(r"\.nmb-arm-([lr])\b", sel).group(1)
        outward = deg if side == "l" else -deg
        assert outward >= -10, (sel, deg)
        assert not 60 <= outward <= 115 or "wave" in sel or "bell" in sel or "lantern" in sel, (sel, deg)
    # No feminine pose rule outranks an act: the look is `:where`, no weight.
    for _, sel, _decls in RULES:
        if re.search(r'\[data-pose="(sit|float)"\]', sel) and re.search(r"\.nmb-arm-[lr]\b", sel):
            assert "[data-atlas-look" not in sel.replace(":where([data-atlas-look", ""), sel


def _moods() -> dict[tuple[str, str], dict[str, float]]:
    out: dict[tuple[str, str], dict[str, float]] = {}
    for css in (CSS08, LAZY):
        for look, mood, body in re.findall(r'\.nm-atlas\[data-atlas-look="(\w+)"\]\[data-atlas-mood="(\w+)"\] \{([^}]*)\}', css):
            vals = out.setdefault((look, mood), {})
            for key, num in re.findall(r"--atl-(ar\d|al\d|chin\d):\s*(-?[\d.]+)", body):
                vals[key] = float(num)
    return out


def test_resting_arms_hang_from_the_shoulders_never_crossed_or_a_t() -> None:
    """Each mood's three variants, both looks: an arm turned in stops with its
    hand at the body's middle, not past it, and no variant holds both arms
    straight out."""
    moods = _moods()
    assert len(moods) >= 28
    for (look, mood), vals in moods.items():
        for v in "012":
            r = vals.get(f"ar{v}", 0.0)
            l_ = vals.get(f"al{v}", 0.0)
            chin = vals.get(f"chin{v}", 0.0)
            out_l, out_r = l_, -r
            for side, out in (("l", out_l), ("r", out_r if chin < 1 else 0.0)):
                if out >= 0:
                    continue
                # Measured standing (where the moods' arms show), each hand lands
                # within 0.3 of the straight arm's: 18 in put his at 30.7 and 31.0.
                total = -out
                sx, _ = PIVOTS[look][side]
                hand = sx + (1 if side == "l" else -1) * ARM[look] * math.sin(math.radians(total))
                past = hand - MIDDLE if side == "l" else MIDDLE - hand
                assert past <= 0.6, (look, mood, v, side, out, round(hand, 1))
            wide = [o for o in (out_l, out_r if chin < 1 else 0.0) if 60 <= o <= 115]
            assert len(wide) < 2, (look, mood, v, "a T")


def test_the_held_props_are_in_front_at_the_hands_and_the_seats_behind_at_the_hips() -> None:
    draw = ATLAS
    assert "atlasMapProp(frontAt.fill);" in draw and "atlasMapProp(back.fill)" not in draw, "the map is held in front"
    assert "atlasBookProp(frontAt.fill);" in draw
    assert "atlasCoilProp.seats(back.fill);" in draw, "the seats are behind the body"
    # The map's lower corners are at the hands (each arm 13 degrees out, the CSS).
    path = re.search(r'class: "atl-prop-map", d: "([^"]+)"', ATLAS).group(1)
    nums = [float(n) for n in re.findall(r"-?[\d.]+", path)]
    xs, ys = nums[0::2], nums[1::2]
    box = (min(xs), min(ys), max(xs), max(ys))
    for look in ("masculine", "feminine"):
        for side, sign in (("l", -1), ("r", 1)):
            sx, sy = PIVOTS[look][side]
            hx = sx + sign * ARM[look] * math.sin(math.radians(13))
            hy = sy + ARM[look] * math.cos(math.radians(13))
            dx = max(box[0] - hx, 0, hx - box[2])
            dy = max(box[1] - hy, 0, hy - box[3])
            assert math.hypot(dx, dy) < 2.5, (look, side, round(hx, 1), round(hy, 1), box)
    assert _set("map", "nmb-arm-l", "transform", "rotate(13deg)") and _set("map", "nmb-arm-r", "transform", "rotate(-13deg)")
    # The seats: the chair's slab under the folded hips, the bag's dip there.
    seat = re.search(r'class: "atl-prop-seat atl-prop-seat-top", x: ([\d.]+), y: ([\d.]+), width: ([\d.]+), height: ([\d.]+)', ATLAS)
    sx, sy, sw, sh = (float(g) for g in seat.groups())
    assert sx < MIDDLE - 12 and sx + sw > MIDDLE + 12, "wider than the hips"
    lower_origin = float(re.search(r"\.atl-lw-lower \{ transform-origin: 31px ([\d.]+)px; \}", CSS08).group(1))
    assert lower_origin <= sy <= lower_origin + 8, "the slab is at the hips the lower body folds about"
    assert re.search(r"#nm-buddy:is\(\.nmb-act-chair, \.nmb-act-beanbag\) :is\(\.atl-lw-lower, \.atl-lw-tail\) \{ scale: [\d.]+ 0\.5; \}", BOTH), "sat, the legs and tail fold"
    lazy = _rules(LAZY)
    for act in ("chair", "beanbag"):
        assert any(_names(sel, act) and f".nmp-{act}" in sel and "opacity: 1" in d for _, sel, d in lazy), act
    # Atlas's own seats stand in for the companion's generic scene.
    assert "#nm-buddy[data-atlas-figure] .nms { opacity: 0; }" in CSS08


def test_the_eyes_and_the_head_go_to_the_prop() -> None:
    assert re.search(r"#nm-buddy:is\(\.nmb-act-map, \.nmb-act-read\) \.nm-atlas \.atl-pupil \{ --atl-px: 0px; --atl-py: 1\.8px; \}", BOTH), "down to the map"
    assert re.search(r"#nm-buddy\.nmb-act-juggle \.nm-atlas \.atl-pupil \{ --atl-px: 0px; --atl-py: -1\.6px; \}", BOTH), "up to the stars"
    rule = re.search(r"#nm-buddy:is\(([^)]*)\) \.nm-atlas \.atl-iris \{ translate: none; \}", BOTH)
    assert rule and {"map", "read", "juggle", "bell", "lantern"} <= set(re.findall(r"\.nmb-act-(\w+)", rule.group(1))), "the pointer's look gives way"


def test_the_stars_are_the_star_hand_s_own_state() -> None:
    """The feminine look wore stars on her left hand (the rig's arm `r`) at all
    times; the cast came from the other hand. Now no stars are drawn at rest,
    the cast is from that hand, never during an act that moves the arms, and an
    act that starts stops one under way."""
    assert "seeds:" not in ATLAS and "atl-seed" not in ATLAS and "atl-seed" not in BOTH
    cast = MICRO[MICRO.index("function atlasMicroCast") : MICRO.index("atlasMicroCast.stop = function")]
    assert 'a.side === "r"' in cast
    assert "if (nmb.act && !NMB_FACELESS_ACTS.includes(nmb.act)" in cast
    assert "box.atlasCastAnims.push(anim)" in cast
    stop = MICRO[MICRO.index("atlasMicroCast.stop = function") :][:300]
    assert "anim.cancel()" in stop and "getAnimations" not in stop
    act = AVATARS[AVATARS.index("function nameMarkBuddyAct(") :][:6000]
    assert "else if (!quiet) window.atlasMicroCast?.stop();" in act
