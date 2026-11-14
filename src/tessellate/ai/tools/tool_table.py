"""The registry: `TOOLS`, with the handlers that read it (list tools, skills, a worked example).

Moved whole from `__init__.py` (audit AR3, gods-2): the code is unchanged, and
`__init__` re-exports every name here that anything reads. Imports run one way,
down the layer list in `__init__.py`'s docstring, never back to `__init__`.
"""

from __future__ import annotations

import json

from tessellate.ai.tools._common import DEFAULT_LIST_LIMIT, MAX_LIST_LIMIT, ToolError, ToolSpec, _clip
from tessellate.core.database import LINK_TYPES
from tessellate.ai.tools.whiteboard import MAX_DIAGRAM_NODES, _add_map_node, _add_whiteboard_card, _add_whiteboard_link, _create_mindmap, _generate_diagram, _link_map_nodes, _map_from_note, _read_mindmap, _read_whiteboard, _search_whiteboard
from sqlalchemy.orm import Session
from tessellate.ai.tools.board_edit import _add_board_shape, _delete_board_item, _edit_board_item, _list_library, _move_board_item, _place_library_item, _restore_board_item
from tessellate.ai.tools.categories import _create_category, _delete_category, _merge_categories, _rename_category
from tessellate.ai.tools.documents import _create_document, _delete_document, _get_document, _list_documents
from tessellate.ai.tools.moving import _move_notes
from tessellate.ai.tools.files import _read_file, _search_files
from tessellate.core import deps
from tessellate.ai import skills
from tessellate.ai.tools.tool_sets import CHANGE_TOOLS, WRITE_TOOLS, tool_enabled
from tessellate.ai.tools.tool_turn import _ask_user, _compress_chat, _make_plan, _run_skill
from tessellate.ai.tools.tool_learn import _audit_link_reasons, _check_learned, _find_contradictions, _save_user_preference
from tessellate.ai.tools.tool_path import _path_between
from tessellate.ai.tools.tool_read import _calculate, _check_answer, _count_notes, _find_similar_notes, _get_current_time, _get_note_tool, _list_categories, _list_notes, _list_tags, _notebook_overview, _notebook_structure, _propose_act, _read_text, _related_notes, _search_help, _search_notes, _summarize_notes
from tessellate.ai.tools.tool_write import _complete_reminder, _create_note, _delete_note, _delete_tag, _edit_note, _link_notes, _list_reminders, _pin_note, _rename_tag, _restore_note, _set_reminder, _tag_note, _unlink_notes, link_type_description
from tessellate.ai.tools.tool_skills import _delete_skill, _search_chat_history, _verify_block
from tessellate.ai.tools.tool_web import _read_url, _web_search

def _tool_group(name: str) -> str:
    """What a tool does to the notebook, as Settings, Tools groups it."""
    if name in ("web_search", "read_url"):
        return "online"
    spec = TOOLS[name]
    #: Every write asks first now (the owner, 2026-11-10), so no tool is in a "write" group.
    return "confirm" if spec.destructive or name in CHANGE_TOOLS or name in WRITE_TOOLS else "read"


def _list_tools(session: Session, args: dict) -> dict:
    """Every tool the assistant has, so a model asked what it can do, or
    reaching for one it was not shown, looks it up instead of guessing (O10;
    BACKLOG "A tool to list the tools"). `filter` keeps the ones whose name
    or description holds the word. Read-only."""
    if str(args.get("name") or "").strip():
        return _describe_tool(session, args)
    word = str(args.get("filter") or "").strip().lower()
    rows = [
        {"name": spec.name, "does": spec.description.split(". ")[0].rstrip(".")[:140], "group": _tool_group(spec.name),
         "enabled": tool_enabled(spec.name)}
        for spec in TOOLS.values()
        if not word or word in spec.name.lower() or word in spec.description.lower()
    ]
    return {"tools": rows, "total": len(rows), "label": f"ph:wrench Listed {len(rows)} tools" + (f" for “{_clip(word, 30)}”" if word else "")}


def _describe_tool(session: Session, args: dict) -> dict:
    """One tool's whole description, its arguments and a worked call
    (`list_tools` with a name)."""
    name = str(args.get("name") or "").strip()
    spec = TOOLS.get(name)
    if spec is None:
        return {"error": f"There is no tool called “{_clip(name, 40)}”; list_tools names them."}
    return {
        "name": name, "description": spec.description, "parameters": spec.parameters, "example": call_example(name),
        "group": _tool_group(name), "enabled": tool_enabled(name), "label": f"ph:wrench Read how {name} works",
    }


def _list_skills(session: Session, args: dict) -> dict:
    """Everything runnable, built-ins included.

    The built-ins used to live only in `app.js`, so a model asked "what skills
    do I have?" answered with the user's own and nothing else, while the
    interface showed ten more. `tools` or `tool` asks for the tools instead
    (`_list_tools`).
    """
    if args.get("tools") or str(args.get("tool") or "").strip():
        return _list_tools(session, {"name": args.get("tool")})
    config = deps.get_config()
    catalog = skills.catalog(config, set(TOOLS))
    return {
        "skills": [
            {
                "name": skill["name"],
                # What it is, and, the part that makes it findable, when to
                # reach for it. Without `when_to_use` a model reading this list
                # can see that a skill exists and has no basis for choosing it.
                "description": skill.get("description", ""),
                "when_to_use": skill.get("when_to_use", ""),
                "prompt": _clip(skill["prompt"], 200),
                "steps": skill["steps"],
                "tools": skill["tools"],
                "inputs": [item["name"] for item in skill["inputs"]],
                "builtin": skill["builtin"],
                # What running it commits to, so the choice can be made on
                # something more than the name. A skill that changes notes is a
                # different proposition from one that only reads them.
                "step_count": len(skill["steps"]),
                "changes_notes": bool(set(skill["tools"]) & WRITE_TOOLS),
            }
            for skill in catalog
        ],
        "count": len(catalog),
        "note_to_model": (
            "Built-in skills can be run but not edited. A skill's steps and "
            "tools are what it does, copy that shape when you make one. "
            "`when_to_use` says when a skill applies; `changes_notes` says "
            "whether running it would alter the notebook. Start one with "
            "run_skill, passing its name exactly as written here and values "
            "for any `inputs`, that ends your turn and the run takes over. "
            "Only start one that matches what was asked; a skill that changes "
            "notes is not the way to answer a question."
        ),
        "label": "ph:lightning Listed the saved skills",
    }


