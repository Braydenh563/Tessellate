"""The tools that change notes: create, edit, tag, pin, link, delete, restore, reminders and tags.

Moved whole from `__init__.py` (audit AR3, gods-2): the code is unchanged, and
`__init__` re-exports every name here that anything reads. Imports run one way,
down the layer list in `__init__.py`'s docstring, never back to `__init__`.
"""

from __future__ import annotations

import logging

from tessellate.ai.tools._common import DEFAULT_LIST_LIMIT, ToolError, _clip, _limit_arg, _note_summary, _refresh_embedding, _require_note, _undo_edit
from tessellate.core.database import Entry, Reminder
from sqlalchemy.orm import Session
from tessellate.core import deps
from sqlalchemy import func, select
from tessellate.entry import manager
from tessellate.repo import relation_types
from tessellate.repo import tags as tags_repo
from datetime import timedelta
from tessellate.ai.tools.tool_read import _named

def _create_note(session: Session, args: dict) -> dict:
    content = str(args["content"]).strip()
    if not content:
        raise ToolError("The note content is empty")
    category = str(args.get("category") or "").strip()
    tags = [str(t) for t in args.get("tags") or []]
    if category:
        entry = manager.create_entry(
            session, content, category_name=category, tags=tags, ai_confidence=100
        )
    else:
        # No category given: ask the janitor, exactly like a manual save.
        try:
            from tessellate.ai import janitor

            category, confidence, _filed_by = janitor.categorise(
                session,
                content,
                deps.get_embeddings(),
                deps.get_model_manager(),
                deps.get_ollama(),
            )
        except Exception:
            # `categorise` handles a model that is down itself; reaching here
            # is a fault in it, which used to read as "uncategorised" forever.
            logging.getLogger("tessellate.tools").warning(
                "filing a note the agent made failed; left uncategorised", exc_info=True
            )
            category, confidence = manager.UNCATEGORISED, 0
        entry = manager.create_entry(
            session, content, category_name=category, tags=tags, ai_confidence=confidence
        )
    deps.store_quietly(session, entry)
    result = _note_summary(session, entry)
    result["label"] = f"ph:pencil-simple Created {_named(entry)} in {result['category']}"
    result["undo"] = {"tool": "delete_note", "arguments": {"note_id": entry.id}}
    return result


def _edit_note(session: Session, args: dict) -> dict:
    entry = _require_note(session, args)
    undo = _undo_edit(session, entry)  # before the write, or it undoes nothing
    content = args.get("content")
    content_changed = content is not None and str(content) != entry.content
    before_category = manager.category_name_for(session, entry)
    before_tags = manager.entry_tags(entry)
    manager.update_entry(
        session,
        entry,
        content=str(content) if content is not None else None,
        category_name=str(args["category"]) if args.get("category") else None,
        tags=[str(t) for t in args["tags"]] if args.get("tags") is not None else None,
    )
    if content_changed:
        _refresh_embedding(session, entry)
    result = _note_summary(session, entry)
    #: What changed, and the category it is still in when that did not
    #: (Qwen2.5-3B, 2026-10-05: "Move the plumber note to Home" sent the
    #: name as a tag and then answered "moved from Work to Home" off a label
    #: that said only "Updated note #1"). The truth goes back with the call.
    after_category = result["category"]
    changed = [
        name
        for name, moved in (
            ("content", content_changed),
            ("category", after_category != before_category),
            ("tags", result["tags"] != before_tags),
        )
        if moved
    ]
    result["changed"] = changed
    parts = []
    if "category" in changed:
        parts.append(f"moved from {before_category} to {after_category}")
    if "tags" in changed:
        parts.append(f"tags now {', '.join(result['tags']) or 'none'}")
    if "content" in changed:
        parts.append("text rewritten")
    if "category" not in changed:
        parts.append(f"still in {after_category}")
    result["label"] = f"ph:note-pencil Updated {_named(entry)}: {'; '.join(parts)}"
    result["undo"] = undo
    return result


