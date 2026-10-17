"""The act registry's table (CHAT_PLAN "The deterministic foundation",
decision 53), a leaf with no imports of its own: the acts, the intents that
wait for Confirm, and the text generated from them (the capability line, the
palette rows, the Guide topic, Ask's line). `ai/acts.py` runs the acts over
`ai/commands.py`; `commands.py` and `help_topics_more.py` read this table, so
neither has to import the runner (an import cycle the lints refused).
"""

from __future__ import annotations

from dataclasses import dataclass

#: The act runner's `propose` (acts.py), set when acts.py is imported: the
#: agent's `propose_act` tool (ai/tools) calls it through this leaf rather
#: than importing the runner, which imports commands, which imports tools
#: (the import cycle `tests/test_no_import_cycles.py` refuses).
#: `api/routes_chat.py` imports acts at module level, so the app always has it.
proposer = None


#: The one reading (`reading.read`) and Chat's help sentence
#: (`composer.help_line`), set by those modules when they are imported, for
#: the Guide (`help_chat`): it sits above both in the import graph (tools and
#: the librarian import it), so it reads them through this leaf. Unset, the
#: Guide keeps its keyword rules and its topic text (decision 59, step 4).
reader = None
help_sentence = None


#: `commands.read_typed`, set when `commands` is imported (the routes do), for
#: `intent.classify`: intent sits below commands in the import graph, so it
#: reads the typed commands through this leaf rather than importing them.
def typed_reader(text, now):  # noqa: ANN001, ARG001
    """Replaced by `commands.read_typed` when that module is imported."""
    return None


#: The question repair (`question_noise.repair`), set when that module is
#: imported (intent, composer and the routes import it), for the Guide: the
#: speller reads the help text, so the Guide importing it back was a cycle
#: (`tests/test_no_import_cycles.py`). Unset, the Guide reads the words as typed.
repair = None

#: The plan reader (`ai/plan_writes.py`: a step's writes, the tools they need,
#: an edit's diff), set when that module is imported. The agent reads it
#: through this leaf because plan_writes imports acts and commands, which
#: import the agent (the import cycle `tests/test_no_import_cycles.py`
#: refuses). `ai/skill_runner.py` (which routes_chat imports at module
#: level) imports it at module level, so the app always has it.
plans = None


def propose(session, text: str, now, note_ids: list[int] | None = None) -> dict | None:  # noqa: ANN001
    """A model's proposed act through the registered runner (acts.propose)."""
    if proposer is None:
        raise RuntimeError("tessellate.ai.acts is not imported, so no act can be proposed")
    return proposer(session, text, now, note_ids)


#: The write intents that wait for Confirm before anything changes.
CONFIRM_INTENTS = frozenset({"delete", "rename", "move", "tag", "untag", "link", "unlink", "append"})


@dataclass(frozen=True)
class Act:
    """One act: the intent `commands.read` gives, the verb it is said with,
    the slots it needs, what Undo runs, and how Help says it."""

    intent: str
    verb: str
    label: str
    help: str
    example: str
    slots: tuple[str, ...]
    #: The tool Undo runs, or "" for an act that changes nothing.
    inverse: str = ""
    writes: bool = True
    #: The words the palette puts in the box for this act, the caret after
    #: them ("Tag the note about "); "" for an act the palette's own starters
    #: already offer (reminders, a new note, find, summarise).
    stem: str = ""

    @property
    def confirm(self) -> bool:
        return self.intent in CONFIRM_INTENTS


