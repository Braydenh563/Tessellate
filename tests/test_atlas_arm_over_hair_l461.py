"""Source text: LEDGER L461, "Draw the Atlas feminine right arm in front of the
hair" (libtl-0926: "the feminine right arm (held out, sowing seeds) sits behind
the hair's locks at the full size ... a drawing-order change").

Measured 2026-11-13 with atlasDraw(480, "calm", "full"): 91 of 200 points on
her right arm's outline were topped by the mane before, 0 after; the masculine
look 0 both times.
"""

from tests._app_js import frontend_text


def test_the_single_drawing_puts_the_mane_under_the_body():
    js = frontend_text("atlas.js")
    draw = js[js.index("function atlasDraw(size") :]
    draw = draw[: draw.index("\n}\n")]
    hair = draw.index('const hairAt = spec.body && !figure ? atlasGroup(atlasGroup(rig, "atl-head"')
    body = draw.index("atlasBody(rig, id, figure, look)")
    assert hair < body
    assert "atlasHead(host, id, level, look, hairAt)" in draw
