"""The rest of INBOX 1741's lag: first looks taken after a frame has drawn, and the anonymous timers named.

At 4x CPU the rig's first look and the follow loop's look after a nap ran in frame callbacks, before the frame's
style pass, and settled whatever the figure's own writes had dirtied. They run in a task after a drawn frame now.
"""

from __future__ import annotations

from pathlib import Path

JS = Path(__file__).resolve().parents[1] / "frontend" / "js"
AVATARS = (JS / "avatars.js").read_text(encoding="utf-8")
MOTION = (JS / "atlas-motion.js").read_text(encoding="utf-8")
DASH = (JS / "dashboard.js").read_text(encoding="utf-8")


def test_the_rigs_first_look_waits_for_a_drawn_frame() -> None:
    assert "(rig.reads ? atlasRigWake.after : atlasRigWake.afterPaint)(" in MOTION
    after = MOTION.split("atlasRigWake.afterPaint = ", 1)[1].split("\n};", 1)[0]
    assert "setTimeout(function atlasRigWakeFirstLook()" in after


def test_the_look_after_a_nap_is_taken_after_a_clean_frame_and_a_wake_cancels_it() -> None:
    body = AVATARS.split("function nameMarkBuddyFollowFrame(", 1)[1].split("\n}\n", 1)[0]
    assert "setTimeout(function nameMarkBuddyNapTask()" in body
    assert "nmb.afterClean(function nameMarkBuddyNapLook()" in body
    assert "if (nmbFollow.timer !== own || !nmb.glue) return;" in body


def test_the_other_anonymous_timers_have_names() -> None:
    assert "setTimeout(function nameMarkBuddyAfterCleanTask()" in AVATARS
    assert "setTimeout(function dashSkeletonFollowTask()" in DASH
