"""Source text: part of this reads the shipped CSS, markup or script, whose effect needs a browser this suite does not run; what was measured in the app is below.

LEDGER L479: the On this day row no longer pushes the phone's list down 44px.

The chips are asked for a second after the rows, so on a phone they arrived
into a hidden row and moved everything under it. The day's answer is
remembered; a later open that day holds the one-chip slot from the first frame.
Measured at 390 (scratchpad probe): the first open of a day still moves 44px,
a later open moves 0 (first row at 427 before and after the chips).
"""
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent / "frontend"
JS = (ROOT / "js" / "timeline.js").read_text(encoding="utf-8")
CSS = (ROOT / "css" / "06-timeline-dialogs.css").read_text(encoding="utf-8")


def test_the_recall_slot_is_held_from_the_remembered_answer_on_a_phone():
    hold = JS[JS.index("timelineRecall.hold = () =>") :][:600]
    assert "max-width: 599.98px" in hold
    assert 'prefs.get("timeline-recall-day", "") === `${timelineRecall.today()}:1`' in hold
    assert 'row.classList.toggle("is-held", held);' in hold
    # Held before the rows paint, remembered once the chips are known.
    show = JS.index("timelineRecall.hold();\n  paintTimeline();")
    assert show > 0
    render = JS[JS.index("async function renderTimelineRecall()") :][:4200]
    assert 'row.classList.remove("is-held");' in render
    assert 'prefs.set("timeline-recall-day", `${md}:${chips.length ? 1 : 0}`);' in render


def test_the_held_slot_is_one_chip_tall_with_its_ring_room():
    rule = CSS[CSS.index(".timeline-recall.is-held {") :][:200]
    assert "max(var(--control-h), var(--target-min)) + 2 * var(--ring-room)" in rule