#: In the order the capability line says them.
_ACTS = (
    Act("reminder", "remind", "set a reminder", "Say what and when; it is set at once with Undo.",
        "remind me to call mum on Friday at 9", ("text", "due_at"), "bin_reminder"),
    Act("tag", "tag", "tag notes", "Name the notes and the tags; the change waits for Confirm.",
        "tag the knife note with kitchen", ("tags",), "edit_note", stem="Tag the note about "),
    Act("untag", "untag", "take a tag off", "Name the tag and the notes; waits for Confirm.",
        "remove the tag urgent from the boiler note", ("tags",), "edit_note"),
    Act("move", "file", "move notes to a category", "Name the notes and the category; waits for Confirm.",
        "move the sourdough note to Cooking", ("category",), "edit_note", stem="Move the note about "),
    Act("new_note", "create", "make a new note", "Start with \"note:\" and the words; saved at once with Undo.",
        "note: buy milk and eggs", ("content",), "delete_note"),
    Act("meeting", "create", "start a meeting", "Starts a meeting note now; Undo bins it.",
        "start a meeting", (), "delete_note", stem="Start a meeting"),
    Act("pin", "pin", "pin a note", "Pins one note to the top of the list; Undo unpins it.",
        "pin the dentist note", (), "pin_note", stem="Pin the note about "),
    Act("unpin", "unpin", "unpin a note", "Takes one note's pin off; Undo pins it again.",
        "unpin the dentist note", (), "pin_note"),
    Act("link", "link", "link two notes", "Names both notes; waits for Confirm, Undo unlinks them.",
        "link the gym note to the running note", (), "unlink_notes", stem="Link the note about "),
    Act("unlink", "unlink", "unlink two notes", "Names both notes; waits for Confirm, Undo links them again.",
        "unlink the gym note from the running note", (), "link_notes"),
    Act("rename", "rename", "rename a note", "Names the note and its new heading; waits for Confirm.",
        "rename the gym note to Strength plan", ("title",), "edit_note", stem="Rename the note about "),
    Act("append", "add", "add a line to a note", "Names the words and the note; waits for Confirm.",
        "add buy chalk to the gym note", ("content",), "edit_note", stem="Add "),
    Act("delete", "delete", "delete a note", "Always waits for Confirm; the note goes to the bin and Undo restores it.",
        "delete the boiler note", (), "restore_note", stem="Delete the note about "),
    Act("find", "find", "find a note", "Lists the notes that match.", "find my note about the passport", (), writes=False),
    Act("open", "open", "open a note", "Opens the one note named.", "open the note about the boiler", (), writes=False),
    Act("navigate", "open", "open a part of the app", "Goes to Settings, the graph, the timeline and the rest.",
        "open settings", ("surface",), writes=False),
    Act("summarise", "summarise", "summarise notes", "Says what a set of notes holds, from the notes.",
        "summarise my gym notes", (), writes=False),
)
ACTS: dict[str, Act] = {a.intent: a for a in _ACTS}


# --- what the surfaces say, generated -------------------------------------------------------


def capability_line() -> str:
    """Agent mode with no model, for a sentence that is not an act: every
    write act the registry has, in order, and one example."""
    said = [a.label for a in _ACTS if a.writes and a.intent not in ("untag", "unpin", "unlink", "append", "rename", "delete", "link", "pin")]
    single = "pin, link, rename or delete a note (delete always after you confirm)"
    reads = "find or open a note"
    return (
        "With no model running I can do these myself: "
        + ", ".join([*said[:4], reads, *said[4:]])
        + f", {single}. For example: {ACTS['reminder'].example}."
    )


def ask_line(parsed: dict | None) -> str:
    """What Ask says to a sentence that is an act: where it is done."""
    act = ACTS.get((parsed or {}).get("intent", ""))
    named = f" ({act.label})" if act else ""
    return f"That is something to do{named} rather than to look up: say it in Chat and it is done there, with Undo."


def palette_rows() -> list[dict]:
    """One palette row per act: its label, the words it puts in the box
    ("" for an act the palette's own starters already offer), an example and
    its help line (palette.js draws those with a stem under "Do")."""
    return [{"intent": a.intent, "label": a.label[:1].upper() + a.label[1:], "stem": a.stem, "example": a.example,
             "help": f"{a.help} For example: {a.example}."} for a in _ACTS]