def _save_skill(session: Session, args: dict) -> dict:
    """Create or update one skill. Same tool for both, because from the
    model's side "make me a skill that does X" is one intent, and a separate
    update tool just adds a way to get it wrong.

    `steps` and `tools` are the rebuild (roadmap §21): without somewhere to
    put them, "make me a skill that files my inbox notes" could only ever
    save another sentence.

    The four flat `verify_*` arguments become one `verify` block
    (`skills.verify_spec` validates it and says what is wrong in the model's
    own words, so a bad predicate name is refused here rather than at the end
    of a run).
    """
    config = deps.get_config()
    try:
        skill = skills.normalise(
            {
                "name": args.get("name"),
                "prompt": args.get("prompt"),
                "steps": args.get("steps"),
                "tools": args.get("tools"),
                "when_to_use": args.get("when_to_use"),
                "verify": _verify_block(args),
            },
            set(TOOLS),
        )
    except skills.SkillError as exc:
        raise ToolError(str(exc)) from exc
    if any(skill["name"] == shipped["name"] for shipped in skills.builtins()):
        raise ToolError(
            f"“{skill['name']}” is a built-in skill, pick a different name"
        )
    stored = skills.stored(config)
    existed = any(s.get("name") == skill["name"] for s in stored)
    if len(stored) >= skills.MAX_SKILLS and not existed:
        raise ToolError(
            f"There are already {skills.MAX_SKILLS} saved skills: delete one first"
        )
    config.set_preference(
        "skills", [s for s in stored if s.get("name") != skill["name"]] + [skill]
    )
    return {
        "name": skill["name"],
        "updated": existed,
        "steps": len(skill["steps"]),
        "tools": skill["tools"],
        # Said back, because a model that asked for a postcondition and got
        # none (a blank tool name, a predicate that was dropped) would
        # otherwise report having added a check the skill does not carry.
        "verify": skill.get("verify"),
        "label": f"ph:lightning {'Updated' if existed else 'Created'} the “{skill['name']}” skill",
    }


# --- the registry ---------------------------------------------------------------

_NOTE_ID = {"type": "integer", "description": "The note's id number"}


