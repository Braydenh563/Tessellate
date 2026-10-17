"""Every agent tool's result said the way the composer says things.

The owner, 2026-10-11: "make sure needle tool calls are properly outputted in
human readable ways and well structured and written ways by the composer when
the ai isnt available." needle (`ai/needle_provider.py`) picks tools and
writes no prose, so once its tools have run the reply is what they returned,
and before this module most of that was a label ("ph:folder Created the
category") or a generic "Done.". Each of the registry's tools is said here:

- a lead sentence that answers ("I found two notes about harbor launch.");
- the result in a shape that reads: a list, a table with its counts, or the
  note quoted;
- a link to every note, document, board or screen it names, as an app
  address (`#/notes/12`), which the Markdown renderer opens in place
  (`appAddressHash`, router.js);
- the next thing to tap where one helps ("Open it", "Show all notes");
- a failure as a plain sentence and the next step, never the raw error.

Nothing here is JSON, an argument name or a tool's name; the gold check is
`tests/test_tool_say.py`, which runs every tool's real result (and a failure
for each) through `say`.
"""

from __future__ import annotations

import re
from collections.abc import Callable
from datetime import date, datetime

from tessellate.ai.realise import count_noun, cut_title, join_items

#: An app address for each kind of thing a tool names (router.js
#: `ROUTE_OBJECTS`, `ROUTE_TABS`, `ROUTE_LIBRARY`).
NOTES = "#/notes"
REMINDERS = "#/reminders"
GRAPH = "#/graph"
BOARDS = "#/library/boards"
SKILLS = "#/library/skills"
FILES = "#/library/files"
DOCUMENTS = "#/docs"
CHATS = "#/chat"


def note_at(note_id: object) -> str:
    return f"#/notes/{int(note_id)}" if _number(note_id) else NOTES


def document_at(document_id: object) -> str:
    return f"#/docs/{int(document_id)}" if _number(document_id) else DOCUMENTS


def board_at(board_id: object) -> str:
    return f"#/library/board/{int(board_id)}" if _number(board_id) else BOARDS


def settings_at(section: str) -> str:
    return f"#/settings/{section}"


def _number(value: object) -> bool:
    return isinstance(value, int) and not isinstance(value, bool) or (isinstance(value, str) and value.isdigit())


def link(label: str, address: str) -> str:
    """A Markdown link whose words cannot close it early."""
    words = re.sub(r"[\[\]]", "", str(label)).strip() or "Open"
    return f"[{words}]({address})"


def _title(content: object, size: int = 60) -> str:
    lines = [ln.strip() for ln in str(content or "").splitlines() if ln.strip()]
    if not lines:
        return "Untitled"
    #: A title written with inline Markdown ("**Plan**") is shown as words:
    #: the link text is not rendered a second time.
    plain = re.sub(r"(\*\*|__|~~|\*|`)(.+?)\1", r"\2", lines[0].lstrip("#").strip())
    return cut_title(plain.strip("*_`~ ") or "Untitled", size)


def _gist(text: object, size: int = 90) -> str:
    """A note's first line after its heading: what a list row says of it."""
    lines = [ln.strip() for ln in str(text or "").splitlines() if ln.strip()]
    body = [ln for ln in lines[1:] if not ln.startswith(("#", "!["))]
    first = re.sub(r"^(?:[-*+]\s+(?:\[[ xX]\]\s+)?|\d+[.)]\s+)", "", body[0]) if body else ""
    first = re.sub(r"[*_`]", "", first).strip()
    return cut_title(first, size) if first else ""


def _note_row(note: dict, extra: str = "") -> str:
    """One note as a list row: its title linked, its first line, where it
    is filed."""
    text = note.get("content") or note.get("preview") or note.get("title") or ""
    filed = note.get("category")
    tags = [str(t) for t in note.get("tags") or []]
    gist = _gist(text) if note.get("content") else ""
    where = f": {gist}" if gist else ""
    where += f" · {filed}" if filed else ""
    where += f" · {', '.join('#' + t for t in tags[:3])}" if tags else ""
    return f"- {link(_title(text), note_at(note.get('id') or note.get('note_id')))}{where}{extra}"


def _table(headers: list[str], rows: list[list[str]]) -> str:
    def cell(value: object) -> str:
        return str(value).replace("|", "/").replace("\n", " ").strip()

    head = "| " + " | ".join(headers) + " |"
    rule = "| " + " | ".join("---" for _ in headers) + " |"
    return "\n".join([head, rule, *("| " + " | ".join(cell(v) for v in row) + " |" for row in rows)])


def _chips(*pairs: tuple[str, str]) -> str:
    return " · ".join(link(label, address) for label, address in pairs if address)


def _quoted(text: str, size: int = 400) -> str:
    """The words as a quote, a line of the quote per line of the text."""
    lines = [" ".join(ln.split()) for ln in str(text or "").splitlines() if ln.strip()]
    kept, used = [], 0
    for line in lines:
        if used + len(line) > size:
            kept.append(cut_title(line, max(20, size - used)))
            break
        kept.append(line)
        used += len(line)
    return "\n".join(f"> {ln}" for ln in kept)


def _when(raw: object) -> str:
    """"Monday 12 October at 9am" from an ISO time; "" when unreadable."""
    try:
        moment = datetime.fromisoformat(str(raw))
    except ValueError:
        return ""
    clock = f"{moment.hour % 12 or 12}{f':{moment.minute:02d}' if moment.minute else ''}{'am' if moment.hour < 12 else 'pm'}"
    return f"{moment.strftime('%A')} {moment.day} {moment.strftime('%B')} at {clock}"


def _plain(label: object) -> str:
    """A tool's own label as words: the icon name off, note numbers named."""
    text = re.sub(r"^(?:ph:[\w-]+|[^\w\s“\"']+)\s*", "", str(label or "")).strip()
    text = re.sub(r"#(\d+)", r"note \1", text)
    text = text.replace("→", "to")
    return text


def _sentence(text: str) -> str:
    text = text.strip()
    if not text:
        return ""
    text = text[0].upper() + text[1:]
    return text if text[-1] in ".?:" else text + "."


Said = tuple[str, str, str]


