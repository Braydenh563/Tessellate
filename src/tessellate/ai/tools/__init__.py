"""Agentic tools: actions the chat model can take on the
notebook, offered to Ollama's native tool-calling API.

Rules of the registry:
- every tool wraps the existing manager layer / models, no new data
  logic lives here, so the AI can't do anything the UI can't;
- destructive tools never run inside the agent loop: the UI shows the
  user a confirm button, which calls POST /chat/tools/execute;
- everything is audit-logged (the wrapped functions do that) and
  deletes are soft, so anything the AI does is recoverable.

Layers, in import order (each imports only those above it; this module
imports them all and re-exports every name that anything else reads, so
`tools.TOOLS`, `tools.execute_tool` and the rest still work):

1. `tool_read`: the tools that read the notebook.
2. `tool_skills`: past chats and the parts of the skill tools that do not read the registry.
3. `tool_write`: the tools that change notes.
4. `tool_web`: search, read a page, prefetch.
5. `tool_turn`: ask the user, run a skill, make a plan, compress, propose an act.
6. `tool_learn`: a saved preference, the learned-note audits.
7. `tool_sets`: write, change, add and core tool names; the groups; the Settings switch.
8. `tool_table`: the registry `TOOLS`, with the handlers that read it.
9. `tool_handoff`: a skill run checked against the registry, the hand-offs.
10. `tool_focus`: the confirm gate and which tools a turn is offered.
11. `tool_schema`: the schemas the model is shown, compacting, ranking, the budget.
12. `tool_run`: confirm labels, argument checks, `execute_tool`.
"""

from __future__ import annotations

from . import _common, contracts, files, verify, whiteboard  # noqa: F401
from ._common import DOCUMENT_CHARS, MAX_LIST_LIMIT, PREVIEW_CHARS, ToolError, ToolSpec, _READ_MORE  # noqa: F401
from .whiteboard import MAX_DIAGRAM_NODES  # noqa: F401
from tessellate.entry import manager  # noqa: F401
from tessellate.ai.tools.tool_read import GRAPH_PREVIEW_CHARS, MAX_GRAPH_NOTES, _count_notes, _graph_neighbours, _list_notes, _related_notes, _scope_filters, _search_notes, _suggested_neighbours  # noqa: F401  (moved; re-exported)
from tessellate.ai.tools import tool_skills  # noqa: F401
from tessellate.ai.tools.tool_write import LINK_TYPE_DESCRIPTION_CHARS, PRIVATE_REMINDER, private_note_ids  # noqa: F401  (moved; re-exported)
from tessellate.ai.tools.tool_web import READ_URL_MAX_CHARS, prefetch_web  # noqa: F401  (moved; re-exported)
from tessellate.ai.tools.tool_turn import MAX_ASK_OPTION, MAX_ASK_OPTIONS, MAX_COMPRESS_TURNS, OneOptionAsk, summarise_turns, validate_ask, validate_compress_chat, validate_make_plan  # noqa: F401  (moved; re-exported)
from tessellate.ai.tools.tool_learn import MAX_ACTIVE_PREFERENCES, MAX_PREFERENCE_CHARS  # noqa: F401  (moved; re-exported)
from tessellate.ai.tools.tool_sets import ADD_TOOLS, CHANGE_TOOLS, CORE_TOOLS, TOOL_GROUPS, WRITE_TOOLS, tool_enabled, web_barred  # noqa: F401  (moved; re-exported)
from tessellate.ai.tools.tool_table import TOOLS, call_example  # noqa: F401  (moved; re-exported)
from tessellate.ai.tools.tool_handoff import HANDOFFS, RUN_STARTERS, handoff_event, validate_run_skill  # noqa: F401  (moved; re-exported)
from tessellate.ai.tools.tool_focus import adds_to_a_named_note, focus_detail, focus_for, is_follow_through, needs_confirm  # noqa: F401  (moved; re-exported)
from tessellate.ai.tools.tool_schema import COMPACT_DESCRIPTION_CHARS, COUNTING_TOOLS, ORCHESTRATION_TOOLS, SMALL_WINDOW_CHARS, asks_for_plan, budget_for_window, compact_schemas, keep_first_for, ollama_tools, rank_tools, ranking_line, schema_chars, tool_catalog, with_relation_types, within_budget  # noqa: F401  (moved; re-exported)
from tessellate.ai.tools.tool_run import _ai_actor, _coerce, check_arguments, confirm_label, example_arguments  # noqa: F401  (moved; re-exported)
from tessellate.ai.tools.tool_door import execute_tool  # noqa: F401  (`tool_run.execute_tool`, each call kept for `/tools`)