def _requested_ids(args: dict, single: str, plural: str) -> list[int]:
    """The ids a batch tool was asked to act on, in order and de-duplicated.

    Reads both the singular and the plural argument without writing to either.
    The first version of this built its list by `args[plural].append(...)`,
    which mutated the caller's own dict: and the agent loop had already taken
    a `json.dumps(arguments)` fingerprint of that dict to spot repeated calls,
    so the fingerprint no longer matched the arguments the tool actually ran
    with and the loop breaker stopped recognising a repeat.
    """
    wanted: list[int] = []
    raw = args.get(plural) or []
    if not isinstance(raw, list):
        raise ToolError(f"{plural} must be a list of note ids")
    for value in [*raw, args.get(single)]:
        if value is None:
            continue
        try:
            note_id = int(value)
        except (TypeError, ValueError) as exc:
            raise ToolError(f"{value!r} is not a note id") from exc
        if note_id not in wanted:
            wanted.append(note_id)
    return wanted


def _tag_note(session: Session, args: dict) -> dict:
    note_ids = _requested_ids(args, "note_id", "note_ids")
    if not note_ids:
        raise ToolError("Must provide at least one note_id")

    add_tags = args.get("add") or []
    #: Folded: a tag is one tag to the person whatever its case (as in the
    #: `repo/tags.py` `bulk_edit`); "remove urgent" left "Urgent" on the
    #: note while the label said it was gone (caught by the B5 postcondition).
    remove_tags = {str(r).casefold() for r in args.get("remove") or []}

    results = []
    undos = []
    tagged: list[int] = []

    for note_id in note_ids:
        # `_require_note` rather than `manager.get_entry`: it is the one place
        # that refuses a private note, and going around it let the AI retag
        # notes it is not allowed to read (caught by
        # test_write_tools_refuse_private_notes_too). A missing or binned note
        # in a batch is skipped; a private one is refused loudly, because
        # quietly skipping it would tell the user the tag was applied.
        if manager.get_entry(session, note_id) is None:
            continue
        entry = _require_note(session, {"note_id": note_id})
        if entry.is_deleted:
            continue

        undos.append(_undo_edit(session, entry))
        tags = manager.entry_tags(entry)
        tags = [t for t in tags if t.casefold() not in remove_tags]
        for tag in add_tags:
            if str(tag).casefold() not in {t.casefold() for t in tags}:
                tags.append(str(tag))
        manager.update_entry(session, entry, tags=tags)

        tagged.append(entry.id)
        results.append(f"#{entry.id} → {', '.join(tags) or 'no tags'}")

    if not tagged:
        raise ToolError("No valid notes found to tag.")

    result: dict = {
        "tagged": tagged,
        "label": f"ph:tag Retagged {len(results)} note(s): {', '.join(results)}",
        # Every note's undo, not just the first. The batch version originally
        # kept `undos[0] if len(undos) == 1 else None`, which meant tagging
        # two notes at once could not be undone at all.
        "undo": undos[0] if len(undos) == 1 else {"tool": "batch", "steps": undos},
    }
    if len(tagged) == 1:
        # A single-note call keeps the shape the one-note tool always had, so
        # callers that read `tags` (and the change list, which reads `id`)
        # don't have to special-case the batch form.
        entry = manager.get_entry(session, tagged[0])
        if entry is not None:
            result["tags"] = manager.entry_tags(entry)
            result["id"] = entry.id
    return result


def _pin_note(session: Session, args: dict) -> dict:
    entry = _require_note(session, args)
    pinned = bool(args.get("pinned", True))
    if pinned != entry.pinned:
        entry.pinned = pinned
        manager.log_action(
            session, "edited", "entry", entry.id, "pinned" if pinned else "unpinned"
        )
        session.commit()
    result = _note_summary(session, entry)
    verb = "Added to Favourites" if pinned else "Removed from Favourites"
    result["label"] = f"ph:star {verb}: {_named(entry)}"
    result["undo"] = {
        "tool": "pin_note",
        "arguments": {"note_id": entry.id, "pinned": not pinned},
    }
    return result


#: The most a `link_type` description may cost on the wire. Prompt text is
#: budgeted (`agent.PROSE_BUDGET_CHARS`) and this one is read on every round
#: of any turn that offers `link_notes`, so a notebook with sixty relation
#: types cannot be allowed to put sixty names in front of a 3B model.
LINK_TYPE_DESCRIPTION_CHARS = 420

_LINK_TYPE_LEAD = (
    "Optional: note_id <kind> the other note. One of: "
)
_LINK_TYPE_TAIL = ". Omit when unsure."


