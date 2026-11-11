"""Which tools a turn is offered: the confirm gate, follow-throughs and the focus on a request.

Moved whole from `__init__.py` (audit AR3, gods-2): the code is unchanged, and
`__init__` re-exports every name here that anything reads. Imports run one way,
down the layer list in `__init__.py`'s docstring, never back to `__init__`.
"""

from __future__ import annotations

import re

from tessellate.ai import toolwords
from tessellate.ai.tools.tool_sets import CHANGE_TOOLS, CORE_TOOLS, TOOL_GROUPS, WRITE_TOOLS
from tessellate.ai.tools.tool_table import TOOLS

def needs_confirm(name: str, arguments: dict | None = None, approved: bool = False) -> bool:
    """Whether this call parks for a Confirm card whatever else is true of the turn.

    `approved` is a run the person already started with the writes listed (a
    plan's "Run the plan", a skill they ran): their click was the confirm for
    changes, so only a removal still parks.
    """
    spec = TOOLS.get(name)
    if spec is None:
        return False
    if spec.destructive:
        return True
    if approved:
        return False
    #: Every write waits (owner, 2026-11-10: "any and all actions need the user's consent"), adds too.
    return name in WRITE_TOOLS or name in CHANGE_TOOLS or (name == "tag_note" and bool((arguments or {}).get("remove")))

# "Do something about my notebook" without saying what. The safe answer is the
# whole toolbox: this is exactly the request that needs tools we can't guess.
BROAD_REQUESTS = (
    "tidy", "organise", "organize", "clean up", "sort out", "sort my",
    "go through", "merge", "duplicate", "reorganise", "reorganize",
    "manage my", "look after", "housekeeping", "do whatever",
)


# "Now do the thing we just talked about." The reported failure this exists
# for: *"I asked it for suggestions on modifying my categories, and when I
# asked it to implement the suggestions it just gave me the suggestions again
# and no tool calls."*
#
# The cause was here and it is exact. `focus_for` read the current message and
# nothing else, and "implement those suggestions" contains no category word, 
# so the turn was offered the reading core and no category tools at all. The
# model was not being lazy; it had no `merge_categories` to call. The only
# thing it *could* do was write the suggestions out again.
#
# A follow-through carries its subject in the turn before it, by definition.
# So on these, the cue matching runs over the previous exchange as well, and
# if that still finds nothing the turn gets everything, losing the tool the
# user just asked for is far worse than sending schemas that go unused.
FOLLOW_THROUGH = (
    "do it", "do that", "do this", "go ahead", "go for it", "implement",
    "apply", "make those", "make these", "make the changes", "carry on",
    "proceed", "please do", "sounds good", "yes do", "action those",
    "execute", "run it", "run them", "get on with", "let's do", "lets do",
    "all of them", "both of them", "the first one", "the second one",
    "that one", "option ", "your suggestion", "those suggestion",
    "these suggestion", "as you suggested", "what you suggested",
)

#: A bare "yes", "ok", "sure" is a follow-through too, but only when it is the
#: *whole* message: "yes, remind me tomorrow" says what it wants and should be
#: read on its own terms.
BARE_AGREEMENT = {
    "yes", "yep", "yeah", "ok", "okay", "sure", "please", "go", "do it",
    "y", "confirmed", "correct", "right", "agreed", "perfect", "great",
}


def is_follow_through(question: str) -> bool:
    """Does this message mean "act on what we just discussed"?"""
    text = f" {(question or '').lower().strip()} "
    stripped = text.strip().strip(".!,").strip()
    if stripped in BARE_AGREEMENT:
        return True
    return any(cue in text for cue in FOLLOW_THROUGH)


#: "add …/put …/write … to/in/into my|the|that … note": an edit.
_ADD_TO_NOTE = re.compile(
    r"\b(?:add|put|write|stick|include)\b[^.?!\n]{1,80}?\b(?:to|in|into|onto)\s+(?:my|the|that|this)\b[^.?!\n]{0,40}?\bnote\b",
    re.IGNORECASE,
)


def adds_to_a_named_note(question: str) -> bool:
    """Whether a request adds to a note it names ("put X in my Y note"), so
    the write it wants is an edit, never a new note."""
    return bool(_ADD_TO_NOTE.search(question or ""))


def focus_for(question: str, recent: str = "") -> list[str] | None:
    """The tools worth offering for this question, or None for all of them.

    Deliberately keyword-driven rather than another model call: an extra
    round-trip to decide what to send would cost more than it saves, and a
    deterministic rule can be read, tested, and argued with.

    `recent` is the previous exchange, and it is only consulted for a message
    that means "now do it", see FOLLOW_THROUGH. Reading history on *every*
    turn would be worse than reading none: a question about beans, asked after
    a conversation about deleting things, would be offered delete_note.
    """
    return focus_detail(question, recent).tools


def focus_detail(question: str, recent: str = "") -> toolwords.Focus:
    """`focus_for`, with the reasoning attached, see `toolwords.Focus`.

    Split out so the agent can log *why* a tool was offered. "The AI didn't use
    the tool I expected" and "the AI tagged something I only asked about" are
    both otherwise indistinguishable from the model making its own choice.
    """
    asked = question or ""
    text = f" {asked} "
    broad = toolwords.score_groups(text, [((), BROAD_REQUESTS)])[0]
    if broad:
        return toolwords.Focus(tools=None, broad=True)

    # A follow-through's subject is in the turn before it. Matched over both,
    # so "implement those suggestions" after a conversation about categories
    # gets the category tools, and so an instruction that names its own
    # subject ("apply that and also tag them") keeps its own cues too.
    following = is_follow_through(asked)
    if following and recent:
        text = f"{text} {recent} "
        if toolwords.score_groups(text, [((), BROAD_REQUESTS)])[0]:
            return toolwords.Focus(tools=None, broad=True, followed_through=True)

    ranked, cues = toolwords.score_groups(text, TOOL_GROUPS)
    if following and not ranked:
        # "Do it" and nothing in the conversation says what "it" is. The safe
        # answer is the whole toolbox: this is precisely the turn where the
        # user is expecting an action, so being unable to act is the one
        # outcome that is certainly wrong.
        return toolwords.Focus(tools=None, followed_through=True)

    # A question *about* a capability keeps that capability's reading tools and
    # loses its writing ones. "How do I tag a note?" should be able to look at
    # the tags to answer well; it should not be holding delete_tag while it
    # does. Note this narrows within a group that already fired, it never
    # drops the group, because the question is still about that subject.
    asking = toolwords.looks_like_a_question_about(asked)

    wanted = list(CORE_TOOLS)
    for index, _score in ranked:
        for name in TOOL_GROUPS[index][0]:
            if asking and name in WRITE_TOOLS:
                continue
            wanted.append(name)

    # "Add X to my Y note" is an edit, and no single cue word says so (INBOX
    # 527: Qwen2.5-1.5B, offered no edit_note, rewrote the note in prose).
    if not asking and _ADD_TO_NOTE.search(asked):
        wanted.append("edit_note")

    # The web tools are the user's own opt-in, made per-notebook rather than
    # per-question; `tool_enabled` already hides them otherwise, and second-
    # guessing that switch here would mean "web search is on but I didn't
    # think you meant it".
    wanted.extend(["web_search", "read_url"])
    # De-duplicated but order-preserving: a group can name a tool that is
    # already core, and a repeated schema is a wasted schema.
    unique = list(dict.fromkeys(wanted))
    return toolwords.Focus(
        tools=unique,
        ranked=ranked,
        cues=cues,
        asking_about=asking,
        followed_through=following,
    )
