"""INBOX 1683 x/y, edges-1107 "Left": the in-app companion leaning on a panel's SIDE edge tucks behind it, eyes over the
edge, and comes back out (a panel's top edge, the phone dock and the bars already peek)."""

from __future__ import annotations

import re

from tests.test_companion_motion import AV, ROOT, _fn

CSS08 = (ROOT / "frontend" / "css" / "companion-travel-lazy.css").read_text(encoding="utf-8")


def test_peekside_is_an_act_for_a_leaning_figure_on_a_side_edge() -> None:
    assert re.search(r'peekside: \{ ms: \d+, w: [\d.]+, cool: \d+, poses: \["lean"\], edge: "side" \}', AV)
    assert 'emerge: { ms: 800, w: 0, cool: 0, poses: ["sit", "stand", "lean"] }' in AV
    # One settings row turns both peeks off; no second menu row to explain.
    assert '["peek", "Peek from behind a panel", ["peek", "peekside"]]' in AV
    assert '"peekside"' in AV.split("const NMB_RESTING_ACTS", 1)[1].split("\n", 1)[0]
    assert '"peekside"' in AV.split("const NMB_MANNER_STILL", 1)[1].split("\n", 1)[0]


def test_peekside_ends_by_emerging_never_a_pop() -> None:
    act = _fn("nameMarkBuddyAct")
    assert 'if ((was === "peek" || was === "peekside") && act !== "emerge" && !nameMarkBuddyStill()) act = act || "emerge";' in act


def test_peekside_slides_sideways_against_the_panel_edge_unclipped() -> None:
    for name in ("nmb-peekside-in", "nmb-emerge-side"):
        assert f"@keyframes {name} {{" in CSS08
    assert '#nm-buddy[data-side="left"] { --nmb-side: 1; }' in CSS08
    assert '#nm-buddy[data-side="right"] { --nmb-side: -1; }' in CSS08
    # Intent moved (INBOX 1463 decision): the clip trimmed 6 px off each side wherever the companion stood, at no
    # panel line, which is the cut body 1463 removed; the slide and the glow fade stay.
    assert "clip-path" not in CSS08
    assert "&.nmb-act-peekside .nm-buddy-char { animation: nmb-peekside-in 1.1s ease-in-out forwards; }" in CSS08
    # Its glow and shadow fade with it, as every other hiding act's do.
    assert "#nm-buddy.nmb-act-peekside::after" in CSS08
