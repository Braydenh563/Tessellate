"""Atlas does the desk's acts (INBOX 1696 v, the owner: "I want the desktop
companion to be just as good as the in-app one and vice versa"; the catalogue's
Batch D, `docs/roadmap/agent-remaining/atlascat-1108.md`).

Ten acts the desk had and the app had not: push-ups, dumbbells, tea, a snack,
fishing (D1) and a journal, stargazing, a blanket nap, watering a plant and a
puzzle (D2). Each is its own pose (the `desk: true` rows of `NAME_MARK_BUDDY_ACTS`), not a generic one: the
eyes on the prop, the arms moving it over several beats, a lean, the tail and a
calm face with an occasional smile, the props drawn in the rig as small vector
parts in both themes. The keyframes are sampled by node at fixed times (no
clock), so a pose that only moved on paper fails here.
"""

from __future__ import annotations

import json
import re
import shutil
import subprocess
from pathlib import Path

import pytest
from tests._js_scope import unwrapped

ROOT = Path(__file__).resolve().parents[1]
JS = ROOT / "frontend" / "js"
AVATARS = unwrapped((JS / "avatars.js").read_text(encoding="utf-8"))
ATLAS = (JS / "atlas.js").read_text(encoding="utf-8")
LAZY = (ROOT / "frontend" / "css" / "atlas-lazy.css").read_text(encoding="utf-8")
CATALOGUE = json.loads((ROOT / "frontend" / "companion-catalogue.json").read_text(encoding="utf-8"))

needs_node = pytest.mark.skipif(not shutil.which("node"), reason="needs node")

#: act key -> (catalogue id, the prop classes the act shows, how long one beat cycle runs in seconds, its cycles)
ACTS = {
    "pushups": ("act.push_ups", ["nmp-pushmat"], 1.75),
    "weights": ("act.lift_weights", ["nmp-dumbbell-l", "nmp-dumbbell-r"], 3.6),
    "tea": ("act.sip_tea", ["nmp-cup"], 3.8),
    "snack": ("act.snack", ["nmp-snack"], 6.4),
    "fish": ("act.fish", ["nmp-rod"], 8.4),
    "journal": ("act.write_journal", ["nmp-diary", "nmp-pen"], 12),
    "stars": ("act.watch_stars", ["nmp-sky"], 36),
    "blanket": ("act.blanket_nap", ["nmp-blanket", "nmp-pillow", "nmp-napz"], 30),
    "plant": ("act.water_plant", ["nmp-plant", "nmp-can"], 10),
    "puzzle": ("act.puzzle", ["nmp-puzzle", "nmp-piece"], 7),
    "agree": ("act.nod", [], 1.2),
    "dance": ("act.little_dance", [], 1.8),
    "proud": ("act.pose_proud", [], 2.5),
    "lookdown": ("act.look_down", [], 2.5),
    "tiptoe": ("act.tiptoe", [], 2.6),
    "daydream": ("act.daydream", ["nmp-daydream"], 12),
    "pace": ("act.pace", [], 4),
    "game": ("act.invent_game", ["nmp-game"], 3),
    "tinker": ("act.tinker", ["nmp-gear", "nmp-spanner"], 4),
    "dust": ("act.dust_off", ["nmp-dust"], 1.25),
    #: INBOX 1710, 1711 (compalive-1109): four small things built on both sides, no prop.
    "sneeze": ("act.sneeze", [], 1.3),
    "hiccup": ("act.hiccup", [], 3),
    "hug": ("act.self_hug", [], 4.5),
    "tap": ("act.foot_tap", [], 3),
    #: INBOX 1710, 1711 (comp2-1109): a firefly chased, a star pile counted, a nap on a note card, a wave at the pointer.
    "firefly": ("act.star_catch", [], 4.5),
    "starpile": ("act.count_stars", [], 6),
    "cardnap": ("act.card_nap", [], 9),
    "wavepointer": ("act.wave_pointer", [], 2.4),
    #: E5 (OPEN.md Tier E; INBOX 1692 e and 1711): a bowl of dinner, a bubble wand, two needles and a strand of starlight.
    "dinner": ("act.dinner", ["nmp-bowl", "nmp-spoon"], 8),
    "bubbles": ("act.blow_bubbles", ["nmp-wand"], 5),
    "knit": ("act.knit_starlight", ["nmp-needles"], 6),
}


def _block() -> str:
    """The desk acts' rows: the `Object.assign(NAME_MARK_BUDDY_ACTS, {...})` that follows their comment."""
    start = AVATARS.index("Object.assign(NAME_MARK_BUDDY_ACTS, {\n  pushups")
    return AVATARS[start : AVATARS.index("\n});", start)]


