"""The god modules' line caps, ratcheted so they only go down (audit AR3,
ranked row 36, gods-1101).

`composer.py` was 6,376 lines, `routes_chat.py` 6,198, `routes_whiteboard.py` 6,344 and `ai/tools/__init__.py` 5,282 before their layers
were moved out whole, each to a module with one reason to exist that imports
only the layers below it (the design is in
docs/roadmap/agent-remaining/gods-1101.md, gods2-1102.md and gods3-1102.md). A cap here is the file's size
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
    "ai/composer.py": 958,
    "api/routes_chat.py": 2281,
    #: The routes and models moved out whole to the wb_*.py layers; this module only includes them (gods-2).
    "api/routes_whiteboard.py": 64,
    #: The table moved out whole to help_topics_core.py (audit AI23): 3,740 lines before.
    "ai/help_chat.py": 1360,
    #: The rules and the turn plan moved out whole to agent_policy.py and agent_turn.py (audit AI23).
    "ai/agent.py": 1228,
    #: The registry and the tools moved out whole to tool_*.py layers by tool family; `__init__` only re-exports (gods3-1102): 5,282 lines before.
    "ai/tools/__init__.py": 48,
    "ai/tools/tool_focus.py": 179,
    "ai/tools/tool_handoff.py": 126,
    "ai/tools/tool_learn.py": 229,
    "ai/tools/tool_read.py": 952,
    "ai/tools/tool_run.py": 304,
    "ai/tools/tool_schema.py": 342,
    "ai/tools/tool_sets.py": 366,
    "ai/tools/tool_skills.py": 153,
    "ai/tools/tool_table.py": 1491,
    "ai/tools/tool_turn.py": 346,
    "ai/tools/tool_web.py": 157,
    "ai/tools/tool_write.py": 539,
    #: The overlay engine's constants and its method groups moved out whole to engine_*.py (audit K24): 4,845 lines before. `Engine` inherits the four mixins.
    "core/overlay/engine.py": 2910,
    "core/overlay/engine_consts.py": 600,
    "core/overlay/engine_flight.py": 490,
    "core/overlay/engine_frames.py": 308,
    "core/overlay/engine_input.py": 325,
    "core/overlay/engine_roam.py": 426,
    #: The digest's words and sentence rules, then its facts and lines, moved out whole in two layers (audit K24): 6,230 lines before.
    "ai/composer_digest.py": 2341,
    "ai/composer_digest_lines.py": 2729,
    "ai/composer_digest_sentences.py": 1291,
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
