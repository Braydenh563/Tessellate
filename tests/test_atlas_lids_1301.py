"""INBOX 1301 D4: no pose rests Atlas's upper lid between open and shut.

The owner: "the half lidded eyes on atlas look creepy and like fnaf". The
lid's edge (atlas.js, `atlasEye`) sits at cy - 4.1 in the eye's middle and
travels 11px per unit of `--atl-lid`; since INBOX 1607 the masculine look
no longer lowers it (it did by 0.8px). The eye's white runs from cy - 4.25 to cy + 3.15 (`atlasAlmond`), so
the share of the eye an upper lid covers is (11 * lid + 0.15) / 7.4.
Every rule that sets it keeps that at 30% or less; only a blink (the
lid's own sweep, `atlasLids`) passes through the middle, and briefly.
"""

import math
import re
from pathlib import Path
from tests._css_paths import FORMER_08, sheets

ROOT = Path(__file__).resolve().parents[1]
CSS = sheets(*FORMER_08)
ATLAS = (ROOT / "frontend" / "js" / "atlas.js").read_text(encoding="utf-8")
EYE_H = 7.4


def upper_closed(lid, turn=0.0):
    # A turned lid (`--atl-lid-r`) dips at one side of the middle: measured
    # 3.5px either side of the centre, as scratchpad/ui-sweeps/atlaslids.js does.
    return max(0.0, 11 * lid + 0.15 + 3.5 * math.sin(math.radians(abs(turn)))) / EYE_H


def lower_closed(low):
    return max(0.0, 10 * low - 0.15) / EYE_H


def _rules():
    for m in re.finditer(r"(?:(?<=[{}])|\A)([^{}]*)\{([^{}]*--atl-(?:lid|low):[^{}]*)\}", CSS):
        yield m.group(1).strip(), m.group(2)


def test_no_rule_rests_the_upper_lid_half_down():
    seen = 0
    for sel, body in _rules():
        lid = re.search(r"--atl-lid:\s*([\d.]+)", body)
        if not lid:
            continue
        seen += 1
        turn = re.search(r"--atl-lid-r:\s*(-?[\d.]+)deg", body)
        closed = upper_closed(float(lid.group(1)), float(turn.group(1)) if turn else 0.0)
        assert closed <= 0.30, (sel, lid.group(1), closed)
    assert seen >= 15


def test_a_squint_from_below_leaves_the_eye_open():
    for sel, body in _rules():
        lid = re.search(r"--atl-lid:\s*([\d.]+)", body)
        low = re.search(r"--atl-low:\s*([\d.]+)", body)
        both = upper_closed(float(lid.group(1)) if lid else 0.1) + lower_closed(float(low.group(1)) if low else 0)
        assert both <= 0.6, (sel, both)


def test_the_soft_drooping_lid_is_gone():
    assert "softlid" not in CSS and "atl-lid-soft" not in ATLAS and "atl-lid-flat" not in ATLAS


def test_a_yawn_shuts_the_eyes_rather_than_half_lidding_them():
    rule = re.search(r"#nm-buddy\.nmb-act-yawn \.nm-atlas \{([^}]*)\}", CSS).group(1)
    assert "--atl-open: 0" in rule and "--atl-doze: 1" in rule and "--atl-lid" not in rule


def test_a_blinks_in_between_frames_pass_quickly():
    # Each partial frame (38% and 72% down) is shown alone for at most
    # 350ms on the way down and on the way up, the slow blink included.
    for name, ms in (("atl-blink", 320), ("atl-blink-slow", 1420)):
        stops = []
        for f in ("f1", "f2", "f3"):
            body = re.search(rf"@keyframes {name}-{f} \{{(.*?)\}} \}}", CSS).group(1)
            on = re.search(r"([\d.]+)%, ([\d.]+)% \{ opacity: 1", body)
            stops.append((float(on.group(1)), float(on.group(2))))
        (a1, b1), _, (a3, b3) = stops
        assert (a3 - a1) * ms / 100 <= 350 and (b1 - b3) * ms / 100 <= 350, (name, stops)


def test_the_calm_face_rests_its_lids_out_of_sight_1607():
    # The owner: "its eyes with its lids or smth look creepy". Open and
    # between blinks, no lid shows: the root, the masculine offset and the
    # moods that used to rest a lid at 0.04 to 0.1 are all 0 now.
    assert re.search(r"--atl-eye-s: 1;[^}]*?--atl-lid: 0;|--atl-lid: 0;\s*\n\s*--atl-lid-r: 0deg", CSS)
    assert 'data-atlas-look="masculine"] .atl-lid { translate: 0 0; }' in CSS
    for mood in ("confused", "sad", "shy"):
        bodies = re.findall(r'\.nm-atlas\[data-atlas-mood="%s"\] \{([^}]*)\}' % mood, CSS)
        assert any("--atl-lid: 0;" in b for b in bodies), mood
    assert upper_closed(0.0) <= 0.03


def test_no_mood_closes_one_eye_alone_1607():
    # Both eyes blink together (one lid layer holds both); a mood that
    # shuts only the right eye leaves the left one blinking alone.
    assert not re.search(r"\.atl-eye-[lr]\s*\{[^}]*--atl-(open|happy|shut|squeeze)", CSS)