def _desk_rows() -> dict[str, dict]:
    rows = {}
    for key, body in re.findall(r"^  ([a-z]+): \{ (ms: .*?) \},$", _block(), re.M):
        rows[key] = {k: v.strip() for k, v in (p.split(":", 1) for p in re.split(r",\s(?![^\[]*\])", body))}
    return rows


def test_every_desk_act_has_a_row_and_only_atlas_plays_it():
    rows = _desk_rows()
    assert set(rows) == set(ACTS), sorted(set(rows) ^ set(ACTS))
    for key, row in rows.items():
        assert row["atlas"] == "true" and row["desk"] == "true", key
        assert float(row["w"]) > 0 and int(row["cool"]) >= 60000 and int(row["ms"]) >= 1000, key  # 1 s: D3's gestures are 1 to 4 s long, no prop, where D1 and D2's doings are 5 s and up
        assert re.search(r'poses: \["[a-z]+"', AVATARS[AVATARS.index(f"  {key}: {{ ms:") :][:200]), key


def test_the_acts_are_in_the_settings_switch_and_the_tooltips():
    """What it does on its own (Settings) lists them, and a hover says what it is doing."""
    assert "NAME_MARK_BUDDY_ACTS[act].desk" in AVATARS
    for key in ACTS:
        assert f'["nmb-act-{key}", "' in AVATARS, key


@pytest.mark.parametrize("key", sorted(ACTS))
def test_the_props_are_drawn_and_shown_only_by_their_act(key):
    for cls in ACTS[key][1]:
        stem = re.sub(r"-[lr]$", "", cls[4:])
        assert stem in ATLAS, cls
        assert re.search(rf"#nm-buddy\.nmb-act-{key}\b[^{{}}]*\.{cls}\b", LAZY), f"{cls} is not shown by {key}"


def test_props_are_painted_in_the_theme_not_in_a_literal_colour():
    """Both themes: the rules for `atl-ds-*` take the rig's custom properties (`--atl-*`), never a hex or rgb."""
    rules = re.findall(r"^\.nm-atlas \.atl-ds-[^{]*\{[^}]*\}", LAZY, re.M)
    assert len(rules) >= 15
    for rule in rules:
        assert not re.search(r"#[0-9a-fA-F]{3,8}\b|rgba?\(", rule), rule
        if "fill" in rule or "stroke" in rule:
            assert "var(--atl-" in rule or "none" in rule or "opacity" in rule, rule


def _keyframes(name: str) -> str:
    m = re.search(rf"@keyframes {re.escape(name)} \{{(.*)", LAZY)
    assert m, f"no keyframes {name}"
    depth, out = 1, []
    for ch in m.group(1):
        depth += (ch == "{") - (ch == "}")
        if depth == 0:
            break
        out.append(ch)
    return "".join(out)


@pytest.mark.parametrize("key", sorted(ACTS))
def test_the_beats_move_the_arm_the_eyes_and_the_tail(key):
    """Every act names a loop for each, and each loop holds several different values (a pose of its own, not one held)."""
    for part in ("arm", "eye", "tail"):
        frames = _keyframes(f"atl-ds-{key}-{part}")
        values = set(re.findall(r"(?:rotate\(|translate: |rotate: )([^;})]+)", frames))
        assert len(values) >= 2, (key, part, values)
    assert re.search(rf"nmb-act-{key} \.atl-figure \.nmb-arm-[lr] \{{ animation: atl-ds-{key}-arm", LAZY)
    assert re.search(rf"nmb-act-{key} \.nm-atlas \.atl-pupil \{{ animation: atl-ds-{key}-eye", LAZY)
    assert re.search(rf"nmb-act-{key} \.nm-atlas \.atl-tail \{{ animation: atl-ds-{key}-tail", LAZY)


@pytest.mark.parametrize("key", sorted(ACTS))
def test_the_face_smiles_now_and_then_and_never_frowns(key):
    assert re.search(rf"nmb-act-{key} \.nm-atlas \.atl-m-grin \{{ animation: atl-ds-grin", LAZY), key
    static = re.search(rf"#nm-buddy\.nmb-act-{key} \.nm-atlas \{{([^}}]*)\}}", LAZY).group(1)
    assert "--atl-knit" not in static and "--atl-m-frown" not in static and "--atl-brow-y: 1" not in static


