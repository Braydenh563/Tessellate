"""Atlas takes a face it has a mood for (L-ui-modernisation-101).

`nameMarkBuddyExpress` applied a face on Atlas only as a drift or a renamed
one, so a pet's "happy" and every other same-name face (love, laughing,
surprised, sleepy) never showed. A face Atlas has a mood for is now applied
the quiet way; a face it has none for is passed over, so it never resets
Atlas to calm.
"""

from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
AV = (ROOT / "frontend" / "js" / "avatars.js").read_text(encoding="utf-8")


def _atlas_branch() -> str:
    start = AV.index("function nameMarkBuddyExpress(")
    start = AV.index("if (isAtlasSeed(seed)) {", start)
    return AV[start:AV.index("return;\n    }", start)]


def test_a_named_face_is_applied_on_atlas_quietly():
    """Source text: the Atlas branch applies any face in ATLAS_MOODS, with a duration or as a drift, quietly, only from calm."""
    body = _atlas_branch()
    assert "ATLAS_MOODS[face]" in body
    assert "(drift || face !== expr)" not in body
    assert "setAtlasMood(face, ms, { quiet: true })" in body
    assert 'atlasMoodNow === "calm"' in body


def test_a_face_atlas_has_no_mood_for_is_passed_over():
    """Source text: an unnamed face (dizzy, cool, the empty hold) needs ATLAS_MOODS to name it, so calm is never re-applied."""
    body = _atlas_branch()
    assert 'typeof ATLAS_MOODS !== "undefined" && ATLAS_MOODS[face]' in body
    assert "(ms || drift)" in body


def test_excited_takes_delighted_on_atlas():
    """Source text: the renames give excited Atlas's delighted, so a cheer shows."""
    assert 'excited: "delighted"' in _atlas_branch()
