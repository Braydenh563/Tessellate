"""Which tools write, change, add or are always offered; the groups and the words that ask for them; the Settings switch.

Moved whole from `__init__.py` (audit AR3, gods-2): the code is unchanged, and
`__init__` re-exports every name here that anything reads. Imports run one way,
down the layer list in `__init__.py`'s docstring, never back to `__init__`.
"""

from __future__ import annotations

from tessellate.core import deps
from tessellate.ai import personal, toolwords
from tessellate.ai.provider import set_write_tools

# The tools that change something. Used by the agent's "you claimed you saved
# it but never called a write tool" safety net, and by the skill list to say
# which skills act rather than answer, one list, so the two can't disagree.
WRITE_TOOLS = {
    "audit_link_reasons",
    "check_learned",
    "create_note",
    "edit_note",
    "tag_note",
    "pin_note",
    "link_notes",
    "unlink_notes",
    # `find_similar_notes` is NOT here, though it was added to this set once.
    # It only reads. Listing a read here has three consequences, all wrong: the
    # agent's "you claimed you saved it" net counts the turn as having written
    # something, skills that only search get labelled as acting, and, the
    # expensive one: the write branch in `run_agent` clears `fresh_reads`, so
    # a single call to it re-opens every already-answered read for repetition.
    "delete_note",
    "restore_note",
    "set_reminder",
    "complete_reminder",
    "rename_tag",
    "delete_tag",
    "save_skill",
    "delete_skill",
    "create_document",
    "delete_document",
    "add_whiteboard_card",
    "add_whiteboard_link",
    "generate_diagram",
    "create_mindmap",
    "map_from_note",
    "add_map_node",
    "link_map_nodes",
    "move_board_item",
    "edit_board_item",
    "delete_board_item",
    "restore_board_item",
    "add_board_shape",
    "place_library_item",
    # The category tools write too (INBOX 431 (e)): left out, a turn that
    # merged two categories counted as having written nothing, so the
    # claimed-a-save net could fire on it, and a skill that only tidied
    # categories was labelled as answering rather than acting.
    "create_category",
    "rename_category",
    "merge_categories",
    "delete_category",
    "move_notes",
}
set_write_tools(WRITE_TOOLS)

#: **Writes are in one of three classes** (audit 1029 H2; table in
#: `docs/roadmap/agent-remaining/audit-1029-harness.md`). The Agent tip says it
#: asks before it changes or removes something, so the gate is in code:
#:
#: - destructive (`ToolSpec.destructive`): removes content; always parks.
#: - CHANGE_TOOLS: overwrites or detaches what the person already wrote;
#:   parks the same way, so a Confirm card names it before it happens.
#: - ADD_TOOLS: only adds (or flips state with an Undo); runs, and its result
#:   card carries the Undo. `tag_note` is here, but `remove` makes it a change
#:   (`needs_confirm`).
#:
#: `tests/test_write_gate_h2.py` fails when a write tool is in none of them.
CHANGE_TOOLS = frozenset({
    "check_learned",
    "edit_note",
    "unlink_notes",
    "rename_tag",
    "rename_category",
    "save_skill",
    "audit_link_reasons",
})
ADD_TOOLS = frozenset({
    "create_note",
    "tag_note",
    "pin_note",
    "link_notes",
    "restore_note",
    "set_reminder",
    "complete_reminder",
    "create_document",
    "add_whiteboard_card",
    "add_whiteboard_link",
    "generate_diagram",
    "create_mindmap",
    "map_from_note",
    "add_map_node",
    "link_map_nodes",
    "restore_board_item",
    "add_board_shape",
    "place_library_item",
    "create_category",
})


# --- which tools a turn is offered (roadmap §11a) --------------------------------
#
# All 26 schemas went up on every round of every turn, whether the question was
# "how many notes do I have" or "remind me to call mum", 10,215 characters,
# 77% of the fixed per-round overhead, resent up to MAX_ROUNDS times. On a
# model with a 4096-token window that is most of the room, and the overflow is
# dropped from the front, which is the system prompt: the model stops knowing
# it has tools at all and reports as "the AI won't use tools".
#
# A skill declares what it needs, so its run is easy (see ai/skills.py). An
# ordinary turn declares nothing, so this reads the question. The rule that
# keeps it honest: **narrow only when we are confident, and widen when we are
# not.** A question gets the reading core; a request that names something gets
# that group as well; anything that sounds like a job but doesn't say which
# one gets everything. Losing a tool the turn needed is worse than paying for
# schemas it didn't.

