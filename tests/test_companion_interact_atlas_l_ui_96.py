"""Source text: the sweep is a node script run against a live server, outside pytest, so this reads its check as text. The interact sweep has an Atlas reading for a pet (L-ui-modernisation-96).

KIND=atlas companioninteract.js failed its pet check on `data-expr`, which
only a face drawn from a name carries: Atlas's face is its mood, and
`nameMarkBuddyExpress` passes a pet's "happy" over on Atlas. What a pet
really sets on both is the wiggle act and its class on the figure.
"""

from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SWEEP = (ROOT / "scratchpad" / "ui-sweeps" / "companioninteract.js").read_text(encoding="utf-8")
AV = (ROOT / "frontend" / "js" / "avatars.js").read_text(encoding="utf-8")


def test_pet_check_reads_the_wiggle_and_only_asks_a_named_face_for_happy():
    """Source text: the pet check needs the wiggle act and class on every kind, and data-expr happy only off Atlas."""
    assert "wiggle: b.classList.contains('nmb-act-wiggle'), atlas: !!b.querySelector('.nm-atlas')" in SWEEP
    assert "if (pet.act !== 'wiggle' || !pet.wiggle || (!pet.atlas && pet.expr !== 'happy'))" in SWEEP


def test_a_pet_is_a_wiggle_and_atlas_takes_only_drifts_and_renamed_faces():
    """Source text: the app side the sweep reads: a pet asks for happy and a wiggle; on Atlas only a drift or a renamed face is applied."""
    start = AV.index("function nameMarkBuddyPet() {")
    pet = AV[start:AV.index("\n  }\n", start)]
    assert 'nameMarkBuddyExpress("happy", 1800);' in pet and 'nameMarkBuddyAct("wiggle");' in pet
    assert "if ((drift || face !== expr) && typeof setAtlasMood" in AV