def _found_notes(lead: str, notes: list[dict], total: int, empty: str, more_at: str = NOTES, limit: int = 8) -> Said:
    if not notes:
        return empty, "", _chips(("Open your notes", NOTES))
    rows = [_note_row(n) for n in notes[:limit]]
    shown = min(len(notes), limit)
    more = f" Here are the first {count_noun(shown, 'note').split(' ', 1)[0]}." if total > shown and " of " not in lead else ""
    chips = [("Open it" if len(notes) == 1 else "Open the first one", note_at(notes[0].get("id") or notes[0].get("note_id")))]
    if total > shown:
        chips.append(("Show all notes", more_at))
    return lead + more, "\n".join(rows), _chips(*chips)


# --- reading -------------------------------------------------------------------


def _time(result: dict, args: dict) -> Said:
    place = result.get("place")
    human = str(result.get("human") or "").strip()
    return (f"It is {human} in {place}." if place else f"It is {human}."), "", ""


def _calculate(result: dict, args: dict) -> Said:
    answer = _sentence(str(result.get("answer") or ""))
    read = str(result.get("read_as") or "").strip()
    return answer, (f"I read the question as {read}." if read and read not in answer else ""), ""


def _count(result: dict, args: dict) -> Said:
    n = int(result.get("count") if result.get("count") is not None else result.get("total") or 0)
    what = []
    if result.get("tag") or args.get("tag"):
        what.append(f"tagged #{result.get('tag') or args.get('tag')}")
    if result.get("category") or args.get("category"):
        what.append(f"in {result.get('category') or args.get('category')}")
    if args.get("untagged"):
        what.append("with no tags")
    if args.get("since"):
        what.append(f"since {args['since']}")
    lead = f"You have {count_noun(n, 'note')}" + (" " + " ".join(what) if what else "") + "."
    per = result.get("by_category") or {}
    body = _table(["Category", "Notes"], [[k, v] for k, v in per.items()]) if len(per) > 1 else ""
    return lead, body, _chips(("Open your notes", NOTES))


def _filed_lead(notes: list[dict], shown: str, filed: str, tag: str) -> str:
    """"Here are your two Work notes, newest first" (ledger row 442)."""
    if len(notes) > 1:
        lead = f"Here are your {shown} {filed} notes" if filed else f"Here are your {shown} notes tagged #{tag}"
        return lead + ", newest first"
    return f"Here is your {filed} note" if filed else f"Here is your note tagged #{tag}"


def _category_named(notes: list[dict], filed: str) -> str:
    """The category as the notebook spells it ("Work" for "work")."""
    if not filed:
        return ""
    return next((str(n["category"]) for n in notes if str(n.get("category") or "").lower() == filed.lower()), filed)


def _list_notes(result: dict, args: dict) -> Said:
    notes = [n for n in result.get("notes") or [] if isinstance(n, dict)]
    total = int(result.get("total_matching") or result.get("total") or len(notes))
    shown = count_noun(min(len(notes), 8), "note").split(" ", 1)[0]
    filed = _category_named(notes, str(args.get("category") or result.get("category") or "").strip())
    tag = str(args.get("tag") or "").strip().lstrip("#")
    if filed or tag:
        lead = _filed_lead(notes, shown, filed, tag)
    else:
        lead = f"Here are your {shown} newest notes" if len(notes) > 1 else "Here is your newest note"
    lead += f", of {count_word_of(total)} in all." if total > len(notes[:8]) else "."
    return _found_notes(lead, notes, total, "You have no notes that fit yet.")


def _search_notes(result: dict, args: dict) -> Said:
    notes = [n for n in result.get("notes") or [] if isinstance(n, dict) and not n.get("why")]
    #: The words searched for: the call's own, else its label's quote
    #: ("Searched notes for “dentist”").
    said = re.search(r"“([^”]+)”", str(result.get("label") or ""))
    query = str(args.get("query") or (said.group(1) if said else "")).strip()
    about = f" about “{query}”" if query else ""
    total = int(result.get("found") or len(notes))
    if result.get("search_mode") == "recent":
        newest = f"your {count_word_of(len(notes))} newest notes" if len(notes) > 1 else "your newest note"
        lead = f"Nothing matched “{query}”, so here are {newest} instead." if query else f"Here are {newest}."
        return _found_notes(lead, notes, total, f"I found no notes{about}.")
    return _found_notes(f"I found {count_noun(total, 'note')}{about}.", notes, total, f"I found no notes{about}. Try other words, or browse them in Notes.")


def _filed_where(result: dict) -> str:
    """" It is in Admin, tagged #health": where a note is kept."""
    filed = result.get("category")
    tags = [str(t) for t in result.get("tags") or []]
    return (f" It is in {filed}" if filed else "") + (f", tagged {join_items(['#' + t for t in tags])}" if tags else "")


def _get_note(result: dict, args: dict) -> Said:
    title = _title(result.get("content"))
    where = _filed_where(result)
    one_line = len([ln for ln in str(result.get("content") or "").splitlines() if ln.strip()]) <= 1
    lead = ("Here is the note." if one_line else f"Here is {link(title, note_at(result.get('id')))}.") + (where + "." if where else "")
    linked = [row for row in result.get("links") or [] if isinstance(row, dict)]
    body = _quoted(result.get("content") or "", 600)
    if linked:
        body += "\n\nLinked to:\n" + "\n".join(_note_row(row) for row in linked[:5])
    return lead, body, _chips(("Open it", note_at(result.get("id"))), ("See it on the graph", f"#/graph/focus/{int(result['id'])}" if _number(result.get("id")) else ""))


def _similar(result: dict, args: dict) -> Said:
    found = [n for n in result.get("similar") or [] if isinstance(n, dict)]
    of = note_at(result.get("note_id") or args.get("note_id"))
    if not found:
        return f"No other note is close to {link('that note', of)} and not already linked to it.", "", _chips(("Open the note", of))
    return (f"{count_noun(len(found), 'note').capitalize()} read like {link('that note', of)} and are not linked to it yet.",
            "\n".join(_note_row(n) for n in found[:8]), _chips(("Open the note", of)))


