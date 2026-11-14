"""Running a call: confirm labels, coercing and checking arguments, and `execute_tool`.

Moved whole from `__init__.py` (audit AR3, gods-2): the code is unchanged, and
`__init__` re-exports every name here that anything reads. Imports run one way,
down the layer list in `__init__.py`'s docstring, never back to `__init__`.
"""

from __future__ import annotations

import json
import logging
import re
import tessellate.ai.tools._common as _common
import tessellate.ai.tools.contracts as contracts
import tessellate.ai.tools.verify as verify
from tessellate.ai.tools.tool_coerce import _coerce, _describe_param

from sqlalchemy.orm import Session
from tessellate.core import activity, deps, events
from tessellate.entry import manager
from tessellate.core.logbuffer import safe_value
from tessellate.ai.tools.tool_table import TOOLS
from tessellate.ai.tools.tool_sets import WRITE_TOOLS, tool_enabled
from tessellate.ai.tools.tool_read import _named

def _confirm_move_notes(arguments: dict) -> str:
    count = len(arguments.get("ids") or [])
    where = f"the category “{arguments['category']}”" if arguments.get("category") else f"the space “{arguments.get('space', '?')}”"
    return f"Move {count} note{'' if count == 1 else 's'} to {where}"


#: The sentence on the confirm button for each tool that parks for a yes:
#: what will happen, not the tool's name. Includes the writes and reaches-out
#: that park once a turn has read text from outside (SEC-02).
_CONFIRM_LABELS = {
    "delete_note": lambda a: f"Move note #{a.get('note_id', '?')} to the recycle bin",
    "delete_tag": lambda a: f"Remove the tag “{a.get('name', '?')}” from every note",
    "move_notes": _confirm_move_notes,
    "delete_skill": lambda a: f"Delete the saved skill “{a.get('name', '?')}”",
    "move_board_item": lambda a: f"Move {a.get('kind', 'item')} #{a.get('item_id', '?')} on the board",
    "edit_board_item": lambda a: f"Change {a.get('kind', 'item')} #{a.get('item_id', '?')} on the board",
    "delete_board_item": lambda a: f"Take {a.get('kind', 'item')} #{a.get('item_id', '?')} off the board",
    "edit_note": lambda a: f"Change note #{a.get('note_id', '?')}",
    "create_note": lambda a: "Make a new note",
    "save_skill": lambda a: f"Save the skill “{a.get('name', '?')}”",
    "set_reminder": lambda a: "Set a repeating reminder" if str(a.get("recurring") or "none").lower() in ("daily", "weekly", "monthly") else "Set a reminder",
    "read_url": lambda a: f"Open {a.get('url', 'a web page')}",
    "web_search": lambda a: f"Search the web for “{a.get('query', '?')}”",
}


#: The confirm sentences that name one note, said with its title when the
#: note can be read (audit 1029 C47: "Move note #12 to the recycle bin").
_CONFIRM_NAMED = {
    "delete_note": "Move {note} to the recycle bin",
    "edit_note": "Change {note}",
}


def confirm_label(name: str, arguments: dict, session: Session | None = None) -> str:
    """Human sentence for the UI's confirm button (destructive tools)."""
    if session is not None and name in _CONFIRM_NAMED:
        try:
            note = _named(_common._require_note(session, arguments))
        #: AttributeError: a session that cannot look notes up (a stub) gets
        #: the plain label; a label never stops the call.
        except (_common.ToolError, KeyError, TypeError, ValueError, AttributeError):
            note = None
        if note:
            return _CONFIRM_NAMED[name].format(note=note)
    label = _CONFIRM_LABELS.get(name)
    if label:
        return label(arguments)
    words = name.replace("_", " ")
    return f"{words[:1].upper()}{words[1:]}"


def _ai_actor(name: str, model: str | None) -> str:
    """`ai:<tool>@<model>`: the note's History says which model made a change
    (owner, 0.3.31: "which models tagged or modified them"). Cut to the
    column's 60 characters from the model's end, never the tool's."""
    actor = f"ai:{name}"
    if model:
        actor = f"{actor}@{model}"[:60]
    return actor


def _fold_key(key: str) -> str:
    """`noteId`, `Note-ID`, `note id` -> `note_id`."""
    spaced = re.sub(r"(?<=[a-z0-9])(?=[A-Z])", "_", str(key))
    return re.sub(r"[^a-z0-9]+", "_", spaced.lower()).strip("_")