def guide_topic() -> dict:
    """The Guide's topic on acts, generated from the registry."""
    lines = [f"{a.label[:1].upper() + a.label[1:]}: \"{a.example}\"." for a in _ACTS]
    waits = ", ".join(a.label for a in _ACTS if a.confirm)
    return {
        "id": "chat-acts",
        "title": "Things Chat does for you",
        "keywords": ("what can chat do", "chat commands", "commands in chat", "do it for me", "acts", "an act",
                     "with no model running", "undo an act", "things chat does"),
        "badge": {"label": "Chat", "tab": "chat"},
        "body": "Chat does these from one sentence, with no model. " + " ".join(lines)
        + f" These wait for Confirm: {waits}. The rest run at once. Undo on the card, or Ctrl+Z, takes any of them back.",
    }


# --- the tools a sentence reaches with no model (decision 59, step 1, Brief 84) ---------------

#: The tool each act runs through (`ai/tools`), so a reading of an act names
#: its tool as well as its intent. "navigate" opens a part of the app and
#: runs no tool.
ACT_TOOLS: dict[str, str] = {
    "reminder": "set_reminder", "tag": "tag_note", "untag": "tag_note", "move": "edit_note",
    "new_note": "create_note", "meeting": "create_note", "pin": "pin_note", "unpin": "pin_note",
    "link": "link_notes", "unlink": "unlink_notes", "rename": "edit_note", "append": "edit_note",
    "delete": "delete_note", "find": "search_notes", "open": "get_note", "summarise": "summarize_notes",
}

#: A utility's kind (`utilities.kind_of`) to the tool a model would call for it.
UTILITY_TOOLS: dict[str, str] = {"clock": "get_current_time", "dates": "get_current_time"}

#: "due" as a time, not "due diligence": the end, or a when after it.
_WHEN = r"(?=$|[?.!]| (?:today|tomorrow|tonight|this|next|soon|now|later|on|by|in|before|yet|for me)\b)"


def _listing(nouns: str) -> str:
    """A request for the whole list of one kind of thing, said any of the
    ways people say it ("what tags do I have", "show me every tag I have",
    "all my tags", "which categories are there"), and nothing after the
    noun that makes it a question about one note ("what tags does the
    dentist note have" is not the list). Routing gold:
    `tests/fixtures/composer/routing_1011.json`."""
    ask = r"(?:(?:can|could|would) you |please |pls )?(?:list|show|give|tell|what|which)(?: me)?(?: all| every)?(?: of)?"
    tail = (
        r"(?: (?:do|have|did) i (?:have|got|use|used|made|got going)| i (?:have|use|used|made)| (?:are|r) there| exist| i(?:'ve| have) got)?"
        r"(?: (?:the )?most| so far| now| atm)?(?: (?:please|pls|plz))?[?.]*$"
    )
    return rf"^(?:{ask} |all |every )?(?:(?:are|r) )?(?:all |every )?(?:my |the |your )?(?:{nouns}){tail}"