def _related(result: dict, args: dict) -> Said:
    found = [n for n in result.get("related") or [] if isinstance(n, dict)]
    of = note_at(result.get("note_id") or args.get("note_id"))
    if not found:
        return f"Nothing is connected to {link('that note', of)} yet.", "", _chips(("Open the note", of))
    rows = [_note_row(n, f" ({n['how']})" if n.get("how") else "") for n in found[:8]]
    return (f"{count_noun(len(found), 'note').capitalize()} {'is' if len(found) == 1 else 'are'} connected to {link('that note', of)}.",
            "\n".join(rows), _chips(("Open the note", of), ("See them on the graph", f"#/graph/focus/{int(args['note_id'])}" if _number(args.get("note_id")) else GRAPH)))


def _path(result: dict, args: dict) -> Said:
    steps = [n for n in result.get("path") or [] if isinstance(n, dict)]
    if not result.get("found") or not steps:
        return "Those two notes are not connected, not even through other notes.", "", _chips(("Open the graph", GRAPH))
    hops = int(result.get("hops") or len(steps) - 1)
    lead = "Those two notes are linked directly." if hops == 1 else f"Those two notes connect in {count_noun(hops, 'step')}."
    body = "\n".join(f"{i}. {link(_title(s.get('preview')), note_at(s.get('id')))}" for i, s in enumerate(steps, 1))
    return lead, body, _chips(("See it on the graph", f"#/graph/focus/{int(steps[0]['id'])}" if _number(steps[0].get("id")) else GRAPH))


def _contradictions(result: dict, args: dict) -> Said:
    found = [t for t in result.get("tensions") or [] if isinstance(t, dict)]
    if not found:
        message = str(result.get("message") or "")
        if "model" in message:
            return "Finding where notes disagree needs a model to read them, and none is running.", "Start one in Settings, Models, then ask again.", _chips(("Open Settings, Models", settings_at("models")))
        return "I found no notes that disagree with each other.", "", _chips(("Open the graph", GRAPH))
    rows = []
    for t in found[:5]:
        earlier, later = note_at(t.get("earlier_note_id")), note_at(t.get("later_note_id"))
        rows.append(f"- {_sentence(str(t.get('what_they_disagree_about') or 'They disagree'))} {link('Earlier note', earlier)}, {link('later note', later)}")
    return f"I found {count_noun(len(found), 'place')} where your notes disagree.", "\n".join(rows), ""


def _summary(result: dict, args: dict) -> Said:
    notes = [n for n in result.get("notes") or [] if isinstance(n, dict)]
    period = str(result.get("period") or "lately")
    #: "all time" is no window: "In the all time you wrote four notes" was
    #: the needle path's summary (O1 probe, 2026-10-17).
    whole = period in ("all time", "lately")
    n = int(result.get("count") or len(notes))
    if not notes:
        empty = "You have no notes yet." if whole else f"You wrote no notes in the {period}."
        return empty, "", _chips(("Open your notes", NOTES))
    kinds: dict[str, int] = {}
    for note in notes:
        kinds[str(note.get("category") or "Uncategorised")] = kinds.get(str(note.get("category") or "Uncategorised"), 0) + 1
    top = sorted(kinds.items(), key=lambda kv: -kv[1])
    said = f"You have {count_noun(n, 'note')}" if whole else f"In the {period} you wrote {count_noun(n, 'note')}"
    lead = f"{said}, most in {top[0][0]}." if len(top) > 1 else f"{said}, all in {top[0][0]}."
    body = _table(["Category", "Notes"], [[k, v] for k, v in top]) + "\n\n" + "\n".join(_note_row(x) for x in notes[:6])
    return lead, body, _chips(("Open your notes", NOTES))


def _named_counts(key: str, noun: str) -> Callable[[dict, dict], Said]:
    def say(result: dict, args: dict) -> Said:
        rows = [r for r in result.get(key) or [] if isinstance(r, dict)]
        if not rows:
            return f"You have no {key} yet.", "", _chips(("Open your notes", NOTES))
        rows = sorted(rows, key=lambda r: -int(r.get("notes") or 0))
        first = rows[0]
        lead = f"You have {count_noun(len(rows), noun)}; {first.get('name')} has the most notes ({first.get('notes')})."
        shown = [[("#" if noun == "tag" else "") + str(r.get("name")), r.get("notes")] for r in rows[:15]]
        more = f"\n\nAnd {len(rows) - 15} more." if len(rows) > 15 else ""
        return lead, _table([noun.capitalize(), "Notes"], shown) + more, _chips(("Open your notes", NOTES))
    return say


def _overview(result: dict, args: dict) -> Said:
    total = int(result.get("total_notes") or 0)
    cats = [c for c in result.get("categories") or [] if isinstance(c, dict)]
    tags = [t for t in result.get("tags") or [] if isinstance(t, dict)]
    lead = f"Your notebook holds {count_noun(total, 'note')} in {count_noun(len(cats), 'category')}, with {count_noun(len(tags), 'tag')}."
    body = _table(["Category", "Notes"], [[c.get("name"), c.get("notes")] for c in cats[:10]])
    if tags:
        body += "\n\nMost used tags: " + join_items([f"#{t.get('name')} ({t.get('notes')})" for t in tags[:5]]) + "."
    return lead, body, _chips(("Open your notes", NOTES), ("Open the graph", GRAPH))


def _structure(result: dict, args: dict) -> Said:
    notes, connected = int(result.get("notes") or 0), int(result.get("connected") or 0)
    lone = [o for o in result.get("orphans") or [] if isinstance(o, dict)]
    lead = f"Of your {count_noun(notes, 'note')}, {count_word_of(connected)} {'is' if connected == 1 else 'are'} connected to others, in {count_noun(int(result.get('cluster_count') or 0), 'group')}."
    body = _table(["Notes", "Connected", "Groups", "On their own"], [[notes, connected, result.get("cluster_count") or 0, result.get("orphan_count") or 0]])
    hubs = [h for h in result.get("hubs") or [] if isinstance(h, dict)]
    return lead, body + _rows_under("Most connected", hubs) + _rows_under("Not linked to anything yet", lone), _chips(("Open the graph", GRAPH))


def _rows_under(heading: str, notes: list[dict]) -> str:
    return f"\n\n{heading}:\n" + "\n".join(_note_row(n) for n in notes[:5]) if notes else ""


