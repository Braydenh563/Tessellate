"""Say at the turn start that the tools a request needs are switched off (L-chat-2).

ANALYSIS.md:4354: with a tool group turned off in Settings, Tools, the model
was handed the request anyway, tried, and the turn ended on the run-time
refusal (`tool_run`: "The 'delete_tag' tool is turned off ..."), or the model
answered in prose as if it had done the job. Read before the first model call
from the same words that pick the turn's tools (`focus_detail`), so the reply
is one plain sentence and no round is spent.
"""

from __future__ import annotations

from tessellate.ai.tools.tool_focus import focus_detail
from tessellate.ai.tools.tool_sets import CORE_TOOLS, TOOL_GROUPS
from tessellate.core import deps

#: Offered by several groups as the confirm-card route, so it says nothing about which group the words asked for.
_SHARED = frozenset(CORE_TOOLS) | {"propose_act"}


def _disabled() -> set[str]:
    config = deps.peek_config()
    return set(config.get_preference("disabled_tools", []) or []) if config else set()


def _top_groups(question: str) -> list[tuple[str, ...]]:
    ranked = focus_detail(question).ranked
    best = ranked[0][1] if ranked else 0
    return [TOOL_GROUPS[index][0] for index, score in ranked if score == best]


def switched_off_line(question: str) -> str | None:
    """The sentence for a request whose every best-matching tool group is off; None otherwise."""
    disabled = _disabled()
    if not disabled:
        return None
    wanted = [name for group in _top_groups(question) for name in group if name not in _SHARED]
    if not wanted or not set(wanted) <= disabled:
        return None
    names = ", ".join(dict.fromkeys(name.replace("_", " ") for name in wanted))
    return (
        f"The tools this needs are switched off in Settings, Tools ({names}), so I have not tried. "
        "Turn them on there and ask again."
    )