#: The words that name one tool, most particular first: the first pattern
#: that matches the lowered sentence names the tool, ahead of the act or
#: question the sentence also reads as ("remove the tag urgent from every
#: note" is the tag's deletion, not one note's untagging). Words only, never
#: a date or a unit: those are `ai/recognise.py`'s (`tests/test_one_reader.py`).
TOOL_CUES: tuple[tuple[str, str], ...] = (
    ("read_url", r"https?://"),
    ("web_search", r"\b(?:search|look up|google)\b.*\b(?:the web|online|internet)\b"),
    ("read_text", r"\bread the (?:dates|amounts|numbers|times|units)\b"),
    ("check_answer", r"\bcheck (?:this|that|the|my) (?:answer|draft|reply)\b"),
    ("propose_act", r"\bsuggest (?:something|an act|a change) to do\b"),
    ("save_user_preference", r"\bremember that i (?:prefer|like|want)\b|\bfrom now on\b"),
    ("ask_user", r"\bask me (?:which|what|before)\b"),
    ("compress_chat", r"\b(?:compress|shorten|condense) (?:this|the) (?:chat|conversation)\b"),
    ("make_plan", r"\bmake (?:me )?a plan\b|\bplan (?:the steps|out)\b"),
    ("search_chat_history", r"\b(?:earlier|previous|past|last|old) (?:chat|conversation)s?\b|\bwhat did we (?:talk|chat) about\b"),
    ("find_contradictions", r"\bcontradict|\bdisagree\b|\binconsisten"),
    ("audit_link_reasons", r"\b(?:audit|check|fix)\b.*\blink reasons?\b"),
    ("path_between", r"\bhow (?:is|are) .+ (?:related|connected) to\b|\bpath between\b"),
    ("related_notes", r"\bwhat(?:'s| is) (?:connected|linked) to\b|\b(?:connected|linked) to the .+ note\b"),
    ("find_similar_notes", r"\bsimilar to\b|\blike the .+ note\b"),
    ("notebook_structure", r"\b(?:shape|structure|clusters?) of (?:my|the) notebook\b|^how (?:are|r) (?:all )?my notes (?:connected|linked)\b"),
    ("notebook_overview", r"\boverview of (?:my|the) notebook\b|\bnotebook overview\b|^how (?:big|large) is (?:my|the) notebook\b"),
    ("count_notes", r"\bcount (?:my |the )?notes\b|\bnotes per (?:category|tag)\b"),
    ("list_tags", r"\b(?:list|show|what are) (?:me )?(?:all )?my tags\b|" + _listing("tags?")),
    ("list_categories", r"\b(?:list|show|what are) (?:me )?(?:all )?my categories\b|" + _listing("categories|categorys|category")),
    #: "what tasks do I have", "whats due this week", "what is overdue": the
    #: reminders are the app's task list (decision 75: with a model up too).
    #: A checklist on one note ("what is still open on X") is the composer's.
    ("list_reminders", r"\b(?:what|which|list|show)\b.*\breminders\b|^any reminders\b"
     r"|^(?:what|which|list|show)(?: me)?(?: are)?(?: all)? (?:my |the )?(?:open |outstanding )?(?:tasks|to-?dos)\b(?! (?:on|for|in|from|about) )"
     rf"|^(?:what(?:'s|s| is| are)?|which \w+|is (?:there )?anything|anything) (?:(?:is |are )?(?:still )?)?(?:over)?due{_WHEN}"
     rf"|^what (?:do|have) i (?:got |have )?(?:over)?due{_WHEN}"),
    ("complete_reminder", r"\bmark\b.*\breminder\b.*\bdone\b|\btick off\b.*\breminder\b"),
    ("list_documents", r"^(?:list|show)(?: me)? (?:all )?my documents[?.]?$|" + _listing("documents|docs")),
    ("list_skills", r"\b(?:list|show) (?:me )?(?:all )?my skills\b|\bwhat skills\b|" + _listing("skills")),
    ("run_skill", r"\brun the .+ skill\b"),
    ("save_skill", r"\bsave (?:this|that|it) as a skill\b"),
    ("delete_skill", r"\bdelete the .+ skill\b"),
    ("list_library", r"\b(?:shape|symbol) library\b|\bwhat shapes\b"),
    ("place_library_item", r"\bfrom the library\b"),
    ("search_whiteboard", r"\bsearch (?:my |the )?(?:white)?boards\b"),
    ("add_whiteboard_card", r"\bput the .+ note on the .*(?:white)?board\b"),
    ("add_whiteboard_link", r"\bconnect the (?:two )?cards\b"),
    ("read_whiteboard", r"\bwhat(?:'s| is) on the .*whiteboard\b|\bread the .*whiteboard\b"),
    ("generate_diagram", r"\bdraw a (?:diagram|tree|flowchart) of\b"),
    ("add_board_shape", r"\bdraw an? (?:rectangle|ellipse|diamond|circle|frame|box)\b"),
    ("restore_board_item", r"\bput the \w+ back on the board\b"),
    ("delete_board_item", r"\btake the \w+ off the board\b"),
    ("move_board_item", r"\bmove the (?:sticky|card|shape|frame|text box)\b.*\bboard\b"),
    ("edit_board_item", r"\bchange the (?:words|text|colour|color|fill) on the (?:sticky|card|shape|frame)\b"),
    ("link_map_nodes", r"\bcross-?link\b"),
    ("add_map_node", r"\badd a node\b"),
    ("map_from_note", r"\b(?:turn|make) (?:the |this |my )?.*note into a (?:mind ?)?map\b|\bmind ?map (?:from|of) (?:the|this|my) .*note\b"),
    ("create_mindmap", r"\b(?:start|make|create) a (?:new )?mind ?map\b"),
    ("read_mindmap", r"\bread the .*mind ?map\b|\bwhat(?:'s| is) on the .*mind ?map\b"),
    ("rename_tag", r"\brename the tag\b"),
    ("delete_tag", r"\b(?:delete|remove) the tag \S+(?: from)? (?:every|all)\b|\bdelete the tag\b"),
    ("create_category", r"\b(?:make|create|add) a (?:new )?category\b"),
    ("rename_category", r"\brename the category\b"),
    #: Notes sent to a space (`tools/moving.py`); to a category is the move act.
    ("move_notes", r"\b(?:move|send|put)\b.*\bnotes?\b.*\b(?:to|into) (?:the |my )?(?:space\b|\w+ space\b)"),
    ("merge_categories", r"\bmerge\b.*\bcategor"),
    ("delete_category", r"\b(?:delete|remove) the category\b"),
    ("restore_note", r"\brestore\b|\bfrom the (?:recycle )?bin\b|\bundelete\b"),
    ("delete_document", r"\bdelete the document\b"),
    ("get_document", r"\b(?:read|open|show) the document\b"),
    ("create_document", r"\bwrite (?:a|me a) (?:document|report|essay|write-up)\b"),
    ("search_files", r"\bin my files\b|\b(?:my|the) (?:photos|scans|attachments|pdfs)\b"),
    ("read_file", r"\bread the .+ file\b|\btext in the .+ file\b"),
    ("list_notes", r"^(?:list|show)(?: me)? (?:all )?my notes[?.]?$"),
    ("search_help", r"^how (?:do|can) i\b|^where (?:is|do i find)\b"),
)