def count_word_of(n: int) -> str:
    return count_noun(n, "x").rsplit(" ", 1)[0]


def _documents(result: dict, args: dict) -> Said:
    docs = [d for d in result.get("documents") or [] if isinstance(d, dict)]
    total = int(result.get("total_matching") or len(docs))
    if not docs:
        return "You have no documents" + (f" about “{args['query']}”." if args.get("query") else " yet."), "", _chips(("Open Documents", DOCUMENTS))
    rows = [[link(d.get("title") or "Untitled", document_at(d.get("id"))), f"{d.get('words') or 0} words"] for d in docs[:10]]
    lead = f"You have {count_noun(total, 'document')}" + (", newest first." if total > 1 else ".")
    chips = [("Open " + cut_title(str(docs[0].get("title") or "it"), 30), document_at(docs[0].get("id")))]
    if result.get("has_more"):
        chips.append(("Show all documents", DOCUMENTS))
    return lead, _table(["Document", "Length"], rows), _chips(*chips)


def _get_document(result: dict, args: dict) -> Said:
    title = str(result.get("title") or "Untitled")
    at = document_at(result.get("id") or args.get("document_id"))
    lead = f"Here is {link(title, at)}, {count_noun(int(result.get('words') or 0), 'word')}."
    return lead, _quoted(re.sub(r"^#+\s*", "", str(result.get("content") or ""), flags=re.M), 600), _chips(("Open it", at))


def _reminders(result: dict, args: dict) -> Said:
    rows = [r for r in result.get("reminders") or [] if isinstance(r, dict) and (args.get("include_done") or not r.get("done"))]
    if not rows:
        return "You have no reminders waiting.", "", _chips(("Open Reminders", REMINDERS))
    table = _table(["Reminder", "When"], [[r.get("text"), _when(r.get("due_at"))] for r in rows[:12]])
    return f"You have {count_noun(len(rows), 'reminder')} waiting.", table, _chips(("Open Reminders", REMINDERS))


def _skills(result: dict, args: dict) -> Said:
    if "tools" in result or result.get("example") is not None:
        return _tools(result, args)
    rows = [s for s in result.get("skills") or [] if isinstance(s, dict)]
    if not rows:
        return "You have no skills yet.", "", _chips(("Open Skills", SKILLS))
    table = _table(["Skill", "When to use it"], [[s.get("name"), cut_title(str(s.get("when_to_use") or s.get("description") or ""), 80)] for s in rows[:12]])
    return f"You have {count_noun(len(rows), 'skill')}.", table, _chips(("Open Skills", SKILLS))


def _help(result: dict, args: dict) -> Said:
    text = str(result.get("guide_text") or "")
    rows = [ln.lstrip("- ").strip() for ln in text.splitlines() if ln.strip().startswith("- ")]
    if not rows:
        return "The help has nothing on that.", "", _chips(("Open Help", settings_at("help")))
    first = rows[0].split(":", 1)
    lead = f"From the app's help, on {first[0].strip().lower()}:" if len(first) == 2 else "From the app's help:"
    #: The sentence that answers the asking, the one Chat's help register
    #: leads with (`composer.help_line`), before the topic's opening.
    answer = str(result.get("answer") or "").strip()
    if answer:
        return f"{lead} {answer}", "", _chips(("Open Help", settings_at("help")))
    body = "\n\n".join(cut_title(r.split(":", 1)[1].strip() if ":" in r else r, 320) for r in rows[:2])
    return lead, body, _chips(("Open Help", settings_at("help")))


_GROUP_WORDS = {"read": "reads", "write": "changes notes", "confirm": "asks first", "online": "goes online"}


def _tool_name(name: object) -> str:
    """A tool's name as words ("search_notes" is "Search notes"), B48: a
    tool is named for the person, never by its identifier."""
    said = str(name or "").replace("_", " ").strip()
    return said[:1].upper() + said[1:]


def _tools(result: dict, args: dict) -> Said:
    """`list_tools` (O10): how many, then a table of what each does; with a
    name, that one tool and a call to copy."""
    if result.get("example") is not None:
        return _tool_described(result, args)
    rows = [r for r in result.get("tools") or [] if isinstance(r, dict)]
    if not rows:
        return "No tool matches that.", "", _chips(("Open Settings, Tools it can use", settings_at("tools")))
    off = sum(1 for r in rows if not r.get("enabled", True))
    lead = f"I have {count_noun(len(rows), 'tool')}" + (f", {count_word_of(off)} of them turned off in Settings" if off else "") + "."
    body = _table(["Tool", "What it does", "Kind"], [[_tool_name(r.get("name")), _plain(r.get("does")), _GROUP_WORDS.get(str(r.get("group")), "")]
                                                     for r in rows[:30]])
    return lead, body, _chips(("Open Settings, Tools it can use", settings_at("tools")))


def _tool_described(result: dict, args: dict) -> Said:
    """One tool (O10): what it does, then what it takes, in words (the call
    itself, JSON, is the model's: `example` in the result)."""
    name = _tool_name(result.get("name"))
    state = "" if result.get("enabled", True) else " It is turned off in Settings, Tools it can use."
    lead = f"{name} is one of my tools. {_sentence(str(result.get('description') or ''))}{state}"
    schema = result.get("parameters") if isinstance(result.get("parameters"), dict) else {}
    takes = list((schema.get("properties") or {}).keys())
    needed = [k for k in schema.get("required") or [] if k in takes]
    body = f"It takes {join_items(takes)}" + (f", and needs {join_items(needed)}." if needed else ".") if takes else "It takes nothing."
    return lead, body, _chips(("Open Settings, Tools it can use", settings_at("tools")))


def _chat_history(result: dict, args: dict) -> Said:
    found = [c for c in result.get("conversations") or [] if isinstance(c, dict)]
    about = f" about “{args['query']}”" if args.get("query") else ""
    if not found:
        return f"No earlier chat mentions that{about and ''}." if not about else f"No earlier chat was{about}.", "", _chips(("Open Chat", CHATS))
    rows = [_chat_row(c) for c in found[:6]]
    return f"I found {count_noun(len(found), 'earlier chat')}{about}.", "\n".join(rows), ""


