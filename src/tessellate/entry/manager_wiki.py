"""Wiki links: the [[name]] readers, the resolve and rewrite passes, and the starter notes.

Moved whole out of `entry/manager.py` (audit K24, BK11), unchanged. It sits above `entry/manager.py` and `entry/manager_links.py` (it files links and edits notes), so they never import it back. Callers import these names from here.
"""

from __future__ import annotations

import re
from datetime import timedelta
from sqlalchemy import func, or_, select
from sqlalchemy.orm import Session
from tessellate.core.database import Entry, EntryLink, LIKE_ESCAPE, like_escape, utcnow
from tessellate.entry.manager import create_entry, log_action, record_revision, update_entry
from tessellate.entry.manager_links import create_link, delete_link
from tessellate.entry.manager_text import WIKI_LINK, wiki_target


def wiki_link_targets(content: str) -> list[str]:
    """The [[names]] mentioned in some text, de-duplicated, in order.

    A `[[Target|Shown]]` is named by its target, so `[[bread]]` and
    `[[Bread|loaf]]` are one name.
    """
    seen = {}
    for match in WIKI_LINK.finditer(content or ""):
        name = wiki_target(match.group(1))
        if name:
            seen.setdefault(name.lower(), name)
    return list(seen.values())


def find_by_wiki_name(session: Session, name: str) -> Entry | None:
    """The note a [[name]] refers to, or None.

    Matched against the start of the note, because a note has no title, its
    opening words are what a person would call it. An exact opening beats a
    partial one, and among equals the oldest wins so a link doesn't silently
    change meaning when a newer note happens to start the same way.
    """
    wanted = wiki_target(name).lower()
    if not wanted:
        return None
    #: **A vault's links name the file, not the first words.** An imported
    #: note carries the path it came from (`Entry.source_path`), and Obsidian
    #: writes `[[Roadmap]]` for `Projects/Roadmap.md`, so without this an
    #: imported vault resolves almost none of its own links, since the note's
    #: text starts with the heading the importer wrote, not with the name.
    #: Tried first and matched exactly: a file called "Index" should not lose
    #: to a note that merely opens with the word "index".
    #: Filtered in SQL rather than by loading every imported note: this runs
    #: once per `[[link]]` per save, and a real vault is thousands of files.
    #: The `LIKE` can over-match (`Roadmap.md` also matches `My Roadmap.md`),
    #: so the stem is checked exactly in Python below: the query narrows, it
    #: does not decide. A name containing `%` used to over-match far wider
    #: than that, matching any path at all; `like_escape` ends that, and the
    #: `escape=` beside it is what makes the escaped pattern mean anything.
    vault_clauses = []
    for suffix in (".md", ".markdown"):
        stem = like_escape(wanted)
        vault_clauses.append(Entry.source_path.ilike(f"{stem}{suffix}", escape=LIKE_ESCAPE))
        vault_clauses.append(Entry.source_path.ilike(f"%/{stem}{suffix}", escape=LIKE_ESCAPE))
    vault = session.scalars(
        select(Entry)
        .where(
            Entry.is_deleted == False,  # noqa: E712
            Entry.is_private == False,  # noqa: E712
            or_(*vault_clauses),
        )
        .order_by(Entry.id)
    ).all()
    for entry in vault:
        stem = (entry.source_path or "").rsplit("/", 1)[-1].lower()
        if stem.removesuffix(".md").removesuffix(".markdown") == wanted:
            return entry
    #: **A note that opens with a heading is named by the heading** (INBOX
    #: 517). Most notes start `# Name`, and matching the raw text against
    #: `name%` never saw past the `#`, so `[[Name]]` linked to nothing. The
    #: SQL narrows (raw start, or a heading marker then the name); the
    #: opening line with its marker stripped decides.
    escaped = like_escape(wanted)
    candidates = session.scalars(
        select(Entry)
        .where(
            Entry.is_deleted == False,  # noqa: E712
            Entry.is_private == False,  # noqa: E712
            or_(
                Entry.content.ilike(f"{escaped}%", escape=LIKE_ESCAPE),
                Entry.content.ilike(f"#% {escaped}%", escape=LIKE_ESCAPE),
                # KG4: a note opening with properties; the name is after them.
                Entry.content.ilike(f"---%{escaped}%", escape=LIKE_ESCAPE),
            ),
        )
        .order_by(Entry.id)
    ).all()
    candidates = [e for e in candidates if wiki_opening(e.content).startswith(wanted)]
    if not candidates:
        return None
    for entry in candidates:
        if wiki_opening(entry.content) == wanted:
            return entry  # its name, exactly: the whole opening line
    return candidates[0]