def example_arguments(name: str) -> str:
    """One valid call's required arguments for `name`, as JSON: what a failed
    call is shown, so the retry copies a shape rather than parses a rule."""
    spec = TOOLS.get(name)
    if spec is None:
        return "{}"
    props = spec.parameters.get("properties") or {}
    samples = {"integer": 12, "number": 1, "boolean": True, "string": "...", "object": {}}
    example: dict = {}
    for key in spec.parameters.get("required") or []:
        schema = props.get(key) or {}
        if schema.get("enum"):
            example[key] = schema["enum"][0]
        elif schema.get("type") == "array":
            example[key] = [samples.get((schema.get("items") or {}).get("type"), "...")]
        else:
            example[key] = samples.get(schema.get("type"), "...")
    return json.dumps(example)


#: Names a model reaches for that no spelling rule reaches: Qwen2.5-1.5B
#: asked to tag a note looked for `tags` and, finding `add`, said it could
#: not tag (INBOX 527).
_PARAM_ALIASES = {"tags": "add", "tag": "add", "untag": "remove"}


def _schema_key(key: str, props: dict, given: dict) -> str:
    """The schema's own name for a key the model spelled its own way, or the
    key unchanged. `id` folds to the tool's one `*_id` parameter only."""
    if key in props:
        return key
    alias = _PARAM_ALIASES.get(_fold_key(key))
    if alias in props and alias not in given:
        return alias
    by_fold = {_fold_key(k): k for k in props}
    folded = _fold_key(key)
    target = by_fold.get(folded) or by_fold.get(f"{folded}s") or by_fold.get(folded[:-1] if folded.endswith("s") else "")
    ids = [k for k in props if k.endswith("_id")]
    if target is None and folded == "id" and len(ids) == 1:
        target = ids[0]
    return target if target and target not in given else key


def _coerce_in_place(args: dict, props: dict) -> list[str]:
    """Read each present value as its schema types it; the ones that will not read, named."""
    wrong = []
    for key, schema in props.items():
        if args.get(key) is None:
            continue
        coerced, ok = _coerce(args[key], schema)
        if ok:
            args[key] = coerced
        else:
            shown = json.dumps(args[key], default=str)[:40]
            wrong.append(f"{_describe_param(key, schema)} not {shown}")
    return wrong


def check_arguments(name: str, arguments: dict) -> tuple[dict, str | None]:
    """(the arguments in the schema's names and types, None), or (them, the
    one-line reason they cannot run), before any handler sees them (INBOX 527).

    Measured before: 20 of 31 tools with a required parameter answered a
    missing one with "the arguments were missing something", naming nothing,
    and `get_note {"id": 1}` failed outright. Now a spelling is folded
    (`noteId`, `id` for the one id parameter, `tag` for `tags`), a value is
    read as its schema types it ("12", "false", one tag for a list, an enum in
    any case), and every missing required parameter is named with its type
    and an example call. A key the schema does not name is kept: a few
    handlers read internal ones.
    """
    spec = TOOLS.get(name)
    if spec is None or not isinstance(arguments, dict):
        return dict(arguments or {}), None
    props = spec.parameters.get("properties") or {}
    args = {_schema_key(key, props, arguments): value for key, value in arguments.items()}
    wrong = _coerce_in_place(args, props)
    missing = [
        _describe_param(key, props.get(key) or {})
        for key in spec.parameters.get("required") or []
        if args.get(key) in (None, "", [])
    ]
    problems = (["missing " + ", ".join(missing)] if missing else []) + (
        ["wrong type: " + "; ".join(wrong)] if wrong else []
    )
    if not problems:
        return args, None
    return args, f"{name}: {'; '.join(problems)}. Example: {example_arguments(name)}"