def _chat_row(chat: dict) -> str:
    excerpt = next((e.get("text") for e in chat.get("excerpts") or [] if isinstance(e, dict) and e.get("text")), "")
    at = f"#/chat/{int(chat['id'])}" if _number(chat.get("id")) else CHATS
    return f"- {link(chat.get('title') or 'A chat', at)}" + (f": {cut_title(str(excerpt), 90)}" if excerpt else "")


def _files(result: dict, args: dict) -> Said:
    found = [f for f in result.get("files") or [] if isinstance(f, dict)]
    about = f" matching “{args['query']}”" if args.get("query") else ""
    if not found:
        return f"No file{about} was found.", "", _chips(("Open Files", FILES))
    rows = []
    for f in found[:8]:
        where = f" (on {link('its note', note_at(f['attached_to_note']))})" if _number(f.get("attached_to_note")) else ""
        said = cut_title(str(f.get("caption") or f.get("text") or ""), 90)
        rows.append(f"- **{f.get('name') or 'A file'}**{where}" + (f": {said}" if said else ""))
    return f"I found {count_noun(len(found), 'file')}{about}.", "\n".join(rows), _chips(("Open Files", FILES))


def _read_file(result: dict, args: dict) -> Said:
    name = str(result.get("name") or "The file")
    text = str(result.get("text") or result.get("content") or "")
    if not text.strip():
        return f"{name} has no readable text.", "", _chips(("Open Files", FILES))
    return f"Here is what {name} says.", _quoted(text, 700), _chips(("Open Files", FILES))


def _read_text(result: dict, args: dict) -> Said:
    found = [r for r in result.get("read") or [] if isinstance(r, dict)]
    if not found:
        return "I found no dates, amounts or names in that.", "", ""
    rows = [[f"“{r.get('said')}”", _sentence(str(r.get("read_as") or "")).rstrip(".")] for r in found]
    return f"I read {count_noun(len(found), 'thing')} in it.", _table(["Said", "Read as"], rows), ""


def _whiteboard(result: dict, args: dict) -> Said:
    title = str(result.get("board_title") or "the board")
    at = board_at(result.get("board_id"))
    cards = [c for c in result.get("cards") or [] if isinstance(c, dict)]
    shapes = [s for s in result.get("shapes") or [] if isinstance(s, dict)]
    links = result.get("links") or []
    parts = [count_noun(len(cards), "card"), count_noun(len(shapes), "shape"), count_noun(len(links), "link")]
    lead = f"{link(title, at)} has {join_items(parts)}."
    rows = [_note_row({"id": c.get("note_id"), "content": c.get("preview")}) for c in cards[:8]]
    rows += [f"- A {_SHAPE_WORDS.get(str(s.get('shape')), 'shape')}: {s.get('text')}" for s in shapes[:5] if s.get("text")]
    return lead, "\n".join(rows), _chips(("Open the board", at))


def _search_board(result: dict, args: dict) -> Said:
    found = [m for m in result.get("matches") or [] if isinstance(m, dict)]
    about = f" for “{args['query']}”" if args.get("query") else ""
    if not found:
        return f"Nothing on your boards matched{about}.", "", _chips(("Open Boards", BOARDS))
    rows = [_note_row({"id": m.get("note_id"), "content": m.get("preview") or m.get("text")}) for m in found[:8]]
    named = f" “{args['query']}”" if args.get("query") else ""
    return f"{count_noun(len(found), 'card').capitalize()} on your boards {'matches' if len(found) == 1 else 'match'}{named}.", "\n".join(rows), _chips(("Open the board", board_at(found[0].get("board_id"))))


def _mindmap(result: dict, args: dict) -> Said:
    title = str(result.get("board_title") or "The map")
    at = board_at(result.get("board_id") or args.get("board_id"))
    outline = [re.sub(r"\s*\[id \d+\]", "", ln) for ln in str(result.get("outline") or "").splitlines()[1:]]
    lead = f"{link(title, at)} has {count_noun(int(result.get('node_count') or len(outline)), 'idea')}."
    return lead, "\n".join(outline[:20]), _chips(("Open the map", at))


def _library(result: dict, args: dict) -> Said:
    items = [i for i in result.get("items") or [] if isinstance(i, dict)]
    if not items:
        return "The shape library has nothing" + (f" for “{args['query']}”." if args.get("query") else "."), "", _chips(("Open Boards", BOARDS))
    sets: dict[str, list[str]] = {}
    for item in items:
        sets.setdefault(str(item.get("set") or "other").replace("-", " "), []).append(str(item.get("name")))
    rows = [[name.capitalize(), len(names), cut_title("; ".join(names[:3]), 70)] for name, names in sets.items()]
    return f"The shape library has {count_noun(len(items), 'shape')} in {count_noun(len(sets), 'set')}.", _table(["Set", "Shapes", "For example"], rows[:12]), _chips(("Open Boards", BOARDS))


def _check(result: dict, args: dict) -> Said:
    missing = [str(x) for x in result.get("unsourced") or []]
    if result.get("ok") or not missing:
        return "Every fact in that answer is in the notes it cites.", "", ""
    return f"The notes cited do not say {join_items(['“' + m + '”' for m in missing])}.", "That part of the answer needs a source, or should go.", ""


def _propose(result: dict, args: dict) -> Said:
    line = _sentence(str(result.get("line") or (result.get("act_card") or {}).get("label") or "Ready"))
    return line, "Nothing changes until you confirm it on the card, and Undo takes it back.", ""


def _web(result: dict, args: dict) -> Said:
    found = [r for r in result.get("results") or [] if isinstance(r, dict)]
    query = str(args.get("query") or "")
    if not found:
        return f"The web search for “{query}” found nothing.", "", ""
    rows = [f"- {link(r.get('title') or r.get('url'), str(r.get('url') or ''))}" + (f": {cut_title(str(r.get('snippet') or ''), 120)}" if r.get("snippet") else "") for r in found[:5] if str(r.get("url") or "").startswith("http")]
    return f"I found {count_noun(len(rows), 'web result')} for “{query}”.", "\n".join(rows), ""


def _read_url(result: dict, args: dict) -> Said:
    title = str(result.get("title") or result.get("domain") or "The page")
    url = str(result.get("url") or args.get("url") or "")
    lead = f"{link(title, url) if url.startswith('http') else title} says:"
    return lead, _quoted(str(result.get("text") or ""), 700), ""


