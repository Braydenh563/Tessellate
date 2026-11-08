"""Surprise mix: a seeded pick of palette, accent and density (BACKLOG, More themes).

Runs the shipped picker under node (the helpers are test_look_share_1108's);
the button, its Undo and its help are read from the source.
"""

from __future__ import annotations

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
    more = (ROOT / "src/tessellate/ai/help_topics_more.py").read_text(encoding="utf-8")
    assert "Surprise mix" in more[more.index('"id": "themes"') :][:3000]
