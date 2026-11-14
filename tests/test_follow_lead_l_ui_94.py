"""L-ui-modernisation-94 (INBOX 1830): on a moving panel the follow loop leads by the panel's measured velocity.

Source text: "the companion's follow loop reads after the draw (tests/test_lag_layout_reads_1766.py, no forced
layout), so on a moving panel it trails by one frame (7.6px at a 0.6s slide). Recommendation, taken: keep the read
where it is and place the companion at the last read plus the panel's measured velocity times the time since that
read, while `nmbFollow.moving`; no layout is read in the frame."
"""

from __future__ import annotations

from tests.test_lag_layout_reads_1766 import AV, READS, _code, _fn


def test_source_text_the_frame_turn_leads_before_it_hands_over_to_the_read() -> None:
    """Source text: "place the companion at the last read plus the panel's measured velocity times the time since that read"."""
    ask = _fn(AV, "nameMarkBuddyFollowFrame.ask = function nameMarkBuddyFollowAsk(")
    assert "nmbFollow.turnAt = t" in ask and "nameMarkBuddyFollowFrame.lead(t)" in ask
    assert ask.index("nameMarkBuddyFollowFrame.lead(t)") < ask.index("setTimeout(")


def test_source_text_the_lead_reads_no_layout_and_runs_only_while_moving() -> None:
    """Source text: "while `nmbFollow.moving`; no layout is read in the frame"."""
    lead = _code(_fn(AV, "nameMarkBuddyFollowFrame.lead = function nameMarkBuddyFollowLead("))
    assert not READS.search(lead), READS.search(lead).group(0)
    assert "!nmbFollow.moving" in lead and "g.lead" in lead
    assert "nmbFollow.pm.end" in lead, "the lead stops at the panel animation's end: an ease-in slide stops at full speed"
    assert "buddy.style.transform" in lead and "nmb.lx" in lead and "nmb.ly" in lead


def test_source_text_the_read_measures_velocity_on_the_frame_clock() -> None:
    """Source text: "the panel's measured velocity times the time since that read"."""
    follow = _fn(AV, "function nameMarkBuddyFollow(eased = false) {")
    assert "nmbFollow.turnAt || at" in follow and "g.lead = {" in follow
    frame = _fn(AV, "function nameMarkBuddyFollowFrame(now) {")
    assert frame.index("nameMarkBuddyFollow();") < frame.index("nmbFollow.turnAt = 0")
    moving = _fn(AV, "function nameMarkBuddyPanelMoving(el) {")
    assert "pm.end = " in moving and "anim.startTime" in moving


def test_source_text_an_animation_on_its_panel_is_looked_for_on_the_next_frame() -> None:
    """Source text: "while `nmbFollow.moving`": a slide that starts slow is found moving before the loop naps."""
    i = AV.index('for (const type of ["pointerdown", "pointerup", "keydown", "transitionrun"')
    body = AV[i : AV.index("nameMarkBuddyKeepUp(1500, near);", i)]
    assert 'if (near && (type === "transitionrun" || type === "animationstart")) nmbFollow.movingAt = 0;' in body
