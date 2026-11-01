"""The god modules' line caps, ratcheted so they only go down (audit AR3,
ranked row 36, gods-1101).

`composer.py` was 6,376 lines and `routes_chat.py` 6,198 before their layers
were moved out whole, each to a module with one reason to exist that imports
only the layers below it (the design is in
docs/roadmap/agent-remaining/gods-1101.md). A cap here is the file's size
when that split landed. A file that grows past its cap fails: put the new
code in the layer it belongs to, or start one. A file that shrinks well
under its cap fails too, until the cap is lowered to the new size, so the
number only moves down.
"""

from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1] / "src" / "tessellate"

#: Lines per file when the split landed. Lower a number when the file
#: shrinks; never raise one.
CAPS = {
    "ai/composer.py": 962,
    "api/routes_chat.py": 2474,
    #: The table moved out whole to help_topics_core.py (audit AI23): 3,740 lines before.
    "ai/help_chat.py": 1370,
}
#: How far under its cap a file may fall before the cap must come down.
SLACK = 50


def _lines(rel: str) -> int:
    return len((ROOT / rel).read_text(encoding="utf-8").splitlines())


def test_no_god_module_grows_past_its_cap() -> None:
    over = {rel: f"{_lines(rel)} > {cap}" for rel, cap in CAPS.items() if _lines(rel) > cap}
    assert not over, f"over its line cap; move the code to its layer instead: {over}"


def test_a_cap_comes_down_when_its_file_shrinks() -> None:
    slack = {rel: f"{_lines(rel)} lines, cap {cap}" for rel, cap in CAPS.items() if _lines(rel) < cap - SLACK}
    assert not slack, f"lower the cap to the file's size: {slack}"