_HEADING_MARK = re.compile(r"^\s{0,3}#{1,6}\s+")


def wiki_opening(content: str | None) -> str:
    """A note's name for [[links]]: its first line, heading marker stripped
    (after its properties block, KG4)."""
    from tessellate.entry.properties import strip as strip_properties

    first = strip_properties(content or "").strip().split("\n", 1)[0]
    return _HEADING_MARK.sub("", first).strip().lower()


def resolve_links_to(session: Session, entry: Entry) -> int:
    """Link the notes that already wrote `[[this note's name]]` (INBOX 517).

    A link is often written before the note it names; `sync_wiki_links` runs
    only on the note that holds the link, so without this such a link stayed
    unresolved until that other note happened to be saved again.
    """
    name = wiki_opening(entry.content)
    if not name or len(name) > 120:
        return 0
    holders = session.scalars(
        select(Entry).where(
            Entry.is_deleted == False,  # noqa: E712
            Entry.id != entry.id,
            Entry.content.ilike(f"%[[{like_escape(name)}]]%", escape=LIKE_ESCAPE),
        )
    ).all()
    made = 0
    for holder in holders:
        if find_by_wiki_name(session, name) is entry and create_link(session, holder, entry, origin="wiki"):
            made += 1
    return made


def sync_wiki_links(session: Session, entry: Entry) -> list[str]:
    """Create links for the [[names]] in this note. Returns the unresolved ones.

    A [[name]] that matches nothing is left alone rather than reported as an
    error, you often write the link before the note it points at, and having
    that fail the save would be worse than useless.

    **And takes away the ones whose name left the text** (GRAPH_PLAN 518): a
    link this note's own `[[name]]` made (`origin == "wiki"`) whose target no
    name in the text resolves to any more. A link made any other way is never
    touched here.
    """
    unresolved = []
    named: set[int] = set()
    for name in wiki_link_targets(entry.content):
        target = find_by_wiki_name(session, name)
        if target is None or target.id == entry.id:
            if target is None:
                unresolved.append(name)
            continue
        named.add(target.id)
        create_link(session, entry, target, origin="wiki")
    stale = session.scalars(
        select(EntryLink).where(
            EntryLink.source_entry_id == entry.id,
            EntryLink.origin == "wiki",
            EntryLink.target_entry_id.not_in(named),
        )
    ).all()
    for link in stale:
        delete_link(session, link)
    return unresolved


def _wiki_name_pattern(name: str) -> re.Pattern:
    """`[[name]]`, `[[name|alias]]` and `[[name#part]]`, any case."""
    return re.compile(r"\[\[\s*" + re.escape(name.strip()) + r"\s*(?=[\]|#])", re.IGNORECASE)


def wiki_holders(session: Session, entry: Entry, name: str) -> list[Entry]:
    """The other notes whose text has `[[name]]` in one of its forms."""
    if not name or len(name) > 120:
        return []
    pattern = _wiki_name_pattern(name)
    rows = session.scalars(
        select(Entry).where(
            Entry.is_deleted == False,  # noqa: E712
            Entry.is_private == False,  # noqa: E712
            Entry.id != entry.id,
            Entry.content.ilike(f"%[[{like_escape(name.strip())}%", escape=LIKE_ESCAPE),
        )
    ).all()
    return [row for row in rows if pattern.search(row.content or "")]


