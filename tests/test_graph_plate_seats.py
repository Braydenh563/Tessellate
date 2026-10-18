"""B71 (INBOX 904): topic names do not stack on each other or sit on a dot.

The owner: "This image is me separating them out as it was soo messy and
stuck together before I couldn't read it." Under the Topic colour rule each
topic's name sat on a plate straight above its outline's highest point, so two
topics whose tops were near put their plates on top of one another, and a
plate could cover another topic's dots. On the real worker's layout of the
seeded 200-note notebook (`scratchpad/ui-sweeps/graphtopics1018.js`, 1440x900,
9 plates): 1 pair of plates overlapping and 10 plates on a dot before; the
count after is in the CHANGELOG.

`gcSeatTopicPlates` is the one pure function that seats them: it tries the
plate's own spot first, then slides it along its outline's top edge, then
lifts it, and takes the first seat clear of every seated plate and every dot.
"""

import json
import re
import shutil
import subprocess
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
CANVAS = (ROOT / "frontend" / "js" / "graph-canvas.js").read_text(encoding="utf-8")


def _function(text: str, name: str) -> str:
    start = re.search(rf"\nfunction {name}\(", text).start() + 1
    return text[start : text.index("\n}\n", start) + 2]


def _run(cases: dict) -> dict:
    node = shutil.which("node")
    if not node:
        pytest.skip("node is not installed")
    script = _function(CANVAS, "gcSeatTopicPlates") + f"\nconsole.log(JSON.stringify(gcSeatTopicPlates(...{json.dumps(cases)}.args)));"
    out = subprocess.run([node, "-e", script], capture_output=True, text=True, check=True)
    return json.loads(out.stdout)


def _hit(a: dict, b: dict) -> bool:
    return a["left"] < b["right"] and b["left"] < a["right"] and a["top"] < b["bottom"] and b["top"] < a["bottom"]


def _entry(topic: int, cx: float, top: float, width: float = 80) -> dict:
    return {"topic": topic, "cx": cx, "top": top, "minX": cx - 60, "maxX": cx + 60, "w": width + 10}


def test_two_topics_with_tops_side_by_side_get_separate_plates() -> None:
    entries = [_entry(1, 100, 50), _entry(2, 140, 52)]
    seats = _run({"args": [entries, [], 1]})
    assert len(seats) == 2
    assert not _hit(seats[0], seats[1]), seats


def test_a_plate_keeps_its_own_spot_when_nothing_is_in_the_way() -> None:
    seats = _run({"args": [[_entry(1, 100, 50)], [], 1]})
    # 27 above the outline's top to 10 above it, centred on the top point.
    assert seats[0]["bottom"] == pytest.approx(40)
    assert seats[0]["top"] == pytest.approx(23)
    assert (seats[0]["left"] + seats[0]["right"]) / 2 == pytest.approx(100)


def test_a_plate_steps_off_a_dot_in_its_way() -> None:
    dots = [{"x": 100, "y": 32, "r": 8}]
    seats = _run({"args": [[_entry(1, 100, 50)], dots, 1]})
    seat = seats[0]
    clear = seat["right"] < 92 or seat["left"] > 108 or seat["bottom"] < 24 or seat["top"] > 40
    assert clear, seat


def test_a_crowd_of_topics_stays_apart_and_in_order() -> None:
    entries = [_entry(i, 100 + 15 * i, 50 + (i % 2)) for i in range(6)]
    seats = _run({"args": [entries, [], 1]})
    assert [s["topic"] for s in seats] == list(range(6))
    for i in range(len(seats)):
        for j in range(i + 1, len(seats)):
            assert not _hit(seats[i], seats[j]), (i, j, seats)


def test_the_seat_is_a_function_of_the_draw_not_a_second_layout() -> None:
    body = _function(CANVAS, "gcDrawTopicHulls")
    assert "gcSeatTopicPlates(" in body, "the hull drawing seats its plates through the one function"
    assert "s.topicPlates.push" not in body or "gcSeatTopicPlates" in body