#: The read tools Chat runs itself with no model and no arguments, the
#: answer drawn in its form by the realiser (`realise.tool_answer`).
NO_MODEL_READS = frozenset({
    "list_tags", "list_categories", "count_notes", "notebook_overview", "list_reminders",
    "list_documents", "list_skills", "list_notes", "notebook_structure",
})

#: The Guide topics that already explain an act (decision 59, step 4): a
#: how-to that reads as one of these acts keeps its topic first, the act's
#: own line next; one whose words reached another topic gets the act first.
ACT_HELP_TOPICS: dict[str, tuple[str, ...]] = {
    "reminder": ("reminders", "reminders-controls"), "meeting": ("meetings", "voice"), "link": ("links",),
    "unlink": ("links",), "tag": ("tags-categories", "tag-manager", "suggested-tags"),
    "untag": ("tags-categories", "tag-manager"), "move": ("tags-categories",), "delete": ("undo-bin",),
    "pin": ("favourites",), "unpin": ("favourites",), "find": ("ask-chat",), "summarise": ("ask-chat",),
    "new_note": ("capture",),
}


def act_topic(intent: str) -> dict:
    """One act as a Guide topic, generated from its row: how it is said in
    Chat, what it does, and that Undo takes it back."""
    act = ACTS[intent]
    return {
        "id": f"act-{intent}",
        "title": act.label[:1].upper() + act.label[1:],
        "keywords": (),
        "badge": {"label": "Chat", "tab": "chat"},
        "body": f"Say it in Chat: “{act.example}”. {act.help}",
    }