def link_type_description(types: dict[str, dict]) -> str:
    """The `link_type` parameter's text for these relation types
    (`relation_types.kinds`): the built-ins first, then the person's own,
    cut to `LINK_TYPE_DESCRIPTION_CHARS` with a count of what was left out."""
    keys = list(types)
    room = LINK_TYPE_DESCRIPTION_CHARS - len(_LINK_TYPE_LEAD) - len(_LINK_TYPE_TAIL)
    shown: list[str] = []
    used = 0
    for key in keys:
        cost = len(key) + (2 if shown else 0)
        # Keep room for "(+99 more)" so the count itself cannot overflow.
        if used + cost > room - 12 and len(shown) < len(keys):
            break
        shown.append(key)
        used += cost
    text = ", ".join(shown)
    left = len(keys) - len(shown)
    if left:
        text += f" (+{left} more)"
    return f"{_LINK_TYPE_LEAD}{text}{_LINK_TYPE_TAIL}"


def _resolve_link_type(session: Session, wanted: object) -> str | None:
    """The key of the relation type the model named, by key or by name in any
    case ("Part of" for `part_of`); None when none was named. An unknown one
    is a ToolError that lists what exists, so the retry is one call."""
    text = " ".join(str(wanted or "").split())
    if not text:
        return None
    types = relation_types.kinds(session)
    folded = text.casefold()
    snake = folded.replace(" ", "_").replace("-", "_")
    for key, row in types.items():
        if folded in (key.casefold(), str(row.get("name") or "").casefold()) or snake == key.casefold():
            return key
    listed = link_type_description(types).removeprefix(_LINK_TYPE_LEAD).removesuffix(_LINK_TYPE_TAIL)
    raise ToolError(f"There is no kind of link called “{_clip(text, 40)}”. Use one of: {listed}.")


def _link_notes(session: Session, args: dict) -> dict:
    source = _require_note(session, args)
    other_ids = _requested_ids(args, "other_note_id", "other_note_ids")
    if not other_ids:
        raise ToolError("Must provide at least one target note id.")
    # Optional: asked for directly ("a note about uni and gym might still be
    # related if they're both about scheduling"): the connection the model
    # is making, in its own words, so the graph and Trace can say *why*
    # rather than just *that*. Applied to every target in this call; a model
    # linking notes for different reasons in one turn makes separate calls.
    reason = str(args.get("reason") or "").strip() or None
    link_type = _resolve_link_type(session, args.get("link_type"))

    linked = []
    for target_id in other_ids:
        if manager.get_entry(session, target_id) is None:
            continue
        # Same reason as `_tag_note`: the target has to go through the private
        # guard too. Linking *to* a private note is a leak even though nothing
        # reads its text: the link shows up in the graph and in `get_note`'s
        # connected ids, so the note's existence and its neighbours escape.
        target = _require_note(session, {"note_id": target_id})
        if target.is_deleted:
            continue
        link = manager.create_link(session, source, target, reason=reason, link_type=link_type)
        if link is not None:
            linked.append(target.id)

    if not linked:
        raise ToolError(
            "No new links were created (they may already be linked, or the target doesn't exist)."
        )

    return {
        "linked": [source.id] + linked,
        "label": (
            f"ph:link Linked {_named(source)} to {len(linked)} other note(s): "
            f"{', '.join(map(str, linked))}"
        ),
    }


def _unlink_notes(session: Session, args: dict) -> dict:
    """Take a connection back out.

    The missing half of `link_notes`, and its absence had a specific cost: a
    notebook audit could add connections and never correct one, so a wrong
    link: from a model's earlier guess, or a topic that turned out to be two
    topics: was permanent from inside the app.

    Not destructive, and that is a deliberate call rather than an oversight: a
    link carries no writing of its own, both notes survive untouched, and the
    result carries the `link_notes` call that puts it straight back. Making it
    ask first would have meant a confirm card for every correction in a tidy-up
    run, which is how people learn to click through confirm cards.
    """
    source = _require_note(session, args)
    # The target goes through the private guard too, exactly as it does in
    # `_link_notes` above: and for the same reason, which is easy to lose
    # because unlinking *feels* like it reveals less than linking.
    #
    # It does not. `manager.get_entry` was what this called, which answers for
    # a private note like any other, so the two error paths below were an
    # oracle: "no note with id N" versus "notes #A and #B aren't linked" tells
    # you whether a private note exists AND whether it is linked to a note you
    # can read: and on the success path it edits the link table for a note the
    # caller is not allowed to see at all.
    #
    # This is the shape CLAUDE.md flags: a guard removed while the code around
    # it kept its shape. `_link_notes` still looked correct beside it.
    target = _require_note(session, {"note_id": int(args["other_note_id"])})
    if target.is_deleted:
        raise ToolError(f"No note with id {args.get('other_note_id')}")
    removed = manager.remove_link(session, source, target)
    if not removed:
        raise ToolError(f"Notes #{source.id} and #{target.id} aren't linked")
    return {
        "unlinked": [source.id, target.id],
        "undo": {
            "tool": "link_notes",
            "arguments": {"note_id": source.id, "other_note_id": target.id},
        },
        "label": f"ph:scissors Unlinked {_named(source)} from {_named(target)}",
    }


