"""The one door every tool call comes through, with each call kept for `/tools`
(O10, L163): `tool_run.execute_tool` wrapped by `ai/tool_history.recorded`.
`tools.execute_tool` is this name."""

from __future__ import annotations

from tessellate.ai.tool_history import recorded
from tessellate.ai.tools.tool_run import execute_tool as _execute_tool

execute_tool = recorded(_execute_tool)
