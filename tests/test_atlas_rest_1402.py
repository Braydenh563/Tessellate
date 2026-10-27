"""INBOX 1402: Atlas reads friendly at rest, not "a bored or grumpy gangster".

The owner, 2026-10-27: "atlas looks like a bored or grumpy gangster with its
facial expressions and arm positioning half the time". Measured over the
cycle (scratchpad/ui-sweeps/atlasrest1402.js): both brows were drawn sloping
down to the nose in every mood, "determined" (a long chat turn, a focus
while typing) scowled with a set mouth, thinking's mouth sagged, the doze
dropped the brows, a masculine stance folded the arms across the chest for
16s, and her elbow folded across her body once her shoulder's target had
wound a turn round. These pin the rule for every resting and idle state:
no mouth that curves down, no brow lowered at the nose or dropped, and arms
a little out, never hanging slack or folded; a sulk is brief.
"""

from __future__ import annotations

import json
import re
import shutil
import subprocess
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
CSS = (ROOT / "frontend" / "css" / "08-consistency.css").read_text(encoding="utf-8")
LAZY = (ROOT / "frontend" / "css" / "atlas-lazy.css").read_text(encoding="utf-8")
ATLAS = (ROOT / "frontend" / "js" / "atlas.js").read_text(encoding="utf-8")
MOTION = (ROOT / "frontend" / "js" / "atlas-motion.js").read_text(encoding="utf-8")
MICRO = (ROOT / "frontend" / "js" / "atlas-micro.js").read_text(encoding="utf-8")
AV = (ROOT / "frontend" / "js" / "avatars.js").read_text(encoding="utf-8")
needs_node = pytest.mark.skipif(not shutil.which("node"), reason="needs node")

#: Moods Atlas rests in (`atlasRestingMood`) or passes through with nothing
#: having happened: the drift (`ATLAS_DRIFT_POOL`), the micro-expressions
#: (`ATLAS_MICRO_MOOD`), a poke, and a chat turn (thinking, then determined).
#: Sad, worried, confused and surprised are for an error, a miss or a fall.
EVENT_ONLY = {"sad", "worried", "confused", "surprised"}


def _mouths() -> dict[str, float]:
    """Each stroked mouth's curve: its handle's drop below its corners'
    middle (positive smiles). Open mouths (`fill`) are smiles; an `o` is 0."""
    body = re.search(r"const ATLAS_MOUTHS = \{(.*?)\n\};", ATLAS, re.S).group(1)
    out = {}
    for name, rest in re.findall(r"^\s*(\w+): \{ (.*)\},?$", body, re.M):
        if "ellipse" in rest:
            out[name] = 0.0
        elif "fill: true" in rest:
            out[name] = 2.5
        else:
            # M x y, then Q cx cy x y segments: the mean of their sags.
            nums = [float(n) for n in re.findall(r"-?\d+(?:\.\d+)?", re.search(r'd: "([^"]+)"', rest).group(1))]
            sags, y = [], nums[1]
            for i in range(2, len(nums), 4):
                cy, y1 = nums[i + 1], nums[i + 3]
                sags.append(cy - (y + y1) / 2)
                y = y1
            out[name] = sum(sags) / len(sags)
    return out


def _rule(selector: str, css: str = CSS) -> str:
    m = re.search(re.escape(selector) + r"\s*\{([^}]*)\}", css)
    assert m, selector
    return m.group(1)


def _num(body: str, prop: str, default: float = 0.0) -> float:
    m = re.search(rf"--atl-{prop}:\s*(-?[\d.]+)", body)
    return float(m.group(1)) if m else default


def _mouth_of(body: str) -> str:
    on = re.findall(r"--atl-m-(\w+):\s*1\b", body)
    return on[-1] if on else "smile"


def _quiet_moods() -> set[str]:
    moods = set(re.findall(r'^\s*(\w+): \{ words:', re.search(r"const ATLAS_MOODS = \{(.*?)\n\};", ATLAS, re.S).group(1), re.M))
    assert len(moods) == 15
    return moods - EVENT_ONLY