def _delete_note(session: Session, args: dict) -> dict:
    entry = _require_note(session, args)
    manager.soft_delete_entry(session, entry)
    return {
        "deleted": entry.id,
        "recoverable": True,
        "undo": {"tool": "restore_note", "arguments": {"note_id": entry.id}},
        "label": f"ph:trash Moved {_named(entry)} to the recycle bin",
    }


def _restore_note(session: Session, args: dict) -> dict:
    # Not `_require_note`: its whole point is refusing a *deleted* note, and
    # restoring one is exactly the case that has to reach a deleted note.
    # But its other refusal, a private note, still has to hold here.
    # Without this check a private note that had been soft-deleted could be
    # restored *and* its content read back through `_note_summary` below,
    # the same private-note bypass CLAUDE.md's own history warns about: a
    # guard quietly missing from one tool while the rest of the shape (and
    # the code review) looks correct.
    entry = manager.get_entry(session, int(args["note_id"]))
    if entry is None:
        raise ToolError(f"No note with id {args.get('note_id')}")
    if entry.is_private:
        raise ToolError(
            f"Note #{entry.id} is private, so it isn't available to the AI"
        )
    if entry.is_deleted:
        manager.restore_entry(session, entry)
    result = _note_summary(session, entry)
    result["label"] = f"ph:recycle Restored {_named(entry)} from the recycle bin"
    result["undo"] = {"tool": "delete_note", "arguments": {"note_id": entry.id}}
    return result


def _set_reminder(session: Session, args: dict) -> dict:
    """A reminder at a time the app works out (INBOX 527; AGENT_SKILLS_REFORM,
    decided 2026-09-21): `when` is the user's own words, resolved by
    `ai/when.py` against their clock; `due_at` stays as an escape hatch. Both
    without an offset mean the user's local time. Measured before: `due_at`
    "2026-10-05T09:00" was stored as 09:00 UTC, 19:00 for a user at UTC+10.
    """
    from tessellate.ai import when as when_words
    from tessellate.core.config import user_now

    text = str(args["text"]).strip()
    if not text:
        raise ToolError("The reminder text is empty")
    now = user_now(deps.get_config())
    said = str(args.get("when") or "").strip()
    exact = str(args.get("due_at") or "").strip()
    due_at = when_words.resolve(said, now) if said else None
    if due_at is None and exact:
        due_at = when_words.resolve(exact, now)
    if due_at is None:
        raise ToolError(
            f"Couldn't read '{said or exact}' as a time. Put the user's own "
            "words in `when`, like 'tomorrow at 9am', 'in 20 minutes' or "
            "'Friday evening'."
            if said or exact
            else "Say when in `when`, in the user's words, like 'tomorrow at 9am'."
        )
    if due_at < now - timedelta(minutes=1):
        raise ToolError(
            f"{due_at.strftime('%A %d %B %H:%M')} has already passed. Ask the "
            "user for a time that has not happened yet."
        )
    entry_id = args.get("note_id")
    if entry_id is not None:
        _require_note(session, {"note_id": entry_id})  # validates it exists
        entry_id = int(entry_id)
    priority = str(args.get("priority") or "normal").lower()
    if priority not in ("low", "normal", "high"):
        priority = "normal"
    reminder = Reminder(text=text, due_at=due_at, entry_id=entry_id, priority=priority)
    session.add(reminder)
    session.flush()
    manager.log_action(session, "created", "reminder", reminder.id, text[:80])
    session.commit()
    return {
        "id": reminder.id,
        "text": text,
        "due_at": due_at.isoformat(),
        #: Said back in words, so the answer repeats the app's reading of the
        #: time rather than the model's own arithmetic.
        "due": due_at.strftime("%A %d %B %Y, %H:%M"),
        "label": f"⏰ Set a reminder for {due_at.strftime('%a %d %b %Y %H:%M')}",
    }