# Always offered: reading the notebook, knowing the time, and saving a note, 
# the last because "save this" is the most common action there is, and the
# cost of missing it is the model claiming a save that never happened.
CORE_TOOLS = [
    # Always offered, and it is the one addition to this list that is not about
    # notes: a request can be ambiguous whatever it is about, so a cue-based
    # rule has nothing to match on. Kept cheap, the schema is four lines , 
    # because the alternative is the model guessing which note you meant (§33).
    "ask_user",
    # Always offered for the same reason and with the same shape of cost: any
    # request can turn out to have several parts, and no keyword says so, "fix
    # my categories" reads exactly like a one-step instruction. Without it on
    # the turn where the model realises the job is big, the model's only move
    # is to do the first part and stop, which is the reported failure (§35K).
    "make_plan",
    "search_notes",
    "get_note",
    "list_notes",
    "count_notes",
    "list_categories",
    "list_tags",
    "notebook_overview",
    "get_current_time",
    "create_note",
    "save_user_preference",
]

# Groups, and the words that ask for them. Generous on purpose: a cue that
# fires when it needn't costs a few hundred characters, and one that fails to
# fire costs the user the thing they asked for.
TOOL_GROUPS: list[tuple[tuple[str, ...], tuple[str, ...]]] = [
    #: The app's own guide, for a question about Tessellate rather than the
    #: notes (2026-10-10 triage, decision 4: it found the right help entry for
    #: eight of ten sample questions). A group, not a core tool: most turns
    #: are about the notes, and a core tool's schema is paid on every round.
    (
        ("search_help",),
        (
            "how do i", "how to", "where is", "where do i", "where are", "setting",
            "feature", "button", "shortcut", "the app", "memorymap", "this app",
        ),
    ),
    (
        #: The app's own working (CHAT_PLAN section 2, the agent row): a small
        #: model asked for a number is handed the tool that works it out.
        ("calculate", "read_text", "check_answer"),
        (
            "calculate", "work out", "how many", "how much", "percent", "%", "convert",
            "total", "add up", "average", "days until", "days since", "how long until",
            "what date", "which day", "sum of", "times", "divided",
        ),
    ),
    (
        ("set_reminder", "list_reminders", "complete_reminder", "propose_act"),
        (
            "remind", "reminder", "forget", "due", "deadline", "tomorrow",
            "tonight", "later", "schedule", "chase", "follow up", "o'clock",
            "next week", "on monday", "on tuesday", "on wednesday",
            "on thursday", "on friday", "on saturday", "on sunday", "alarm",
        ),
    ),
    (
        ("tag_note", "rename_tag", "delete_tag", "propose_act"),
        ("tag", "label", "untagged", "retag", "categorise", "categorize"),
    ),
    (
        # Kept apart from the tag group even though "categorise" cues both:
        # tagging a note and reorganising the category tree are different
        # jobs, and sending four category schemas to every "tag this" question
        # is exactly the per-round cost §11a went to some trouble to cut.
        ("create_category", "rename_category", "merge_categories", "delete_category", "move_notes"),
        (
            # "file … under" is split into its two halves deliberately: the
            # first draft matched "file it under" and missed "file this under",
            # which is the same request with a different pronoun.
            "category", "categories", "folder", "file ", "filed ", "under",
            "reorganise", "reorganize", "duplicate categor", "merge", "rename",
            "move ", "send ", "space",
        ),
    ),
    (
        (
            "link_notes",
            "unlink_notes",
            "related_notes",
            "path_between",
            "notebook_structure",
            #: **Also found unreachable by the eval harness.** `find_similar_notes`
            #: appeared in no group either, so "what reads like my thesis note?"
            #: was offered every connection tool except the one that answers it.
            #: It belongs here rather than in a group of its own: it is the same
            #: question as `related_notes` asked of similarity instead of links,
            #: and a question about one is a question about the other.
            "find_similar_notes",
        ),
        (
            "link", "connect", "related", "relate", "join", "graph", "together",
            # …and the words for a connection nobody has made yet, which is
            # what `find_similar_notes` is for.
            "similar", "similarly", "reads like", "looks like", "same sort of",
            "same kind of",
            # What the notebook's shape gets called when somebody asks about
            # it. "orphan" and "cluster" are the words the answer uses, so they
            # are also the words the next question uses.
            "structure", "shape", "cluster", "orphan", "unconnected",
            "disconnected", "isolated", "web", "map of",
            # "how are these two related" and its phrasings. `path_between` is
            # cued by the group rather than by a slot in CORE_TOOLS on purpose
            # (§34 on a registry that should stop growing): a question about two
            # notes always says one of these words, so the schema is only ever
            # paid for on a turn that is already about connections.
            "between", "path", "route", "how are", "what links",
            # The words people use when a connection is WRONG rather than
            # missing. Without them "unlink these" offered no way to do it.
            "unlink", "disconnect", "detach", "separate", "unrelated",
        ),
    ),
    (
        ("edit_note", "pin_note"),
        (
            "edit", "change", "update", "rewrite", "fix", "correct", "amend",
            "append",
            "pin", "unpin", "reword", "shorten", "expand",
            # Filing one note is `edit_note`'s `category`, not a category
            # tool (H4, Qwen2.5-3B): "File the dentist note under Health" was
            # offered only the category tree's four tools and called
            # `count_notes`, the one thing on offer that seemed near it.
            "file ", "filed ", "move ",
        ),
    ),
    (
        ("delete_note", "restore_note"),
        ("delete", "remove", "bin", "trash", "restore", "undelete", "recycle"),
    ),
    (
        ("list_documents", "get_document", "create_document"),
        (
            "document", "doc ", "docs", "write-up", "essay", "report", "chapter",
            # The words that mean "make me one", which cued nothing before
            # `create_document` existed to be cued.
            "write up", "draft", "compose", "long-form",
        ),
    ),
    (
        ("search_chat_history",),
        (
            "we talked", "we discussed", "you said", "earlier", "last time",
            "previous", "conversation", "chat about", "mentioned before",
        ),
    ),
    (
        ("list_skills", "run_skill", "save_skill", "delete_skill"),
        ("skill", "shortcut", "what can you do", "your tools", "which tool", "what tools", "list the tools", "capabilities"),
    ),
    (
        ("summarize_notes",),
        ("summarise", "summarize", "summary", "recap", "overview", "gist"),
    ),
    (
        ("compress_chat",),
        (
            # About the CONVERSATION getting long, not about summarising
            # notes: "summarise my notes" must not offer this, so it shares
            # no words with the summarize_notes group above.
            "compress the chat", "compress this chat", "compress our chat",
            "compress the conversation", "condense the chat",
            "condense this conversation", "shorten the chat",
            "shorten this conversation", "running out of context",
            "context window",
        ),
    ),
    (
        (
            "read_whiteboard", "search_whiteboard", "add_whiteboard_card",
            "add_whiteboard_link", "generate_diagram",
            # Same group and the same cues: "mind map" already fires this
            # one, and a question about a map that was offered the board
            # tools and not the map tools is the worst of both, the model
            # answers by placing cards on a canvas instead.
            "read_mindmap", "create_mindmap", "map_from_note", "add_map_node", "link_map_nodes",
            "move_board_item", "edit_board_item", "delete_board_item", "add_board_shape",
            "list_library", "place_library_item",
        ),
        (
            "whiteboard", "board", "canvas", "diagram", "mind map", "mindmap",
            "mind-map", "sketch", "draw.io", "drawio", "flowchart",
        ),
    ),
    (
        #: **The uploaded-files group, and it had none at all.**
        #:
        #: Found by the eval harness on its first run (`tests/eval`, PLAN.md
        #: §4 A6): three golden asks: "find the photo of the whiteboard",
        #: "which file mentions the retention plan?", "read the whiteboard
        #: photo for me", were each offered a narrowed toolbox with neither
        #: `search_files` nor `read_file` in it. Neither tool appeared in any
        #: group, and `focus_for` only returns `None` (everything) for a broad
        #: request or a follow-through, so on an ordinary question about a
        #: file these two could not be called *at all*. The tools worked; they
        #: were unreachable, which is CLAUDE.md's "features that never ran
        #: once" one layer up from the code.
        #:
        #: The cues deliberately avoid `"file "` and `"filed "`, those belong
        #: to the category group above ("file it under Work"), and taking them
        #: would break filing to fix reading. `"which file"`/`"that file"`/
        #: `"the file"` are the phrasings that mean an actual file, and they
        #: cue both groups, which is fine: two small groups on the wire beats
        #: the right one missing.
        ("search_files", "read_file"),
        (
            "upload", "uploaded", "pdf", "photo", "photos", "picture",
            "image", "screenshot", "scan", "scanned", "attachment",
            "attached", "files", "which file", "that file", "the file",
            "my file", "a file", "ocr",
        ),
    ),
]


def web_barred(question: str) -> set[str]:
    """The web tools a first-person question must not be offered: "who is my
    sister" is in the notes, and a model holding `web_search` sends it out
    (audit 1030 A3). An explicit "search the web for" keeps them."""
    if personal.about_own_record(question or "") and not toolwords.asks_web(question or ""):
        return {"web_search", "read_url"}
    return set()


def tool_enabled(name: str) -> bool:
    """A tool is offered unless the user turned it off in Settings, Tools.
    web_search additionally requires the online opt-in."""
    # Listing the tools must not start the app: without settings the defaults
    # hold (web off, nothing disabled), which is what a fresh notebook has.
    config = deps.peek_config()
    web_on = config.get_preference("web_search_enabled", False) if config else False
    if name in ("web_search", "read_url") and not web_on:
        return False
    disabled = config.get_preference("disabled_tools", []) if config else []
    return name not in set(disabled)