def test_the_idle_moods_come_only_from_the_quiet_set():
    drift = re.search(r"const ATLAS_DRIFT_POOL = \{(.*?)\};", ATLAS, re.S).group(1)
    micro = re.search(r"const ATLAS_MICRO_MOOD = \{(.*?)\};", MICRO).group(1)
    pokes = re.search(r"const ATLAS_POKES = \[(.*?)\];", ATLAS).group(1)
    named = set(re.findall(r'"(\w+)"', drift + micro + pokes))
    # The micro "surprised" is a startle with brows up and an O: not a frown.
    assert named - {"surprised"} <= _quiet_moods(), named - _quiet_moods()


def test_no_quiet_mood_curves_the_mouth_down():
    mouths = _mouths()
    assert mouths["smile"] > 2 and mouths["frown"] < -2
    for mood in sorted(_quiet_moods() - {"calm"}):
        body = _rule(f'.nm-atlas[data-atlas-mood="{mood}"]')
        assert mouths[_mouth_of(body)] > 0.3, (mood, _mouth_of(body), mouths[_mouth_of(body)])
    # And the companion's own quiet states: asleep, waking, yawning.
    for sel in ("#nm-buddy:is(.nmb-sleep, .nmb-act-lie) .nm-atlas",):
        assert mouths[_mouth_of(_rule(sel))] > 0.3, sel


def _brow_slant(kind: str) -> float:
    """The drawn brow's inner end below its outer end, in drawing units."""
    m = re.search(
        r'spec\.brow === "straight"\s*\?\s*`M\$\{x - [\d.]+ \* side\} \$\{y ([+-] [\d.]+)\}Q[^`]*\$\{x \+ [\d.]+ \* side\} \$\{y ([+-] [\d.]+)\}`'
        r'\s*:\s*`M\$\{x - [\d.]+ \* side\} \$\{y ([+-] [\d.]+)\}Q[^`]*\$\{x \+ [\d.]+ \* side\} \$\{y ([+-] [\d.]+)\}`',
        ATLAS,
    )
    assert m, "brow paths"
    v = [float(g.replace(" ", "")) for g in m.groups()]
    return v[1] - v[0] if kind == "straight" else v[3] - v[2]


def test_the_brows_are_drawn_level_or_lifted_at_the_nose():
    # The path starts at the outer end (x - k * side) and ends at the inner.
    for kind in ("straight", "arch"):
        assert _brow_slant(kind) <= 0, kind


def test_no_quiet_mood_lowers_the_brows():
    for mood in sorted(_quiet_moods() - {"calm"}):
        body = _rule(f'.nm-atlas[data-atlas-mood="{mood}"]')
        knit, y = _num(body, "knit"), _num(body, "brow-y")
        # The left brow turns by knit + bl-r, the right by -knit + br-r;
        # either inner end down past 4 degrees is a scowl.
        assert knit + _num(body, "bl-r") <= 4 and knit - _num(body, "br-r") <= 4, (mood, body)
        assert y + _num(body, "bl-y") <= 0.25 and y + _num(body, "br-y") <= 0.25, (mood, y)
    for sel in ("#nm-buddy.nmb-groggy .nm-atlas", "#nm-buddy.nmb-act-yawn .nm-atlas"):
        body = _rule(sel)
        assert _num(body, "brow-y") <= 0.25 and _num(body, "knit") <= 4, sel


def _raise(side: str, deg: float) -> float:
    # A right arm's negative turn and a left arm's positive one swing it out.
    return -deg if side == "r" else deg


def _relaxed(look: str, r: float, left: float) -> bool:
    out = all(6 <= a <= 60 for a in (r, left))
    # Hers may bring both hands together low in front (the owner's clasp).
    clasp = look == "feminine" and all(-48 <= a <= -15 for a in (r, left))
    return out or clasp


def test_calm_arms_rest_a_little_out_in_every_variant():
    for look in ("masculine", "feminine"):
        body = _rule(f'.nm-atlas[data-atlas-look="{look}"][data-atlas-mood="calm"]', LAZY)
        for v in "012":
            r, left = _raise("r", _num(body, f"ar{v}")), _raise("l", _num(body, f"al{v}"))
            assert _relaxed(look, r, left), (look, v, r, left)


#: Both hands meeting in front with a smile: at the heart (love), held
#: together (shy), on the belly (laughing). Any other quiet mood with both
#: arms turned in 50 degrees or more has folded them.
HANDS_MEET = {"love", "shy", "laughing"}