#: What a reminder linked to a private note is called to a model and in chat:
#: its words may be the note's own (a reminder made from a selection), and a
#: private note's words never leave it (the .ics and calendar-link rule,
#: `routes_reminders._event_details`). The Reminders tab still shows them.
PRIVATE_REMINDER = "A reminder on a private note"


def private_note_ids(session: Session, ids: list) -> set[int]:
    """Which of these note ids are private (`PRIVATE_REMINDER`; the day's
    activity reads it too, `ai/activity.py`)."""
    wanted = {i for i in ids if i is not None}
    if not wanted:
        return set()
    return set(session.scalars(select(Entry.id).where(Entry.id.in_(wanted), Entry.is_private.is_(True))).all())


def _list_reminders(session: Session, args: dict) -> dict:
    """A page of reminders, soonest first, like every other list tool.

    This one read the whole table and handed all of it to the model. Its
    sibling `_list_documents` has paged since it was written, and the reason
    matters more here than in the HTTP routes: everything this returns is
    spent from the model's context window, so an unbounded list is a bill the
    answer pays before it starts. A notebook with three hundred reminders
    would have filled the window with reminders and left no room to reason
    about them.

    The `done` filter is applied in SQL rather than after the fetch, because
    filtering a page after limiting it is how "show me ten" quietly returns
    two: the rows dropped are already gone from the page.
    """
    limit = _limit_arg(args, default=DEFAULT_LIST_LIMIT)
    offset = max(0, int(args.get("offset") or 0))
    filters = [] if args.get("include_done") else [Reminder.done.is_(False)]
    total = session.scalar(select(func.count(Reminder.id)).where(*filters)) or 0
    rows = session.scalars(
        select(Reminder).where(*filters).order_by(Reminder.due_at).limit(limit).offset(offset)
    ).all()
    private = private_note_ids(session, [r.entry_id for r in rows])
    reminders = [
        {
            "id": r.id,
            "text": PRIVATE_REMINDER if r.entry_id in private else r.text,
            "due_at": r.due_at.isoformat(),
            "done": r.done,
            "note_id": r.entry_id,
        }
        for r in rows
    ]
    # The total travels with the page so the model can say "ten of three
    # hundred" rather than implying it has seen everything.
    return {
        "reminders": reminders,
        "total": total,
        "offset": offset,
        "label": f"⏰ Listed {len(reminders)} of {total} reminders",
    }


def _complete_reminder(session: Session, args: dict) -> dict:
    reminder = session.get(Reminder, int(args["reminder_id"]))
    if reminder is None:
        raise ToolError(f"No reminder with id {args.get('reminder_id')}")
    done = bool(args.get("done", True))
    if reminder.done != done:
        reminder.done = done
        manager.log_action(
            session, "edited", "reminder", reminder.id, "done" if done else "reopened"
        )
        session.commit()
    return {
        "id": reminder.id,
        "done": done,
        "label": f"ph:check-circle Marked reminder #{reminder.id} {'done' if done else 'not done'}",
    }


def _rename_tag(session: Session, args: dict) -> dict:
    try:
        changed = len(tags_repo.rename(session, [str(args["old"])], str(args["new"])))
        session.commit()
    except ValueError as exc:
        # A blank new name: told to the model as a tool error it can fix,
        # not raised as a crash of the whole turn.
        raise ToolError(str(exc)) from exc
    return {
        "entries_changed": changed,
        "label": f"ph:tag Renamed tag “{args['old']}” → “{args['new']}” ({changed} notes)",
        "undo": {"tool": "rename_tag", "arguments": {"old": str(args["new"]), "new": str(args["old"])}},
    }


def _delete_tag(session: Session, args: dict) -> dict:
    changed = len(tags_repo.remove(session, [str(args["name"])]))
    session.commit()
    return {
        "entries_changed": changed,
        "label": f"ph:tag Removed the tag “{args['name']}” from {changed} notes",
    }