TOOLS: dict[str, ToolSpec] = {
    spec.name: spec
    for spec in [
        ToolSpec(
            "find_contradictions",
            "Finds places where the user's own notes disagree with each other, a decision reversed, a date that moved, a view they changed. Reports them; does not link anything.",
            {
                "type": "object",
                "properties": {
                    "limit": {"type": "integer", "description": "Max contradictions to report (default 5, max 10)"}
                },
            },
            _find_contradictions,
        ),

        ToolSpec(
            "check_learned",
            "Re-check what was learned about the user against the notes as they are now: retire "
            "what no longer holds, flag what needs a look (two notes disagree, a date passed).",
            {"type": "object", "properties": {}},
            _check_learned,
        ),
        ToolSpec(
            "audit_link_reasons",
            "Audits vague graph link reasons (like 'similar in meaning') and rewrites them by deducing a specific reason based on both notes.",
            {
                "type": "object",
                "properties": {
                    "limit": {"type": "integer", "description": "Max number of links to process (default 50)"}
                },
            },
            _audit_link_reasons,
        ),
        ToolSpec(
            "save_user_preference",
            # "Suggest", not "save": the tool proposes and the user accepts.
            # Saying so in the description matters as much as the code, a
            # model told it has *saved* something will act as though the rule
            # is already in force.
            "Suggest a standing preference for the user to accept. Use it when they state a "
            "rule or work style to remember. It does NOT take effect until they accept it.",
            {
                "type": "object",
                "properties": {
                    "preference": {"type": "string", "description": "A clear, concise rule or fact to remember."},
                },
                "required": ["preference"],
            },
            _save_user_preference,
        ),
        ToolSpec(
            "ask_user",
            # Terse on purpose: this tool is offered on every turn, so every
            # character is paid for on every round. The two rules that stop it
            # being misused (stop after asking; don't ask what you could look
            # up) are worth their space; nothing else here is.
            "Ask which of 2-6 options the user meant, when the request is "
            "ambiguous. Your turn ENDS; their reply comes next. Don't ask "
            "permission, and don't ask what search_notes could tell you.",
            {
                "type": "object",
                "properties": {
                    "question": {"type": "string", "description": "One short sentence"},
                    "options": {
                        "type": "array",
                        "items": {"type": "string"},
                        "description": "2-6 short answers",
                    },
                },
                "required": ["question", "options"],
            },
            _ask_user,
            ends_turn=True,
        ),
        ToolSpec(
            "search_notes",
            "Search the user's notes by meaning or keywords. Use this to find "
            "note ids before editing, tagging, linking, or deleting anything.",
            {
                "type": "object",
                "properties": {
                    "query": {"type": "string", "description": "What to search for"},
                    "limit": {"type": "integer", "description": "Max results (1-10)"},
                },
                "required": ["query"],
            },
            _search_notes,
        ),
        ToolSpec(
            "related_notes",
            "A note's connections: what it links to, what replies to it, what shares its "
            "tags, each with HOW and how far. include_suggestions adds notes that READ alike "
            "but were never linked: guesses, not connections.",
            {
                "type": "object",
                "properties": {
                    "note_id": _NOTE_ID,
                    "depth": {
                        "type": "integer",
                        "description": "1 = direct connections, 2 = their connections too",
                    },
                    "include_suggestions": {
                        "type": "boolean",
                        "description": "Also list notes that READ alike but were never linked",
                    },
                },
                "required": ["note_id"],
            },
            _related_notes,
        ),
        ToolSpec(
            "path_between",
            "For 'how are these two notes related?': the chain joining them, each step a "
            "link, a reply thread or a shared tag. For what surrounds one note, use "
            "related_notes.",
            {
                "type": "object",
                "properties": {
                    "note_id": _NOTE_ID,
                    "other_note_id": {
                        "type": "integer",
                        "description": "The note to find a route to",
                    },
                },
                "required": ["note_id", "other_note_id"],
            },
            _path_between,
        ),
        ToolSpec(
            "notebook_structure",
            "The notebook's SHAPE, not its filing: which notes cluster, the best-connected "
            "hubs, and notes connected to nothing. Use it before reorganising or when asked "
            "what to link; list_categories describes filing.",
            {"type": "object", "properties": {}},
            _notebook_structure,
        ),
        ToolSpec(
            "get_note",
            "Read one note in full, by id. search_notes and list_notes give only previews: "
            "read the note before quoting it or answering a detailed question about it.",
            {
                "type": "object",
                "properties": {"note_id": _NOTE_ID},
                "required": ["note_id"],
            },
            _get_note_tool,
        ),
        ToolSpec(
            "list_notes",
            "Walk the user's notes, newest first, optionally by category, tag, age or "
            "untagged; while has_more, call again with next_offset. untagged:true for "
            "'tag my untagged notes'; search_notes finds something specific.",
            {
                "type": "object",
                "properties": {
                    "category": {
                        "type": "string",
                        "description": "Only this category (optional)",
                    },
                    "tag": {"type": "string", "description": "Only notes with this tag"},
                    "untagged": {
                        "type": "boolean",
                        "description": "Only notes that have no tags at all",
                    },
                    "since": {
                        "type": "string",
                        "description": "Optional window: 'this week', 'since Friday', 'last month', or a number of days",
                    },
                    "limit": {
                        "type": "integer",
                        "description": f"Notes per page (1-{MAX_LIST_LIMIT}, "
                        f"default {DEFAULT_LIST_LIMIT})",
                    },
                    "offset": {
                        "type": "integer",
                        "description": "Skip this many: use next_offset from the "
                        "previous call to page",
                    },
                },
            },
            _list_notes,
        ),
        ToolSpec(
            "count_notes",
            "Count the user's notes: in total, per category, or for one "
            "category, tag, age or untagged. Numbers only: the cheap way to "
            "answer 'how many…'.",
            {
                "type": "object",
                "properties": {
                    "category": {
                        "type": "string",
                        "description": "Only count this category (optional)",
                    },
                    "tag": {
                        "type": "string",
                        "description": "Only count notes with this tag (optional)",
                    },
                    "untagged": {
                        "type": "boolean",
                        "description": "Only count notes with no tags at all "
                        "(optional)",
                    },
                    "since": {
                        "type": "string",
                        "description": "Optional window: 'this week', 'since Friday', 'last month', or a number of days",
                    },
                },
            },
            _count_notes,
        ),
        ToolSpec(
            "list_tags",
            "List every tag in use with how many notes carry it, most-used "
            "first. Use it to find the exact tag name before filtering by it.",
            {"type": "object", "properties": {}},
            _list_tags,
        ),
        ToolSpec(
            "notebook_overview",
            "Categories, tags and the total note count, in one call: use it "
            "instead of list_categories + list_tags + count_notes for the "
            "notebook's overall shape.",
            {"type": "object", "properties": {}},
            _notebook_overview,
        ),
        ToolSpec(
            "list_documents",
            "The user's long-form documents, newest first, optionally by a word in the title "
            "or body. Documents are never searched with notes: use this for anything they "
            "wrote up properly.",
            {
                "type": "object",
                "properties": {
                    "query": {
                        "type": "string",
                        "description": "Only documents containing this text (optional)",
                    },
                    "limit": {"type": "integer", "description": "Per page"},
                    "offset": {"type": "integer", "description": "Skip this many"},
                },
            },
            _list_documents,
        ),
        ToolSpec(
            "search_files",
            "Search the user's uploaded files (photos, scans, PDFs, attachments) by name, "
            "caption or the text read from them. Use it for anything about a picture or file:"
            " notes never hold a file's contents.",
            {
                "type": "object",
                "properties": {
                    "query": {
                        "type": "string",
                        "description": "Words to look for in the name, caption or extracted text",
                    },
                    "limit": {"type": "integer", "description": "How many at most"},
                },
            },
            _search_files,
        ),
        ToolSpec(
            "read_file",
            "Everything the app knows about one file: its caption and the text read from it. "
            "Takes `kind` and `id` as search_files gave them. Long text is capped: pass query.",
            {
                "type": "object",
                "properties": {
                    "kind": {
                        "type": "string",
                        "description": "'upload' or 'attachment', from search_files",
                    },
                    "file_id": {"type": "integer", "description": "The file's id"},
                    "query": {
                        "type": "string",
                        "description": "Optional: a word or phrase to find; returns "
                        "the text around it, not only the start.",
                    },
                },
                "required": ["kind", "file_id"],
            },
            _read_file,
        ),
        ToolSpec(
            "create_document",
            "Write a new long-form document (an essay, a report, a write-up) "
            "and save it. For short captured thoughts use create_note "
            "instead: a document is something sat down and written.",
            {
                "type": "object",
                "properties": {
                    "title": {"type": "string", "description": "A title, up to 200 characters"},
                    "content": {
                        "type": "string",
                        "description": "The whole document, in Markdown",
                    },
                },
                "required": ["title", "content"],
            },
            _create_document,
        ),
        ToolSpec(
            "delete_document",
            "Delete a document by id. The app asks the user to confirm first.",
            {
                "type": "object",
                "properties": {
                    "document_id": {"type": "integer", "description": "The document's id"}
                },
                "required": ["document_id"],
            },
            _delete_document,
            destructive=True,
        ),
        ToolSpec(
            "get_document",
            "Read one document in full, by id, after list_documents (previews only). For a "
            "long one, pass query for its most relevant paragraphs instead of the head.",
            {
                "type": "object",
                "properties": {
                    "document_id": {"type": "integer", "description": "The document's id"},
                    "query": {
                        "type": "string",
                        "description": "Optional: what to look for; returns the "
                        "most relevant paragraphs.",
                    },
                },
                "required": ["document_id"],
            },
            _get_document,
        ),
        ToolSpec(
            "read_whiteboard",
            "Read a whiteboard: its cards, text boxes, image count and which cards link. Use "
            "it for 'what's on my board?' or before adding, so nothing is duplicated.",
            {
                "type": "object",
                "properties": {
                    "board_id": {
                        "type": "integer",
                        "description": "The board's note id; omit for the default board.",
                    },
                },
            },
            _read_whiteboard,
        ),
        ToolSpec(
            "search_whiteboard",
            "Search every board for a card or text box containing a word: for 'which board "
            "did I put X on?' when the board is not known.",
            {
                "type": "object",
                "properties": {
                    "query": {"type": "string", "description": "Word or phrase to look for"},
                    "limit": {"type": "integer", "description": "Max results (1-10)"},
                },
                "required": ["query"],
            },
            _search_whiteboard,
        ),
        ToolSpec(
            "add_whiteboard_card",
            "Place an existing note as a card on a whiteboard board. Call "
            "read_whiteboard first so a note is not placed twice.",
            {
                "type": "object",
                "properties": {
                    "note_id": _NOTE_ID,
                    "board_id": {
                        "type": "integer",
                        "description": "The board's note id; omit for the default board.",
                    },
                    "x": {"type": "number", "description": "Board x position (optional)"},
                    "y": {"type": "number", "description": "Board y position (optional)"},
                },
                "required": ["note_id"],
            },
            _add_whiteboard_card,
        ),
        ToolSpec(
            "add_whiteboard_link",
            "Draw a link between two cards already on a whiteboard board "
            "(add_whiteboard_card first).",
            {
                "type": "object",
                "properties": {
                    "from_card_id": {"type": "integer", "description": "The source card's id (not the note id)"},
                    "to_card_id": {"type": "integer", "description": "The target card's id (not the note id)"},
                    "curved": {"type": "boolean", "description": "Curved instead of straight (default false)"},
                },
                "required": ["from_card_id", "to_card_id"],
            },
            _add_whiteboard_link,
        ),
        ToolSpec(
            "generate_diagram",
            "Place a tree of notes on a board in one call. Each node is a new note ('title') "
            "or an existing one ('note_id') with a short 'ref'; children name it as "
            "'parent_ref'. The root has none, or card:<id> to grow from a board card. "
            "Never invent x/y. "
            f"Up to {MAX_DIAGRAM_NODES} nodes.",
            {
                "type": "object",
                "properties": {
                    "nodes": {
                        "type": "array",
                        "items": {
                            "type": "object",
                            "properties": {
                                "ref": {"type": "string", "description": "Short local id, e.g. 'a'"},
                                "title": {"type": "string", "description": "Content for a new note"},
                                "note_id": {"type": "integer", "description": "An existing note's id instead"},
                                "parent_ref": {"type": "string", "description": "Omit for the root"},
                            },
                            "required": ["ref"],
                        },
                    },
                    "board_id": {
                        "type": "integer",
                        "description": "The board's note id; omit for the default board.",
                    },
                    "layout": {
                        "type": "string",
                        "description": "'tree' (default) or 'radial'",
                    },
                },
                "required": ["nodes"],
            },
            _generate_diagram,
        ),
        # --- mindmaps (MINDMAP_PLAN.md §5 item 14) -------------------------
        #
        # One tool per step, and each description names the tool that comes
        # before it: these are written to AGENT_SKILLS_REFORM.md's Phase A/B
        # contract shape, for a 4B model that will otherwise narrate a step
        # instead of calling anything. `generate_diagram` above is the bulk
        # alternative for *cards*; these four are the map's own, and the one
        # thing they never ask the model for is a coordinate.
        ToolSpec(
            "read_mindmap",
            "Read a mindmap as an indented outline: each node's id, kind and the note or "
            "document it stands for. Use it before adding. Needs board_id; search_whiteboard "
            "finds it.",
            {
                "type": "object",
                "properties": {
                    "board_id": {
                        "type": "integer",
                        "description": "The map's own note id.",
                    },
                },
                "required": ["board_id"],
            },
            _read_mindmap,
        ),
        ToolSpec(
            "create_mindmap",
            "An empty mindmap with one root topic, for 'start a mind map about X'. Returns "
            "board_id and root_id for add_map_node, which builds the tree one node per call.",
            {
                "type": "object",
                "properties": {
                    "title": {"type": "string", "description": "What the map is called"},
                    "kind": {"type": "string", "enum": ["map", "board"], "description": "board: an empty whiteboard, no root"},
                    "root_text": {
                        "type": "string",
                        "description": "The centre node's text (defaults to the title)",
                    },
                },
                "required": ["title"],
            },
            _create_mindmap,
        ),
        ToolSpec(
            "map_from_note",
            "A mind map from one note in one call ('turn this note into a map'): title the "
            "centre, headings and lists the branches. Use it, not create_mindmap plus "
            "add_map_node, for one note's outline.",
            {
                "type": "object",
                "properties": {
                    "note_id": {"type": "integer", "description": "The note to map"},
                    "title": {"type": "string", "description": "The map's name (defaults to the note's title)"},
                },
                "required": ["note_id"],
            },
            _map_from_note,
        ),
        ToolSpec(
            "add_map_node",
            "Add ONE node to a mindmap, under a parent or as a new root. "
            "Call read_mindmap (or create_mindmap) first for the ids. Never "
            "invent x/y. Kind 'topic' is plain text; kind 'note' with "
            "note_id puts an existing note on the map.",
            {
                "type": "object",
                "properties": {
                    "board_id": {"type": "integer", "description": "The map's own note id."},
                    "parent_id": {
                        "type": "integer",
                        "description": "The node this one hangs off. Omit for a new root.",
                    },
                    "text": {"type": "string", "description": "The node's text"},
                    "kind": {
                        "type": "string",
                        "description": "'topic' (default) or 'note'/'document'/'file'/'link'",
                    },
                    "note_id": _NOTE_ID,
                    "ref_id": {
                        "type": "integer",
                        "description": "For a document/file/link node: the id it stands for",
                    },
                },
                "required": ["board_id"],
            },
            _add_map_node,
        ),
        ToolSpec(
            "link_map_nodes",
            "Draw a cross-link between two existing nodes on one mindmap, "
            "what a tree can't express ('this depends on that'); read_mindmap "
            "gives their ids.",
            {
                "type": "object",
                "properties": {
                    "board_id": {"type": "integer", "description": "The map's own note id."},
                    "from_id": {"type": "integer", "description": "The node the link starts at"},
                    "to_id": {"type": "integer", "description": "The node it points at"},
                    "label": {"type": "string", "description": "What the link means (optional)"},
                },
                "required": ["from_id", "to_id"],
            },
            _link_map_nodes,
        ),
        #: Editing what is on a board (FEAT-12, WHITEBOARD_PLAN decision 29):
        #: move, edit and delete ask the person first, like every other tool
        #: that changes their own work; each returns an undo.
        ToolSpec(
            "move_board_item",
            "Move one item on a board so its top-left corner is at x, y (board "
            "units). kind is 'card', 'object' (text box, sticky or frame) or "
            "'shape'; read_whiteboard gives each item's kind, id and corner.",
            {
                "type": "object",
                "properties": {
                    "kind": {"type": "string", "description": "'card', 'object' or 'shape'"},
                    "item_id": {"type": "integer", "description": "The item's id from read_whiteboard"},
                    "x": {"type": "number", "description": "New left edge"},
                    "y": {"type": "number", "description": "New top edge"},
                },
                "required": ["kind", "item_id", "x", "y"],
            },
            _move_board_item,
            destructive=True,
        ),
        ToolSpec(
            "edit_board_item",
            "Change a text box's, sticky's, frame's or shape's words, line "
            "colour or fill, e.g. 'make the risks red'. A card shows its note: "
            "edit the note instead.",
            {
                "type": "object",
                "properties": {
                    "kind": {"type": "string", "description": "'object' or 'shape'"},
                    "item_id": {"type": "integer", "description": "The item's id from read_whiteboard"},
                    "text": {"type": "string", "description": "New words (optional)"},
                    "color": {"type": "string", "description": "Line or text colour, like #cc3333 (optional)"},
                    "fill": {"type": "string", "description": "Fill colour, like #ffee99 (optional)"},
                    "fold": {"type": "boolean", "description": "A sticky's folded corner on or off (optional)"},
                },
                "required": ["kind", "item_id"],
            },
            _edit_board_item,
            destructive=True,
        ),
        ToolSpec(
            "delete_board_item",
            "Take one item off a board (its connectors go with it). A card's "
            "note stays in the notebook. The app asks the person first.",
            {
                "type": "object",
                "properties": {
                    "kind": {"type": "string", "description": "'card', 'object' or 'shape'"},
                    "item_id": {"type": "integer", "description": "The item's id from read_whiteboard"},
                },
                "required": ["kind", "item_id"],
            },
            _delete_board_item,
            destructive=True,
        ),
        ToolSpec(
            "restore_board_item",
            "Put back a board item delete_board_item took off: pass the item "
            "text its undo gave. Only for undoing a delete.",
            {
                "type": "object",
                "properties": {"item": {"type": "string", "description": "The undo's item text"}},
                "required": ["item"],
            },
            _restore_board_item,
        ),
        ToolSpec(
            "add_board_shape",
            "Draw a rectangle, ellipse or diamond with words in it, or a frame "
            "(a titled region), on a board at x, y with a width and height.",
            {
                "type": "object",
                "properties": {
                    "board_id": {"type": "integer", "description": "The board's id; omit for the default board"},
                    "shape": {"type": "string", "description": "'rect', 'ellipse', 'diamond' or 'frame'"},
                    "x": {"type": "number"},
                    "y": {"type": "number"},
                    "width": {"type": "number"},
                    "height": {"type": "number"},
                    "text": {"type": "string", "description": "Words in the shape, or the frame's title"},
                    "color": {"type": "string", "description": "Line colour, like #335599 (optional)"},
                    "fill": {"type": "string", "description": "Fill colour (optional)"},
                },
                "required": ["shape"],
            },
            _add_board_shape,
        ),
        ToolSpec(
            "list_library",
            "Find shapes, flowchart symbols, arrows, frames (Kanban, SWOT, "
            "retrospective), icons and the person's saved items in the board "
            "library by a word; each has a ref for place_library_item.",
            {
                "type": "object",
                "properties": {
                    "query": {"type": "string", "description": "A word, like decision, kanban or star"},
                    "limit": {"type": "integer", "description": "How many (default 12, at most 30)"},
                },
            },
            _list_library,
        ),
        ToolSpec(
            "place_library_item",
            "Place a library item (a ref from list_library) on a board, centred "
            "at x, y. It becomes an ordinary copy on the board.",
            {
                "type": "object",
                "properties": {
                    "ref": {"type": "string", "description": "From list_library, like builtin:flowchart/decision"},
                    "board_id": {"type": "integer", "description": "The board's id; omit for the default board"},
                    "x": {"type": "number"},
                    "y": {"type": "number"},
                },
                "required": ["ref"],
            },
            _place_library_item,
        ),
        ToolSpec(
            "search_chat_history",
            "Search earlier conversations with the user, from other days too. Use it when "
            "they mention something 'we talked about' that is not in this thread.",
            {
                "type": "object",
                "properties": {
                    "query": {
                        "type": "string",
                        "description": "Words to look for (leave empty for the most recent chats)",
                    },
                    "limit": {"type": "integer", "description": "How many chats"},
                },
            },
            _search_chat_history,
        ),
        ToolSpec(
            "list_skills",
            #: And the tools (O10, BACKLOG "A tool to list the tools, and the
            #: skills"): folded in here, not a tool of its own, because every
            #: schema must fit a 32k window untrimmed and a new tool tipped it.
            "List the user's saved skills: repeatable jobs you can start "
            "with run_skill. Each says when_to_use and whether it changes "
            "notes. tools:true lists your tools; tool: one's details.",
            {"type": "object", "properties": {"tools": {"type": "boolean"}, "tool": {"type": "string"}}},
            _list_skills,
        ),
        ToolSpec(
            "run_skill",
            # Terse for the same reason ask_user is: this is offered whenever
            # skills are in play. The two facts that stop it being misused, 
            # the turn ends, and a skill is not a substitute for doing the
            # thing: are worth their characters; nothing else here is.
            "Start one of the user's saved skills, by name from list_skills. "
            "Your turn ENDS and the run takes over, step by step. Use it for "
            "a job a skill already describes, not for a one-off you can just "
            "do.",
            {
                "type": "object",
                "properties": {
                    "name": {
                        "type": "string",
                        "description": "The skill's name, exactly as list_skills gave it",
                    },
                    "inputs": {
                        "type": "object",
                        "description": "Values for the skill's declared inputs, by name",
                    },
                },
                "required": ["name"],
            },
            _run_skill,
            ends_turn=True,
        ),
        ToolSpec(
            "make_plan",
            # Terse on purpose: this is in CORE_TOOLS, so every turn pays for
            # it. The two facts that make it work are the trigger ("a job with
            # several parts") and the consequence (the turn ends and the steps
            # run one at a time). Everything else is in the validator's errors,
            # which only cost characters when the model gets it wrong.
            "Plan a job that has several parts, as 2-6 short steps. Your turn "
            "ENDS and the steps then run one at a time, so nothing gets "
            "half-done. Use it when one instruction covers many notes.",
            {
                "type": "object",
                "properties": {
                    "goal": {
                        "type": "string",
                        "description": "The whole job in one sentence",
                    },
                    "steps": {
                        "type": "array",
                        "items": {"type": "string"},
                        "description": "2-6 steps, each one action, in order",
                    },
                },
                "required": ["goal", "steps"],
            },
            _make_plan,
            ends_turn=True,
        ),
        ToolSpec(
            "compress_chat",
            # Offered by cue, not in CORE_TOOLS (§34's "the registry should
            # stop growing", this only needs to be on the wire for the rare
            # turn that's actually about the chat getting long).
            "Summarise the older part of this chat to free context. Your turn ENDS: the user "
            "edits the summary first. Only when asked to shorten the chat, not to summarise notes.",
            {"type": "object", "properties": {}},
            _compress_chat,
            ends_turn=True,
        ),
        ToolSpec(
            "save_skill",
            "Create a saved skill, or update one by using the same name. A "
            "skill is a job the user runs with one click: what to do, the "
            "steps, and the tools it needs.",
            {
                "type": "object",
                "properties": {
                    "name": {"type": "string", "description": "Short name, up to 40 characters"},
                    "prompt": {
                        "type": "string",
                        "description": "What the skill should do, in one instruction",
                    },
                    "steps": {
                        "type": "array",
                        "items": {"type": "string"},
                        "description": "The steps to follow, in order",
                    },
                    "tools": {
                        "type": "array",
                        "items": {"type": "string"},
                        "description": "Names of the tools the skill needs, e.g. tag_note",
                    },
                    "when_to_use": {
                        "type": "string",
                        "description": "When this skill applies, so it can be found later",
                    },
                    #: **The postcondition, on the wire** (CHAT_PLAN decision
                    #: 10b). It was readable and writable through `normalise`
                    #: and offered nowhere, so only the built-ins had one. Flat
                    #: fields rather than a nested object, because a 3B model
                    #: writing a skill gets a three-field shape right far more
                    #: often than a shape inside a shape, and this is the tool
                    #: the "Build a skill" skill drives.
                    "verify_tool": {
                        "type": "string",
                        "description": "Optional read-only counting tool, e.g. "
                        "count_notes, to check the skill worked",
                    },
                    "verify_expect": {
                        "type": "string",
                        "description": "min, max, equals or unchanged",
                    },
                    "verify_value": {
                        "type": "integer",
                        "description": "The number to compare (not for unchanged)",
                    },
                    "verify_untagged": {
                        "type": "boolean",
                        "description": "Count only untagged notes (count_notes)",
                    },
                },
                "required": ["name", "prompt"],
            },
            _save_skill,
        ),
        ToolSpec(
            "delete_skill",
            "Delete one of the user's saved skills. The app asks the user to "
            "confirm before this runs.",
            {
                "type": "object",
                "properties": {"name": {"type": "string"}},
                "required": ["name"],
            },
            _delete_skill,
            destructive=True,
        ),
        ToolSpec(
            "search_help",
            #: Short on purpose: every tool's schema must fit a 32k window
            #: untrimmed (tests/test_prompt_budget.py), and this one tipped it.
            "How a Tessellate feature or setting works, from its guide.",
            {
                "type": "object",
                "properties": {"query": {"type": "string"}},
                "required": ["query"],
            },
            _search_help,
        ),
        ToolSpec(
            "get_current_time",
            "The date and time now, here or in a named place; for "
            "time-aware answers and reminder times.",
            {"type": "object", "properties": {"place": {"type": "string"}}},
            _get_current_time,
        ),
        ToolSpec(
            "calculate",
            "Work out a sum, percentage, unit or currency conversion, or count "
            "of days, as the app does. Use it for every number; say the result "
            "and how it was read.",
            {"type": "object", "properties": {"question": {"type": "string", "description": "e.g. 15% of 240, 5 km in miles, days until 25 December"}},
             "required": ["question"]},
            _calculate,
        ),
        ToolSpec(
            "read_text",
            "The dates, times, durations, amounts and units in a text exactly as the app "
            "reads them, each with how it was read. Use it rather than working out a date "
            "yourself.",
            {"type": "object", "properties": {"text": {"type": "string"}}, "required": ["text"]},
            _read_text,
        ),
        ToolSpec(
            "check_answer",
            "Check a draft answer against the text it came from: lists any "
            "number or name in the answer the sources do not contain.",
            {"type": "object", "properties": {"answer": {"type": "string"},
                                              "sources": {"type": "array", "items": {"type": "string"}}},
             "required": ["answer", "sources"]},
            _check_answer,
        ),
        ToolSpec(
            "propose_act",
            "Propose one change in the user's words (\"remind me to call Sam on "
            "Friday at 9\", \"pin the dentist note\"): the app shows a card and "
            "the user confirms. Use it when unsure a change is wanted; then stop.",
            {"type": "object", "properties": {"sentence": {"type": "string"}}, "required": ["sentence"]},
            _propose_act,
            ends_turn=True,
        ),
        ToolSpec(
            "summarize_notes",
            "Gather the user's recent notes (optionally from the last N days or a "
            "category) so you can summarise them. Read-only.",
            {
                "type": "object",
                "properties": {
                    "days": {
                        "type": "integer",
                        "description": "Only include notes from the last N days (optional)",
                    },
                    "category": {
                        "type": "string",
                        "description": "Only include this category (optional)",
                    },
                },
            },
            _summarize_notes,
        ),
        ToolSpec(
            "list_categories",
            "List every category with how many notes it holds.",
            {"type": "object", "properties": {}},
            _list_categories,
        ),
        ToolSpec(
            "create_note",
            "Save a new note for the user. Leave category empty to let the "
            "app file it automatically.",
            {
                "type": "object",
                "properties": {
                    "content": {"type": "string", "description": "The note text"},
                    "category": {"type": "string", "description": "Category (optional)"},
                    "tags": {"type": "array", "items": {"type": "string"}},
                },
                "required": ["content"],
            },
            _create_note,
        ),
        ToolSpec(
            "edit_note",
            "Change a note's text, category, or replace its whole tag list.",
            {
                "type": "object",
                "properties": {
                    "note_id": _NOTE_ID,
                    "content": {"type": "string", "description": "New text (optional)"},
                    "category": {"type": "string", "description": "New category (optional)"},
                    "tags": {
                        "type": "array",
                        "items": {"type": "string"},
                        "description": "Replacement tag list (optional)",
                    },
                },
                "required": ["note_id"],
            },
            _edit_note,
            # NOT destructive, and this was reconsidered rather than inherited.
            # It was flipped to `destructive=True` once, which sounds like the
            # safe direction and is not, for three reasons:
            #
            # - An edit is the one write here that is *fully* reversible. Every
            #   call captures `_undo_edit`, the exact call that restores the
            #   note: before it writes, and `entry_revisions` keeps the old
            #   text besides. A delete is not comparable, which is why that one
            #   stays destructive.
            # - Destructive tools park the turn for a confirmation, so an
            #   agent asked to tidy twenty notes stopped twenty times. The
            #   change list with an Undo on every row is the better answer to
            #   "the AI edited something I didn't want": it costs nothing when
            #   the edits were right, which is most of the time.
            # - It broke the background librarian outright. That run abandons
            #   itself on any `confirm` event, because there is nobody to ask, 
            #   so with this flag set, the first note it tried to edit ended
            #   the entire pass.
        ),
        ToolSpec(
            "tag_note",
            "Add and/or remove individual tags on one or multiple notes.",
            {
                "type": "object",
                "properties": {
                    "note_id": {"type": "integer", "description": "ID of a single note to tag"},
                    "note_ids": {
                        "type": "array",
                        "items": {"type": "integer"},
                        "description": "IDs of multiple notes to tag (optional)",
                    },
                    "add": {"type": "array", "items": {"type": "string"}, "description": "Tags to add"},
                    "remove": {"type": "array", "items": {"type": "string"}},
                },
                "required": [],
            },
            _tag_note,
        ),
        ToolSpec(
            "pin_note",
            # The tool keeps its name, renaming it would break every saved
            # skill and every plan that calls it, but the description is what
            # the model reads, and it now names the feature the user sees.
            # "Favourites" is a place in the sidebar; "floats to the top" is
            # the sort. The flag does both, so the sentence says both.
            "Add a note to Favourites (or remove it). Favourited notes appear "
            "under Favourites in the sidebar and float to the top of lists.",
            {
                "type": "object",
                "properties": {
                    "note_id": _NOTE_ID,
                    "pinned": {"type": "boolean", "description": "Leave out to pin; false only to unpin"},
                },
                "required": ["note_id"],
            },
            _pin_note,
        ),
        ToolSpec(
            "link_notes",
            "Connect a note to one or more related notes.",
            {
                "type": "object",
                "properties": {
                    "note_id": _NOTE_ID,
                    "other_note_id": {"type": "integer", "description": "ID of a single target note"},
                    "other_note_ids": {
                        "type": "array",
                        "items": {"type": "integer"},
                        "description": "IDs of multiple target notes to link to (optional)",
                    },
                    "reason": {
                        "type": "string",
                        "description": (
                            "Optional: why, in a few words ('both about scheduling'). Skip it"
                            " when obvious."
                        ),
                    },
                    "link_type": {
                        "type": "string",
                        "description": link_type_description(
                            {key: {} for key in LINK_TYPES}
                        ),
                    },
                },
                "required": ["note_id"],
            },
            _link_notes,
        ),
        ToolSpec(
            "find_similar_notes",
            "Notes that read like a given note: conceptual matches that may share no keywords"
            " or tags.",
            {
                "type": "object",
                "properties": {
                    "note_id": _NOTE_ID,
                },
                "required": ["note_id"],
            },
            _find_similar_notes,
        ),
        ToolSpec(
            "unlink_notes",
            "Remove a connection between two notes that shouldn't be linked. "
            "The notes themselves are untouched.",
            {
                "type": "object",
                "properties": {
                    "note_id": _NOTE_ID,
                    "other_note_id": {"type": "integer", "description": "The other note's id"},
                },
                "required": ["note_id", "other_note_id"],
            },
            _unlink_notes,
        ),
        ToolSpec(
            "delete_note",
            "Move a note to the recycle bin (recoverable). The app asks the "
            "user to confirm before this runs.",
            {"type": "object", "properties": {"note_id": _NOTE_ID}, "required": ["note_id"]},
            _delete_note,
            destructive=True,
        ),
        ToolSpec(
            "restore_note",
            "Bring a note back from the recycle bin.",
            {"type": "object", "properties": {"note_id": _NOTE_ID}, "required": ["note_id"]},
            _restore_note,
        ),
        ToolSpec(
            "set_reminder",
            #: **Say what `note_id` is for, not merely that it exists.** The
            #: link between a note and a reminder has been storable since
            #: reminders were written, and INBOX 309 is the owner reporting
            #: it as missing, because nothing on either side showed it. A
            #: reminder Atlas makes while reading a note is exactly the case
            #: the link is for, and "optionally attached to a note" does not
            #: tell a small model that.
            "Create a reminder; put when in the user's own words. If it comes out of a note you "
            "have just read, pass that note's id so the two stay joined.",
            {
                "type": "object",
                "properties": {
                    "text": {"type": "string", "description": "What to remind about"},
                    "when": {
                        "type": "string",
                        "description": "The user's words, e.g. 'tomorrow 9am', 'in 20 minutes'",
                    },
                    "due_at": {"type": "string", "description": "An exact ISO date-time, only if you have one"},
                    "note_id": {"type": "integer", "description": "The note this reminder came out of, if any"},
                    "priority": {"type": "string", "enum": ["low", "normal", "high"], "description": "Defaults to normal"},
                    "recurring": {"type": "string", "enum": ["none", "daily", "weekly", "monthly"]},
                },
                "required": ["text"],
            },
            _set_reminder,
        ),
        ToolSpec(
            "list_reminders",
            "List the user's reminders, soonest first.",
            {
                "type": "object",
                "properties": {
                    "include_done": {"type": "boolean", "description": "Include finished ones"}
                },
            },
            _list_reminders,
        ),
        ToolSpec(
            "complete_reminder",
            "Mark a reminder done (or not done).",
            {
                "type": "object",
                "properties": {
                    "reminder_id": {"type": "integer"},
                    "done": {"type": "boolean", "description": "false to reopen"},
                },
                "required": ["reminder_id"],
            },
            _complete_reminder,
        ),
        ToolSpec(
            "rename_tag",
            "Rename a tag everywhere it's used (merges if the new name exists).",
            {
                "type": "object",
                "properties": {"old": {"type": "string"}, "new": {"type": "string"}},
                "required": ["old", "new"],
            },
            _rename_tag,
        ),
        # Written terse on purpose. Every character of these four schemas is
        # resent on every round in "all tools" mode, and the registry was
        # already within ~100 characters of what a 4096-token window can hold
        # (tests/test_prompt_budget.py). The per-parameter descriptions the
        # other tools carry are the first thing to go: "old"/"new" and
        # "from"/"into" do not need explaining.
        ToolSpec(
            "create_category",
            "Make a new category. Use before filing a note under a category "
            "that doesn't exist yet.",
            {
                "type": "object",
                "properties": {"name": {"type": "string"}},
                "required": ["name"],
            },
            _create_category,
        ),
        ToolSpec(
            "rename_category",
            "Rename a category; merges if the new name is already taken.",
            {
                "type": "object",
                "properties": {"old": {"type": "string"}, "new": {"type": "string"}},
                "required": ["old", "new"],
            },
            _rename_category,
        ),
        ToolSpec(
            "merge_categories",
            "Move every note from one category into another and remove the "
            "empty one. Tidies duplicates like 'Work' and 'work'.",
            {
                "type": "object",
                "properties": {"from": {"type": "string"}, "into": {"type": "string"}},
                "required": ["from", "into"],
            },
            _merge_categories,
            destructive=True,
        ),
        ToolSpec(
            "delete_category",
            "Remove a category. Its notes are kept, as Uncategorised.",
            {
                "type": "object",
                "properties": {"name": {"type": "string"}},
                "required": ["name"],
            },
            _delete_category,
            destructive=True,
        ),
        ToolSpec(
            "move_notes",
            "Move notes into a category or a space. The app asks first.",
            {
                "type": "object",
                "properties": {
                    "ids": {"type": "array", "items": {"type": "integer"}},
                    "category": {"type": "string"},
                    "space": {"type": "string"},
                },
                "required": ["ids"],
            },
            _move_notes,
            destructive=True,
        ),
        ToolSpec(
            "web_search",
            "Search the internet (DuckDuckGo) for current information the "
            "notebook doesn't have. Only available when the user enabled "
            "web search in their preferences.",
            {
                "type": "object",
                "properties": {"query": {"type": "string"}},
                "required": ["query"],
            },
            _web_search,
        ),
        ToolSpec(
            "read_url",
            "Open a web page and read its text. Use this whenever the user "
            "gives you a link, or after web_search when a result looks like it "
            "holds the answer: a search snippet is rarely enough. Only "
            "available when the user enabled web search.",
            {
                "type": "object",
                "properties": {
                    "url": {"type": "string", "description": "The full http(s) URL"}
                },
                "required": ["url"],
            },
            _read_url,
        ),
        ToolSpec(
            "delete_tag",
            "Remove a tag from every note. The app asks the user to confirm "
            "before this runs.",
            {
                "type": "object",
                "properties": {"name": {"type": "string"}},
                "required": ["name"],
            },
            _delete_tag,
            destructive=True,
        ),
    ]
}