# --- writing -------------------------------------------------------------------


def _created_note(result: dict, args: dict) -> Said:
    at = note_at(result.get("id"))
    filed = result.get("category")
    tags = [str(t) for t in result.get("tags") or []]
    where = (f" in {filed}" if filed else "") + (f", tagged {join_items(['#' + t for t in tags])}" if tags else "")
    return f"Saved a new note{where}: {link(_title(result.get('content')), at)}.", "", _chips(("Open it", at))


def _edited_note(result: dict, args: dict) -> Said:
    at = note_at(result.get("id") or args.get("note_id"))
    changed = [str(c) for c in result.get("changed") or []]
    tags = [str(t) for t in result.get("tags") or []]
    said = []
    if "tags" in changed:
        said.append(f"its tags are now {join_items(['#' + t for t in tags])}" if tags else "it has no tags now")
    if "category" in changed:
        said.append(f"it is filed in {result.get('category')}")
    if "content" in changed:
        said.append("its text is updated")
    detail = f": {join_items(said)}" if said else ""
    return f"Updated {link(_title(result.get('content')), at)}{detail}.", "", _chips(("Open it", at))


def _tagged(result: dict, args: dict) -> Said:
    ids = [i for i in result.get("tagged") or [] if _number(i)]
    added, removed = [str(t) for t in args.get("add") or []], [str(t) for t in args.get("remove") or []]
    change = []
    if added:
        change.append(f"added {join_items(['#' + t for t in added])}")
    if removed:
        change.append(f"took off {join_items(['#' + t for t in removed])}")
    lead = f"Retagged {count_noun(len(ids), 'note')}" + (f": {join_items(change)}." if change else ".")
    body = "\n".join(f"- {link(f'Note {i}', note_at(i))}" for i in ids[:10])
    return lead, body, _chips(("Open the first one", note_at(ids[0])) if ids else ("Open your notes", NOTES))


def _pinned(result: dict, args: dict) -> Said:
    if not _number(result.get("id") or args.get("note_id")) and result.get("label"):
        return _sentence(_plain(result["label"])), "", ""
    at = note_at(result.get("id") or args.get("note_id"))
    on = result.get("pinned", args.get("pinned", True))
    lead = f"{'Added' if on else 'Took'} {link(_title(result.get('content')), at)} {'to' if on else 'out of'} Favourites."
    return lead, "", _chips(("Open it", at))


def _linked(result: dict, args: dict) -> Said:
    ids = [i for i in result.get("linked") or result.get("unlinked") or [] if _number(i)]
    joined = " and ".join(link(f"note {i}", note_at(i)) for i in ids[:2])
    if result.get("unlinked") is not None:
        return f"Unlinked {joined}.", "", _chips(("Open the graph", GRAPH))
    reason = args.get("reason")
    more = f" ({count_noun(len(ids) - 1, 'other note')})" if len(ids) > 2 else ""
    return f"Linked {joined}{more}" + (f", because {reason}." if reason else "."), "", _chips(("See it on the graph", f"#/graph/focus/{int(ids[0])}" if ids else GRAPH))


def _audit(result: dict, args: dict) -> Said:
    n = int(result.get("updated") or 0)
    if not n:
        return "Every link already says why it is there; I changed none.", "", _chips(("Open the graph", GRAPH))
    return f"Rewrote the reasons on {count_noun(n, 'link')} to say why the notes connect.", "", _chips(("Open the graph", GRAPH))


def _category(result: dict, args: dict) -> Said:
    moved = int(result.get("notes_moved") or 0)
    notes = count_noun(moved, "note")
    if "from" in args and "into" in args:
        tail = f"; {notes} moved." if moved else "; no notes needed moving."
        return f"Merged “{args['from']}” into “{args['into']}”{tail}", "", _chips(("Open your notes", NOTES))
    if "name" in args and "created" not in result:
        tail = f"; {'its' if moved == 1 else 'their'} {notes} {'is' if moved == 1 else 'are'} now Uncategorised." if moved else "; it held no notes."
        return f"Deleted the category “{args['name']}”{tail}", "", _chips(("Open your notes", NOTES))
    return _sentence(_plain(result.get("label"))), "", _chips(("Open your notes", NOTES))


def _tag(result: dict, args: dict) -> Said:
    n = int(result.get("entries_changed") or 0)
    if args.get("old"):
        return f"Renamed #{args['old']} to #{args.get('new')} on {count_noun(n, 'note')}.", "", _chips(("Open your notes", NOTES))
    return f"Took #{args.get('name')} off {count_noun(n, 'note')}.", "", _chips(("Open your notes", NOTES))


def _created_document(result: dict, args: dict) -> Said:
    at = document_at(result.get("id"))
    return f"Created the document {link(result.get('title') or 'Untitled', at)}, {count_noun(int(result.get('words') or 0), 'word')}.", "", _chips(("Open it", at))


def _deleted_document(result: dict, args: dict) -> Said:
    return f"Deleted the document “{result.get('title') or 'Untitled'}”.", "", _chips(("Open Documents", DOCUMENTS))


def _mindmap_made(result: dict, args: dict) -> Said:
    at = board_at(result.get("board_id"))
    return f"Made the mind map {link(result.get('title') or args.get('title') or 'Untitled', at)}" + (f", starting from “{args['root_text']}”." if args.get("root_text") else "."), "", _chips(("Open the map", at))


def _map_from_note(result: dict, args: dict) -> Said:
    at = board_at(result.get("board_id"))
    nodes = int(result.get("nodes") or 0)
    return f"Made the mind map {link(result.get('title') or 'Untitled', at)} from the note, {count_noun(nodes, 'idea')}.", "", _chips(("Open the map", at))


def _moved(result: dict, args: dict) -> Said:
    moved = int(result.get("moved") or 0)
    where = f"the category “{result['category']}”" if result.get("category") else f"the space “{result.get('space') or 'you named'}”"
    if not moved:
        return f"Those notes are already in {where}.", "", _chips(("Open your notes", NOTES))
    return f"Moved {count_noun(moved, 'note')} to {where}.", "", _chips(("Open your notes", NOTES))