def rewrite_wiki_name(
    session: Session, entry: Entry, old: str, new: str, saved: list[dict] | None = None
) -> int:
    """Rewrite `[[old]]` as `[[new]]` in every note that names it (GRAPH_PLAN
    518: a renamed note offers this). Each note keeps its alias and part, gets
    a revision first so it can be undone from its history, and is synced so
    its links point where the names now do. Returns how many notes changed.

    `saved`, when given, gets `{"id", "revision_id"}` for each note changed:
    the version each held before, which is how Undo puts the old name back
    (`POST /entries/{id}/history/{revision_id}/restore`, INBOX 898)."""
    pattern = _wiki_name_pattern(old)
    changed = 0
    for holder in wiki_holders(session, entry, old):
        revision = record_revision(session, holder)
        if saved is not None:
            saved.append({"id": holder.id, "revision_id": revision.id})
        update_entry(session, holder, content=pattern.sub(lambda _m: f"[[{new.strip()}", holder.content))
        sync_wiki_links(session, holder)
        changed += 1
    if changed:
        log_action(session, "edited", "entry", entry.id, f"renamed [[{old}]] in {changed} notes")
    session.commit()
    return changed


# ROADMAP.md's onboarding item: "seeded example notes so the graph, timeline
# and dashboard have something to show before the first note exists". Content
# is deliberately about the app itself, a first-run tour that also
# demonstrates linking and categories, rather than generic placeholder text.
#: Each note's content deliberately opens with its own name verbatim, 
#: `find_by_wiki_name` resolves a [[link]] by matching the *start* of
#: another note's content (there's no separate title field), so this is
#: what makes the two real [[links]] below actually resolve.
_EXAMPLE_NOTES = [
    (
        "About Tessellate",
        ["welcome"],
        "Local-first, always: Tessellate keeps everything on this machine, "
        "notes, search, even the AI, if you point it at a local model. "
        "Nothing is sent anywhere unless you explicitly turn on web search.",
        9,
    ),
    (
        "About Tessellate",
        ["welcome", "graph"],
        "Linking notes together: type [[Local-first, always]] and it "
        "becomes a real link, click it, or see it drawn on the Graph tab. "
        "That's how a notebook here becomes a map instead of a pile.",
        7,
    ),
    (
        "About Tessellate",
        ["welcome", "ai"],
        "Try asking a question: open the Ask tab and try something like "
        "\"what's in my notebook about being local-first?\" The answer will "
        "point back to [[Local-first, always]] and show its reasoning.",
        5,
    ),
    (
        "Personal",
        ["example"],
        "A running shopping list: not every note has to be deep, jot down "
        "a shopping list, a name you don't want to forget, a link to read "
        "later. This one just fills out a second category and a different "
        "day on the Timeline.",
        3,
    ),
    (
        "About Tessellate",
        ["welcome"],
        "Delete these whenever: these five notes are just here so the "
        "Graph, Timeline and Dashboard have something to show on a "
        "brand-new notebook. Filter the Library by the welcome tag and "
        "delete them any time, nothing about them is special.",
        1,
    ),
]


def seed_example_notes(session: Session) -> int:
    """Create the starter notes above, oldest first so each [[link]] resolves
    against a target that already exists (`sync_wiki_links` only ever adds,
    never fails a save on an unresolved name, but an unresolved name here
    would just be a missed demonstration, not a bug).

    Refuses silently (returns 0) on a notebook that already has any note, 
    seeding is an onboarding offer, never something that could land on top of
    real work if this were ever called twice.
    """
    if session.scalar(select(func.count(Entry.id))) or 0:
        return 0
    now = utcnow()
    for category_name, tags, content, days_ago in _EXAMPLE_NOTES:
        entry = create_entry(
            session, content=content, category_name=category_name, tags=tags
        )
        entry.created_at = now - timedelta(days=days_ago)
        entry.updated_at = entry.created_at
        session.commit()
        sync_wiki_links(session, entry)
        session.commit()
    return len(_EXAMPLE_NOTES)