#: Stand-in values for a worked example, by JSON-schema type. Chosen to look
#: obviously like placeholders rather than like an answer: a model shown
#: `{"note_id": 0}` has copied a real-looking id, while `12` next to the
#: sentence below reads as "put yours here".
_EXAMPLE_VALUES: dict[str, object] = {
    "integer": 12,
    "number": 12,
    "string": "…",
    "boolean": True,
    "object": {},
}

#: How many arguments one example shows. Enough to demonstrate the shape (a
#: link needs both ends of it to read as a link), few enough that the line
#: stays one line. A tool that *requires* more than this shows all of them, 
#: an example missing a required argument teaches the wrong call.
EXAMPLE_ARG_LIMIT = 3


def call_example(name: str) -> str:
    """One line showing the shape of a call to `name`, or "" if there is no
    such tool.

    **Generic, and deliberately not a hand-written example per tool.** Built
    from the same JSON schema that goes on the wire, so a tool whose arguments
    change cannot leave a stale example behind it, the failure mode of a
    hand-maintained table, and one nothing would catch. Phase B of the skills
    reform: *"a worked example in the prompt, per step, showing the exact call
    shape. Small models copy structure far more reliably than they follow
    description."*
    """
    spec = TOOLS.get(name)
    if spec is None:
        return ""
    schema = spec.parameters if isinstance(spec.parameters, dict) else {}
    properties = schema.get("properties") or {}
    required = [key for key in (schema.get("required") or []) if key in properties]
    wanted = list(required)
    for key in properties:
        if len(wanted) >= EXAMPLE_ARG_LIMIT:
            break
        if key in wanted or _is_plural_variant(key, wanted):
            continue
        wanted.append(key)
    arguments = {key: _example_value(properties.get(key) or {}) for key in wanted}
    return (
        f"A call to {name} looks like this, same shape, your own values: "
        f"{name}({json.dumps(arguments, ensure_ascii=False)})"
    )


def _is_plural_variant(key: str, chosen: list[str]) -> bool:
    """Is `key` the many-at-once form of an argument already in the example?

    Several tools here take `note_id` **or** `note_ids`, `other_note_id` **or**
    `other_note_ids`, alternatives, never both. Showing both in one worked
    example is worse than showing neither: a small model copying the shape
    sends both and gets an argument error on a call it was explicitly taught.
    A name rule rather than a per-tool table, so a tool added later is covered
    without anyone remembering to add it.
    """
    for other in chosen:
        if key == f"{other}s" or other == f"{key}s":
            return True
        if key.endswith("_ids") and other == f"{key[:-4]}_id":
            return True
        if other.endswith("_ids") and key == f"{other[:-4]}_id":
            return True
    return False


def _example_value(field: dict):
    """A placeholder of the right JSON type for one schema property."""
    kind = str(field.get("type") or "string")
    if kind == "array":
        item = field.get("items") or {}
        return [_example_value(item)] if isinstance(item, dict) else ["…"]
    enum = field.get("enum")
    if isinstance(enum, list) and enum:
        return enum[0]
    return _EXAMPLE_VALUES.get(kind, "…")