def _map_node(result: dict, args: dict) -> Said:
    at = board_at(result.get("board_id") or args.get("board_id"))
    return f"Added “{result.get('text') or args.get('text') or 'an idea'}” to {link('the map', at)}.", "", _chips(("Open the map", at))


def _map_link(result: dict, args: dict) -> Said:
    at = board_at(result.get("board_id") or args.get("board_id"))
    named = result.get("label_text") or args.get("label")
    return f"Joined two ideas on {link('the map', at)}" + (f", labelled “{named}”." if named else "."), "", _chips(("Open the map", at))


def _board_card(result: dict, args: dict) -> Said:
    at = board_at(args.get("board_id"))
    note = note_at(result.get("note_id") or args.get("note_id"))
    title = re.sub(r"^.*?“(.+?)”.*$", r"\1", _plain(result.get("label"))) if "“" in str(result.get("label")) else "the note"
    return f"Put {link(title, note)} on {link('the board', at)}.", "", _chips(("Open the board", at))


_SHAPE_WORDS = {"rect": "rectangle", "ellipse": "ellipse", "diamond": "diamond", "frame": "frame"}


def _board_write(verb: str) -> Callable[[dict, dict], Said]:
    def say(result: dict, args: dict) -> Said:
        at = board_at(args.get("board_id") or result.get("board_id"))
        said = re.sub(r"\b(?:a|the) rect\b", lambda m: m.group(0)[:-4] + "rectangle", _plain(result.get("label")))
        return _sentence(said or verb), "", _chips(("Open the board", at))
    return say


def _diagram(result: dict, args: dict) -> Said:
    cards = [c for c in result.get("cards") or [] if isinstance(c, dict)]
    at = board_at(result.get("board_id") or args.get("board_id"))
    titles = {str(n.get("ref")): str(n.get("title") or "") for n in args.get("nodes") or [] if isinstance(n, dict)}
    rows = [f"- {link(titles.get(str(c.get('ref'))) or 'Note ' + str(c.get('note_id')), note_at(c.get('note_id')))}" for c in cards[:12]]
    return f"Drew a diagram of {count_noun(len(cards), 'card')} and {count_noun(int(result.get('links_created') or 0), 'link')} on {link('the board', at)}.", "\n".join(rows), _chips(("Open the board", at))


def _placed(result: dict, args: dict) -> Said:
    at = board_at(args.get("board_id"))
    return f"Placed “{result.get('placed') or 'the shape'}” on {link('the board', at)}.", "", _chips(("Open the board", at))


def _reminder_set(result: dict, args: dict) -> Said:
    when = _when(result.get("due_at")) or str(result.get("due") or "")
    return f"I'll remind you to {_lower_first(str(result.get('text') or args.get('text') or 'do that'))} on {when}.", "", _chips(("Open Reminders", REMINDERS))


def _lower_first(text: str) -> str:
    return text[:1].lower() + text[1:] if text[:2] != text[:2].upper() else text


def _reminder_done(result: dict, args: dict) -> Said:
    if result.get("done") is False and result.get("due_at"):
        return f"Ticked off; it comes round again on {_when(result.get('due_at'))}.", "", _chips(("Open Reminders", REMINDERS))
    return "Marked the reminder done.", "", _chips(("Open Reminders", REMINDERS))


def _note_deleted(result: dict, args: dict) -> Said:
    return f"Moved note {result.get('deleted') or args.get('note_id')} to the bin. It can be restored from there.", "", _chips(("Open the bin", "#/library/all"))


def _note_restored(result: dict, args: dict) -> Said:
    at = note_at(result.get("id") or args.get("note_id"))
    return f"Restored {link(_title(result.get('content')), at)} from the bin.", "", _chips(("Open it", at))


def _preference(result: dict, args: dict) -> Said:
    said = (result.get("proposal") or {}).get("content") or args.get("preference")
    return f"I can remember that you said “{said}”, once you accept it.", "It is not in force until then.", _chips(("Review it", settings_at("memory")))


def _skill_saved(result: dict, args: dict) -> Said:
    steps = int(result.get("steps") or 0)
    verb = "Updated" if result.get("updated") else "Created"
    return f"{verb} the skill “{result.get('name') or args.get('name')}”" + (f", {count_noun(steps, 'step')}." if steps else "."), "", _chips(("Open Skills", SKILLS))


def _skill_deleted(result: dict, args: dict) -> Said:
    return f"Deleted the skill “{result.get('name') or args.get('name')}”.", "", _chips(("Open Skills", SKILLS))


# --- the tools that hand the turn back to the person ------------------------------


def _ask(result: dict, args: dict) -> Said:
    options = [str(o) for o in args.get("options") or result.get("options") or []]
    return _sentence(str(args.get("question") or result.get("question") or "Which one?")).rstrip(".") + ("" if str(args.get("question") or "").rstrip().endswith("?") else ""), "\n".join(f"- {o}" for o in options), ""


def _plan(result: dict, args: dict) -> Said:
    steps = [str(s) for s in args.get("steps") or result.get("steps") or []]
    goal = str(args.get("goal") or result.get("goal") or "this")
    return f"The plan for “{goal}”, in {count_noun(len(steps), 'step')}:", "\n".join(f"{i}. {_sentence(s)}" for i, s in enumerate(steps, 1)), ""


def _run_skill(result: dict, args: dict) -> Said:
    return f"Running the skill “{args.get('name') or result.get('name') or 'you picked'}”.", "", _chips(("Open Skills", SKILLS))


def _compress(result: dict, args: dict) -> Said:
    return "I summed up this chat so far for you to check before it replaces the older turns.", "", ""