def execute_tool(
    session: Session,
    name: str,
    arguments: dict,
    context_tokens: int | None = None,
    model: str | None = None,
    agent: str | None = None,
) -> dict:
    """Run one tool call. Errors come back as {"error": ...} so the
    agent loop can hand them to the model instead of crashing.

    `agent` names an outside caller (the MCP server's client, H4); without
    it, a call made inside a request that named one (`events.as_agent`) is
    that agent's. Either way its writes are filed as `agent:<tool>@<who>`,
    not as Atlas's.

    Only `_common.ToolError` text is passed on, see that class. A `KeyError`, a
    `TypeError`, or a plain `ValueError` from inside a handler is something
    else: a missing argument the model didn't send, or a genuine bug. Its text
    is an internal detail, a key name, a function signature, sometimes a
    fragment of a row, so it goes to the log, and the caller gets a
    description of the *shape* of the problem, which is all a retry needs.
    """
    spec = TOOLS.get(name)
    if spec is None:
        return {"error": f"Unknown tool '{name}'"}
    deps.get_config()  # a call runs inside the app: the user's settings, never the defaults
    if not tool_enabled(name):
        return {"error": f"The '{name}' tool is turned off in Settings, Tools it can use"}
    #: Stop landed while the model call that chose this write was in flight:
    #: the write is discarded, not run late (the stream only sees Stop between
    #: yields, `activity.bind`). Reads are harmless and still run.
    if name in WRITE_TOOLS and activity.current_stopped():
        return {"error": "You stopped this run before this step ran, so nothing was changed."}
    args, problem = check_arguments(name, dict(arguments or {}))
    if problem:
        # Logged like a handler's argument failure, so Settings, Logs shows
        # what the model sent; the text is the app's own, safe to hand back.
        logging.getLogger("tessellate.tools").warning("tool %s refused: %s", safe_value(name, 40), safe_value(problem, 200))
        return {"error": problem}
    # WORLD_CLASS_PLAN B5: what must be true of the notebook first, checked
    # here rather than trusted to the model (`contracts.py` says which).
    problem = contracts.precondition(session, name, args)
    if problem:
        logging.getLogger("tessellate.tools").info("tool %s refused: %s", safe_value(name, 40), safe_value(problem, 200))
        return {"error": problem}
    try:
        if context_tokens is not None:
            args["__context_tokens__"] = context_tokens
        # Every write the handler makes, however deep in the managers it
        # happens, is recorded as this tool's doing (Brief 7). Set here, at
        # the one door every tool call comes through, rather than in each
        # handler: a handler that forgot would silently file the AI's edit
        # as something the user typed, which is the one question the event
        # log exists to answer.
        outside = _common.outside_seen()
        flag_token = outside.set([False])
        try:
            outsider = agent or events.current_agent()
            actor = events.agent_actor(name, outsider) if outsider else _ai_actor(name, model)
            with events.acting_as(actor):
                result = spec.handler(session, args)
            # SEC-02: the call put a clipped or imported note's words in front
            # of the model; the agent taints the turn on this, as for a web read.
            if outside.get()[0] and isinstance(result, dict) and "error" not in result:
                result["from_outside"] = True
        finally:
            outside.reset(flag_token)
    except _common.ToolError as exc:
        # An explanation the handler wrote on purpose, safe to hand back.
        session.rollback()
        return exc.result(name)
    except (KeyError, TypeError, ValueError) as exc:
        # A missing or wrong-typed argument, or a bug. Keep the detail here.
        session.rollback()
        logging.getLogger("tessellate.tools").warning(
            "tool %s failed on its arguments (%s)",
            safe_value(name, 40),
            type(exc).__name__,
            exc_info=True,
        )
        return {
            "error": (
                f"{name}: the arguments were missing something or were the "
                f"wrong type. Re-read the tool's schema and try once more."
            )
        }
    except Exception as exc:  # noqa: BLE001  # the backstop, not the rule
        # Anything else a handler can raise (a SQLAlchemy error, a filesystem
        # error, a bug the two branches above don't name) used to propagate
        # straight through: `agent.run_agent`'s tool loop has no try/except
        # of its own, so one bad call killed the whole SSE stream mid-turn,
        # with no rollback and no error the model or the user ever saw. A
        # tool failing is not supposed to be fatal to the turn; it is
        # supposed to be a result the model can read and try something else
        # with, the same as every other tool error here.
        session.rollback()
        logging.getLogger("tessellate.tools").error(
            "tool %s failed unexpectedly (%s)",
            safe_value(name, 40),
            type(exc).__name__,
            exc_info=True,
        )
        return {"error": f"{name}: something went wrong running this tool. Try a different approach."}
    # ...and what the call claimed, re-read from the rows. A label is not a
    # change: a claim that did not hold goes back as an error, so neither the
    # model nor the skill verifier reports it as done.
    if isinstance(result, dict) and "error" not in result:
        broken = verify.check(session, name, args, result)
        if broken:
            logging.getLogger("tessellate.tools").warning("tool %s: %s", safe_value(name, 40), safe_value(broken, 200))
            return {"error": broken}
    manager.log_action(
        session,
        "ai_tool",
        "chat",
        detail=f"{name} {json.dumps(arguments or {})[:200]}",
        actor=_ai_actor(name, model),
    )
    session.commit()
    return result