def test_no_quiet_mood_folds_or_hangs_both_arms():
    both = CSS + LAZY
    found = re.findall(r'\.nm-atlas\[data-atlas-look="(\w+)"\]\[data-atlas-mood="(\w+)"\]\s*\{([^}]*)\}', both)
    assert len(found) >= 28
    for look, mood, body in found:
        if mood not in _quiet_moods():
            continue
        for v in "012":
            r, left = _raise("r", _num(body, f"ar{v}", 99)), _raise("l", _num(body, f"al{v}", 99))
            if 99 in (abs(r), abs(left)):
                continue
            assert not (abs(r) < 6 and abs(left) < 6), (look, mood, v, "slack")
            assert mood in HANDS_MEET or not (r <= -50 and left <= -50), (look, mood, v, "folded")


def test_the_resting_stances_and_poses_keep_the_arms_relaxed():
    stances = re.search(r"const NMB_STANCES = \{(.*?)\};", AV, re.S).group(1)
    assert "fold:" not in stances and "hips:" in stances
    for act, look in (("hips", "masculine"), ("clasp", "feminine")):
        r = float(re.search(rf"#nm-buddy\.nmb-act-{act} \.atl-figure \.nmb-arm-r \{{ transform: rotate\((-?[\d.]+)deg\)", CSS).group(1))
        left = float(re.search(rf"#nm-buddy\.nmb-act-{act} \.atl-figure \.nmb-arm-l \{{ transform: rotate\((-?[\d.]+)deg\)", CSS).group(1))
        assert _relaxed(look, _raise("r", r), _raise("l", left)), act
    for pose in ("sit", "float"):
        r = float(re.search(rf'#nm-buddy\[data-pose="{pose}"\] \.nmb-arm-r \{{ transform: rotate\((-?[\d.]+)deg\)', CSS).group(1))
        left = float(re.search(rf'#nm-buddy\[data-pose="{pose}"\] \.nmb-arm-l \{{ transform: rotate\((-?[\d.]+)deg\)', CSS).group(1))
        assert _relaxed("masculine", _raise("r", r), _raise("l", left)), pose


def test_a_sulk_is_brief():
    grumpy = int(re.search(r"const NMB_GRUMPY_MS = (\d+);", AV).group(1))
    pout = int(re.search(r"const NMB_POUT_MS = (\d+);", AV).group(1))
    assert grumpy <= 10000 and pout <= 4000
    assert "now + 30000" not in AV and 'nameMarkBuddyExpress("unimpressed", 30000)' not in AV


def _fn(src: str, name: str) -> str:
    start = src.index(f"function {name}(")
    return src[start : src.index("\n}\n", start) + 2]


@needs_node
def test_the_elbow_reads_the_arm_as_drawn_not_its_winding():
    up = re.search(r"^const ATLAS_EL_UP = .*;$", MOTION, re.M).group(0)
    script = up + "\n" + _fn(MOTION, "atlasRigGesture") + """
const arm = { side: "l" };
const at = (r) => atlasRigGesture(arm, r, null)[0];
console.log(JSON.stringify([[at(0), at(-360), at(360)], [at(-40), at(-400), at(320)], [at(16), at(-344), at(736)]]));
"""
    got = json.loads(subprocess.run(["node", "-e", script], capture_output=True, text=True, check=True).stdout)
    for same in got:
        assert max(same) - min(same) < 1e-6, got
    # Hanging, a whole turn round: the small resting bend, not a fold.
    assert abs(got[0][1]) < 6


#: How sour a generated face reads (0: friendly). Its arms go with it
#: (`data-feel`): cool and sly fold them in, angry and unimpressed hang them.
SOUR = {"evil": 3, "angry": 3, "unimpressed": 2, "serious": 1, "sly": 1, "cool": 1}


def test_a_generated_face_never_drifts_sourer_than_it_was():
    body = re.search(r"const NMB_EXPR_NEAR = \{(.*?)\n\};", AV, re.S).group(1)
    near = {k.strip('"'): re.findall(r'"(\w+)"', v) for k, v in re.findall(r'(\w+|""): \[([^\]]*)\]', body)}
    assert near[""] and near["calm"] and near["sly"]
    for base, faces in near.items():
        for face in faces:
            assert SOUR.get(face, 0) <= SOUR.get(base, 0), (base, face)