SAYERS: dict[str, Callable[[dict, dict], Said]] = {
    "get_current_time": _time, "calculate": _calculate, "count_notes": _count, "list_notes": _list_notes,
    "search_notes": _search_notes, "get_note": _get_note, "find_similar_notes": _similar, "related_notes": _related,
    "path_between": _path, "find_contradictions": _contradictions, "summarize_notes": _summary,
    "list_tags": _named_counts("tags", "tag"), "list_categories": _named_counts("categories", "category"),
    "notebook_overview": _overview, "notebook_structure": _structure, "list_documents": _documents,
    "get_document": _get_document, "list_reminders": _reminders, "list_skills": _skills, "search_help": _help,
    "search_chat_history": _chat_history, "search_files": _files, "read_file": _read_file, "read_text": _read_text,
    "read_whiteboard": _whiteboard, "search_whiteboard": _search_board, "read_mindmap": _mindmap,
    "list_library": _library, "check_answer": _check, "propose_act": _propose, "web_search": _web, "read_url": _read_url,
    "create_note": _created_note, "edit_note": _edited_note, "tag_note": _tagged, "pin_note": _pinned,
    "link_notes": _linked, "unlink_notes": _linked, "audit_link_reasons": _audit,
    "create_category": _category, "rename_category": _category, "merge_categories": _category, "delete_category": _category,
    "rename_tag": _tag, "delete_tag": _tag, "create_document": _created_document, "delete_document": _deleted_document,
    "create_mindmap": _mindmap_made, "map_from_note": _map_from_note, "move_notes": _moved, "add_map_node": _map_node, "link_map_nodes": _map_link,
    "add_whiteboard_card": _board_card, "add_whiteboard_link": _board_write("Linked the two cards"),
    "add_board_shape": _board_write("Drew the shape"), "edit_board_item": _board_write("Changed it"),
    "move_board_item": _board_write("Moved it"), "delete_board_item": _board_write("Took it off the board"),
    "restore_board_item": _board_write("Put it back on the board"), "generate_diagram": _diagram,
    "place_library_item": _placed, "set_reminder": _reminder_set, "complete_reminder": _reminder_done,
    "delete_note": _note_deleted, "restore_note": _note_restored, "save_user_preference": _preference,
    "save_skill": _skill_saved, "delete_skill": _skill_deleted, "ask_user": _ask, "make_plan": _plan,
    "run_skill": _run_skill, "compress_chat": _compress,
}

#: The screen each tool works on: where a failure's next step points.
_SCREENS = {
    "reminder": ("Reminders", REMINDERS), "document": ("Documents", DOCUMENTS), "board": ("Boards", BOARDS),
    "map": ("Boards", BOARDS), "diagram": ("Boards", BOARDS), "library": ("Boards", BOARDS), "whiteboard": ("Boards", BOARDS),
    "skill": ("Skills", SKILLS), "file": ("Files", FILES), "link": ("the graph", GRAPH), "path": ("the graph", GRAPH),
    "related": ("the graph", GRAPH), "chat": ("Chat", CHATS), "help": ("Help", settings_at("help")),
    "web": ("Settings, Web search", settings_at("websearch")), "url": ("Settings, Web search", settings_at("websearch")),
    "preference": ("What it remembers", settings_at("memory")),
}
#: The argument names an error may quote, as words.
_ARG_WORDS = {
    "note_id": "note number", "other_note_id": "other note's number", "note_ids": "note numbers", "board_id": "board",
    "item_id": "item", "file_id": "file", "document_id": "document number", "reminder_id": "reminder", "card_id": "card",
    "from_card_id": "first card", "to_card_id": "second card", "from_id": "first idea", "to_id": "second idea",
    "parent_id": "parent idea", "parent_ref": "parent", "due_at": "time", "root_text": "first idea",
}


def _screen(tool: str) -> tuple[str, str]:
    for word, screen in _SCREENS.items():
        if word in tool:
            return screen
    return "Notes", NOTES


def _error(tool: str, message: str, args: dict) -> Said:
    text = re.sub(rf"^{re.escape(tool)}:\s*", "", str(message or "")).strip()
    if re.search(r"turned off in Settings|is disabled in Settings", text):
        what = "Web search" if tool in ("web_search", "read_url") else "That tool"
        return f"{what} is turned off.", "Turn it on in Settings, Tools it can use, then ask again.", _chips(("Open Settings, Tools it can use", settings_at("tools")))
    if re.search(r"starts a run rather|answered by the person|hands the summary", text):
        return SAYERS[tool]({}, args) if tool in SAYERS else ("That needs you to take the next step.", "", "")
    missing = re.match(r"No (?:uploaded )?(note|document|reminder|file|board|card|skill|category|tag)\b[^\d]*(\d+)?", text, re.I)
    name, at = _screen(tool)
    if missing:
        kind = missing.group(1).lower()
        named = f"{kind} {missing.group(2)}" if missing.group(2) else f"that {kind}"
        return f"I could not find {named}.", f"It may have been deleted, or the number is wrong. Look for it in {name}.", _chips((f"Open {name}", at))
    for key, words in _ARG_WORDS.items():
        text = re.sub(rf"\b{key}\b", words, text)
    for other in SAYERS:
        text = re.sub(rf"\b{other}\b", other.replace("_", " "), text)
    text = re.sub(r"\b([a-z]+)_([a-z_]+)\b", lambda m: m.group(0).replace("_", " "), text)
    text = text.replace("{", "(").replace("}", ")").replace("→", "to")
    text = re.sub(r"\[\d+\]", "", text)
    return f"That did not work: {_lower_first(_sentence(text))}", f"Try again with different words, or do it by hand in {name}.", _chips((f"Open {name}", at))


def say(tool: str, result: object, args: dict | None = None, today: date | None = None) -> dict:
    """`result` from `tool` as {"text": Markdown, "links": [app addresses]}:
    the lead, the structured body, the next taps. Never raises: a result
    this cannot read is said by its label, or as done."""
    args = args if isinstance(args, dict) else {}
    if not isinstance(result, dict):
        lead, body, chips = ("Done.", "", "")
    elif result.get("error"):
        lead, body, chips = _error(tool, str(result["error"]), args)
    else:
        sayer = SAYERS.get(tool)
        try:
            lead, body, chips = sayer(result, args) if sayer else (_sentence(_plain(result.get("label"))) or "Done.", "", "")
        except (TypeError, ValueError, KeyError, AttributeError):
            lead, body, chips = (_sentence(_plain(result.get("label"))) or "Done.", "", "")
    if not lead.strip():
        lead = "Done." if not body.strip() else lead
    text = "\n\n".join(part for part in (lead, body, chips) if part)
    return {"text": text, "lead": lead, "body": body, "chips": chips, "links": re.findall(r"\]\((#/[^)]+|https?://[^)]+)\)", text)}