SAMPLER = r"""
const css = process.argv[1];
const act = process.argv[2];
const cycle = +process.argv[3];
const frames = (name) => {
  const at = css.indexOf("@keyframes " + name + " {");
  let depth = 0, i = css.indexOf("{", at), start = i + 1, out = [];
  for (; i < css.length; i += 1) { if (css[i] === "{") depth += 1; if (css[i] === "}") { depth -= 1; if (depth === 0) break; } }
  const body = css.slice(start, i);
  const re = /([0-9.%,\s]+)\{([^}]*)\}/g;
  let m;
  while ((m = re.exec(body))) {
    const num = /(?:rotate\(|translate:|rotate:)\s*(-?[0-9.]+)(?:deg|px)?\)?(?:\s+(-?[0-9.]+)px)?/.exec(m[2]);
    if (!num) continue;
    for (const stop of m[1].split(",")) out.push([parseFloat(stop) / 100, +num[1], num[2] === undefined ? 0 : +num[2]]);
  }
  return out.sort((a, b) => a[0] - b[0]);
};
// Linear between stops, as `ease` is monotone: enough to tell a held pose from a moving one.
const at = (f, t) => {
  if (t <= f[0][0]) return f[0].slice(1);
  for (let k = 1; k < f.length; k += 1) {
    if (t <= f[k][0]) { const u = (t - f[k - 1][0]) / (f[k][0] - f[k - 1][0] || 1); return [f[k - 1][1] + (f[k][1] - f[k - 1][1]) * u, f[k - 1][2] + (f[k][2] - f[k - 1][2]) * u]; }
  }
  return f[f.length - 1].slice(1);
};
const out = {};
// The fixed clock: 24 timestamps spread over one cycle (a long act's moves come in beats, so three fixed ones can all fall in a hold), no real time.
for (const part of ["arm", "eye", "tail"]) {
  const f = frames("atl-ds-" + act + "-" + part);
  out[part] = Array.from({ length: 24 }, (_, i) => at(f, i / 24).map((v) => +v.toFixed(2)));
}
console.log(JSON.stringify(out));
"""


@needs_node
@pytest.mark.parametrize("key", sorted(ACTS))
def test_over_a_cycle_the_arm_the_eyes_and_the_tail_have_moved(key):
    run = subprocess.run(["node", "-e", SAMPLER, LAZY, key, str(ACTS[key][2])], capture_output=True, text=True)
    assert run.returncode == 0, run.stderr[-1500:]
    got = json.loads(run.stdout)
    for part, samples in got.items():
        assert len({tuple(s) for s in samples}) >= (3 if part == "arm" else 2), (key, part, samples)
    # An arm that moves does so by more than a wobble.
    arm = [s[0] for s in got["arm"]]
    assert max(arm) - min(arm) >= 6, (key, arm)


def test_the_catalogue_rows_are_built_here_and_point_at_the_table():
    by_id = {e["id"]: e for e in CATALOGUE["entries"]}
    for key, (cid, _, _) in ACTS.items():
        app = by_id[cid]["app"]
        assert app["s"] == "built" and app["names"] == [f"acts:{key}"], cid
        assert app["at"] == f"frontend/js/avatars.js#  {key}: {{ ms:", cid


def test_the_pick_is_the_weighted_choice_and_never_repeats_back_to_back():
    """The acts take no path of their own: `nameMarkBuddyDecide` reads the table, weighs each by its catalogue row and never plays one of the last five."""
    decide = AVATARS[AVATARS.index("function nameMarkBuddyDecide") :][:6000]
    assert "NAME_MARK_BUDDY_ACTS" in decide and "nmb.cat" in decide
    assert re.search(r"recent|lastActs|nmb\.last", decide)


def test_miffed_and_smirk_are_atlas_faces_with_a_cue_a_look_and_a_trigger():
    """D4: the desk's two attitude faces. Each is a mood (words, cue, face rules, arms per look) and something reaches it."""
    css = (ROOT / "frontend" / "css" / "characters-lazy.css").read_text(encoding="utf-8")
    for mood in ("miffed", "smirk"):
        assert re.search(rf'^  {mood}: \{{ words: "[^"]+", cue: "rest" \}},$', ATLAS, re.M), mood
        assert f"  {mood}: (g) =>" in ATLAS and f'[data-atlas-mood="{mood}"] .atl-cue-{mood}' in LAZY, mood
        assert re.search(rf'\.nm-atlas\[data-atlas-mood="{mood}"\] \{{[^}}]*--atl-', css), mood
        for look in ("masculine", "feminine"):
            assert f'[data-atlas-look="{look}"][data-atlas-mood="{mood}"]' in css, (look, mood)
    miffed = re.search(r'\.nm-atlas\[data-atlas-mood="miffed"\] \{([^}]*)\}', css).group(1)
    assert float(re.search(r"--atl-knit:\s*(-?[\d.]+)", miffed).group(1)) > 0 and "--atl-m-frown: 1" in miffed
    smirk = re.search(r'\.nm-atlas\[data-atlas-mood="smirk"\] \{([^}]*)\}', css).group(1)
    assert "--atl-m-smug: 1" in smirk and "--atl-bl-y: -" in smirk
    # What reaches them: a pout, a grumble, a shake and a facepalm (miffed), a shrug (smirk).
    assert re.search(r'\{ unimpressed: "miffed", angry: "miffed", nervous: "worried", sly: "smirk" \}', AVATARS)
    assert 'shrug: "sly"' in AVATARS and "isAtlasSeed(buddy.dataset.seed" in AVATARS


