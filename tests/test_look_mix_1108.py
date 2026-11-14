"""Surprise mix: a seeded pick of palette, accent and density (BACKLOG, More themes).

Runs the shipped picker under node (the helpers are test_look_share_1108's);
the button, its Undo and its help are read from the source.
"""

from __future__ import annotations

from tests._help_text import help_more_text
from tests.test_look_share_1108 import CONTROLS, INDEX, ROOT, SETTINGS, _run


def test_a_seeded_pick_is_repeatable_and_inside_the_sets():
    out = _run(
        """
const current = { palette: "ocean", accent: "teal", density: "compact" };
const picks = [];
for (let seed = 1; seed <= 300; seed += 1) picks.push(settingsLook.lookFile.pick(seed, current));
const again = settingsLook.lookFile.pick(7, current);
console.log(JSON.stringify({
  same: JSON.stringify(again) === JSON.stringify(picks[6]),
  palettes: [...new Set(picks.map((p) => p.palette))].length,
  accents: [...new Set(picks.map((p) => p.accent))].length,
  densities: [...new Set(picks.map((p) => p.density))].sort(),
  inSets: picks.every((p) => PALETTES.some((x) => x.id === p.palette) && ACCENTS.some((x) => x.name === p.accent)),
  allDiffer: picks.every((p) => p.palette !== "ocean" && p.accent !== "teal" && p.density !== "compact"),
}))
"""
    )
    assert out["same"] and out["inSets"] and out["allDiffer"]
    assert out["palettes"] >= 8 and out["accents"] >= 15
    assert out["densities"] == ["comfortable", "spacious"]


def test_the_button_is_wired_applies_through_a_saved_look_and_can_be_undone():
    assert 'id="look-surprise"' in INDEX
    assert "surpriseNow" in CONTROLS[CONTROLS.index('$("look-surprise")') :][:200]
    body = SETTINGS[SETTINGS.index("function surpriseNow") :][:1200]
    assert "applySavedTheme(" in body and "changeLookWithUndo(" in body
    assert "density" in body
    more = help_more_text()
    guide = more[more.index('"id": "themes"') :][:3500]
    assert "Mix palette, accent and density" in guide and "Random theme" in guide
    assert "Surprise" not in guide


def test_the_two_buttons_say_what_they_change():
    assert "Random theme</button>" in INDEX[INDEX.index('id="theme-surprise"') :][:300]
    assert "Mix palette, accent and density</button>" in INDEX[INDEX.index('id="look-surprise"') :][:300]
    help_text = INDEX[INDEX.index('id="themes-help"') :][:1200]
    assert "Random theme" in help_text and "Mix palette, accent and density" in help_text
    assert "Press Random theme again" in CONTROLS


def test_the_mix_says_what_it_did_without_a_seed_number():
    body = SETTINGS[SETTINGS.index("function surpriseNow") :][:1400]
    assert "`Mixed a look: ${names}.`" in body and "density`" in body
    assert "Mix ${seed}" not in body and "Mix ${" not in body


def test_a_look_change_raises_one_toast_not_the_generic_preference_one():
    data = (ROOT / "frontend/js/settings-data.js").read_text(encoding="utf-8")
    note = data[data.index("function noteSettingChange") :][:900]
    assert "settingsLook.quiet" in note and 'change.kind === "look"' in note
    change = SETTINGS[SETTINGS.index("function changeLookWithUndo") :][:900]
    assert "settingsLook.quiet" in change
    restore = SETTINGS[SETTINGS.index("function restoreLook") :][:500]
    assert "settingsLook.quiet" in restore


def test_reading_choices_are_part_of_a_look_and_a_mix_leaves_them():
    ai = (ROOT / "frontend/js/ai-tools.js").read_text(encoding="utf-8")
    look = ai[ai.index("const OVERRIDABLE_KEYS") :][:500]  # LOOK_KEYS is built from it
    assert '"read-leading"' in look and '"read-measure"' in look
    body = SETTINGS[SETTINGS.index("function surpriseNow") :][:1400]
    assert "read-" not in body
    out = _run('console.log(JSON.stringify(settingsLook.lookFile.check({kind:"tessellate-look",version:1,values:{"read-leading":"roomy","read-measure":"wide"}})))')
    assert out["values"] == {"read-leading": "roomy", "read-measure": "wide"} and not out["skipped"]
    bad = _run('console.log(JSON.stringify(settingsLook.lookFile.check({kind:"tessellate-look",version:1,values:{"read-leading":"huge","fontsize":"large"}})))')
    assert bad["values"] == {} and len(bad["skipped"]) == 2


def test_the_live_editor_follows_line_spacing():
    # 09-editor.css, or library-lazy.css for a rule only the Library bundle draws (UI plan 13b, L459).
    editor = "\n".join((ROOT / "frontend/css" / n).read_text(encoding="utf-8") for n in ("09-editor.css", "library-lazy.css"))
    for tag, value in (("tight", "1.44"), ("roomy", "1.84")):
        sel = f':root[data-read-leading="{tag}"] .doc-editor .cm-editor:not(.doc-content-code) .cm-scroller'
        at = editor.index(sel + " {")
        assert f"line-height: {value};" in editor[at : editor.index("}", at)]