# --- INBOX 1770: the nap's blanket drapes, the rings rest, a z rises -------------------------------------------


def test_the_nap_blanket_drapes_over_a_pillow_with_no_flat_box_stitches_or_gold_diamond():
    """The owner, seeing it asleep on the bar: "idk what Im looking at" (a flat rectangle, rows of dashes, a gold diamond)."""
    front = ATLAS[ATLAS.index('const blanket = atlasGroup(layer, "nmp nmp-blanket")'):]
    front = front[: front.index("const napz = ")]
    for cls in ("atl-ds-blanket", "atl-ds-cuff", "atl-ds-fold", "atl-ds-crease"):
        assert f'class: "{cls}"' in front, cls
    assert "atl-ds-stitch" not in front and "atlasSpark" not in front  # no stitches, no gold diamond
    assert "atl-ds-stitch" not in LAZY
    # The pillow is behind the head, in the back layer with the mat, not over the body.
    assert "atlasHandProps.pillow(back.fill);" in ATLAS and 'atlasGroup(layer, "nmp nmp-pillow")' in ATLAS
    for cls in ("atl-ds-cuff", "atl-ds-crease", "atl-ds-pillow", "atl-ds-pillow-seam"):
        assert re.search(rf"^\.nm-atlas \.{cls} \{{[^}}]*var\(--atl-", LAZY, re.M), cls


def test_asleep_the_rings_dim_the_nebula_draws_in_and_the_pose_says_so():
    nap = re.search(r"#nm-buddy\.nmb-act-blanket \.nm-atlas \{([^}]*)\}", LAZY).group(1)
    assert float(re.search(r"--atl-halo-o:\s*([\d.]+)", nap).group(1)) <= 0.25  # the rings' own opacity token
    orbits = re.search(r"#nm-buddy\.nmb-act-blanket \.atl-orbits \{([^}]*)\}", LAZY).group(1)
    assert 0 < float(re.search(r"opacity:\s*([\d.]+)", orbits).group(1)) <= 0.35  # the planets with them: a halo, not gone
    neb = re.search(r"#nm-buddy\.nmb-act-blanket :is\(\.atl-lw-neb, \.atl-lw-neb-front\) \{([^}]*)\}", LAZY).group(1)
    assert float(re.search(r"scale:\s*([\d.]+)", neb).group(1)) < 0.7
    # The tail is the lower body's calm "lie" one (a curl), not the idle sway, flick and loop.
    motion = (JS / "atlas-motion.js").read_text(encoding="utf-8")
    assert 'has("nmb-act-nap") || has("nmb-act-lie") || has("nmb-act-blanket")) return "lie"' in motion


def test_the_slow_down_keeps_the_planets_where_they_are_and_the_waking_rings_ease_back():
    """A longer `animation-duration` on a running loop jumped the planets up to 50 degrees (measured), so the nap changes the
    playback rate instead, and the rings' opacity is a transition both ways."""
    css08 = (ROOT / "frontend" / "css" / "characters-lazy.css").read_text(encoding="utf-8")
    assert re.search(r"#nm-buddy \.atl-figure-box > \.atl-orbits \{[^}]*transition: [^;}]*opacity", css08)
    life = unwrapped((JS / "atlas-life.js").read_text(encoding="utf-8"))
    assert 'classList.contains("nmb-act-blanket") ? 1 / 3 : 1' in life
    assert "updatePlaybackRate(pace)" in life and '.closest?.(".atl-orbits")' in life


def test_the_z_rises_only_under_the_motion_gate_and_rests_drawn_under_reduced_motion():
    assert re.search(r"#nm-buddy\.nmb-act-blanket \.atl-figure :is\([^)]*\.nmp-napz\)", LAZY)
    gate_at = LAZY.rindex(':root:not([data-avatar-motion="off"])', 0, LAZY.index("/* A journal: a stroke"))
    assert "nmb-act-blanket .atl-nap-z { animation: atl-ds-blanket-z" in LAZY[gate_at : LAZY.index("/* A journal. */")]
    # Outside the gate (reduced motion, avatar animation off) the two z's are held drawn, one fainter.
    outside = LAZY[:gate_at]
    assert "nmb-act-blanket .atl-nap-z-0 { opacity: 0.9; }" in outside and "atl-ds-blanket-z" not in outside
    frames = _keyframes("atl-ds-blanket-z")
    assert "opacity: 0" in frames and "-8px" in frames  # it drifts up and fades out
