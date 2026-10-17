"""Skills the composer runs when no model does (O7 rest; INBOX 904 B69: "Can
the composer run skills and do them well??").

A skill is steps for a model to carry out, so with no model running the
Skills menu was a wall of disabled rows. The shipped skills whose job is a
reading of the notebook have an exact, model-free equivalent here, and each
says so ("composed from your notes, no AI"):

- **ask**: the skill is a question the composer answers (`Summarise my week`
  is "what did I write in the last 7 days?", `Catch up on a topic` is "what
  have I written about {topic}?"); the route sends it down the ordinary
  composed path, so the answer is the one Ask would give;
- **starter**: the skill is one of the engine's own starters
  (`starter_acts`): loose ends, tagging untagged notes with tags already in
  use, linking related notes, the last two as act cards with Confirm and
  Undo, exactly as the typed acts;
- **report**: the skill is a count or a list the notebook can read off
  itself (`Tidy suggestions`, `Notebook health check`, `Find notes worth
  combining`), read-only like the skills they stand in for.

Anything else writes in its own words, asks questions or edits with
judgement, so it says that, and which skills do run, and where to connect a
model. Nothing here imitates a model: a skill it cannot do is not half done.
"""

from __future__ import annotations

import json
import re
from collections import Counter

from sqlalchemy import select
from sqlalchemy.orm import Session

from tessellate.ai import realise

#: Shipped skill name to how the composer runs it: (kind, what).
RUNS: dict[str, tuple[str, str]] = {
    "Summarise my week": ("ask", "What did I write in the last 7 days?"),
    "Daily review": ("ask", "What did I write today?"),
    "Catch up on a topic": ("ask", "What have I written about {topic}?"),
    "Find loose ends": ("starter", "loose_ends"),
    "Auto-tag my notes": ("starter", "tag_untagged"),
    "Link related notes": ("starter", "link_related"),
    "Tidy suggestions": ("report", "tidy"),
    "Notebook health check": ("report", "health"),
    "Find notes worth combining": ("report", "combine"),
}

#: How alike two unlinked notes must be to be worth reading side by side.
COMBINE_FLOOR = 0.5


def can_run(skill: dict) -> bool:
    """Whether the composer runs `skill`: a shipped one with a reading here.
    A saved skill of the same name is the person's own steps, not this."""
    return bool(skill.get("builtin")) and skill.get("name") in RUNS


def plan(skill: dict, inputs: dict | None) -> tuple[str, str] | None:
    """`(kind, what)` for a skill the composer runs, the question filled in;
    None for one it does not."""
    if not can_run(skill):
        return None
    kind, what = RUNS[skill["name"]]
    if kind == "ask":
        what = what.format(topic=str((inputs or {}).get("topic") or "").strip() or "this")
    return kind, what


def needs_a_model(skill: dict) -> str:
    """The honest answer for a skill the composer does not run."""
    name = str(skill.get("name") or "This skill")
    why = "writes in its own words" if skill.get("builtin") else "has steps for a model to carry out"
    return (
        f"“{name}” {why}, so it needs a model, and none is running. Connect one in Settings, Models, and it will run. "
        f"These skills run without one: {', '.join(RUNS)}."
    )


# --- reports ----------------------------------------------------------------------


def _tags_of(raw: str) -> list[str]:
    try:
        parsed = json.loads(raw or "[]")
    except (TypeError, ValueError):
        return []
    return [str(t).strip().lower() for t in parsed if str(t).strip()] if isinstance(parsed, list) else []


def _kin(tag: str) -> str:
    """Tags that differ only in case, punctuation or a plural "s" share this."""
    return re.sub(r"[^a-z0-9]", "", tag.lower()).rstrip("s")


def _duplicate_tags(counts: Counter) -> list[list[str]]:
    kin: dict[str, list[str]] = {}
    for tag in counts:
        kin.setdefault(_kin(tag), []).append(tag)
    return [sorted(group, key=lambda t: -counts[t]) for group in kin.values() if len(group) > 1]


def audit(session: Session) -> dict:
    """What the notebook says about its own tidiness: counts and the tags and
    categories that look like one another."""
    from tessellate.ai import slash
    from tessellate.core.database import Category, EntryLink
    from tessellate.entry import manager

    entry, visible = slash._notes()
    rows = list(session.execute(select(entry.id, entry.tags, entry.category_id).where(*visible)).all())
    counts = Counter(t for _, raw, _ in rows for t in _tags_of(raw))
    linked = set(session.scalars(select(EntryLink.source_entry_id))) | set(session.scalars(select(EntryLink.target_entry_id)))
    filed = dict(session.execute(select(Category.id, Category.name)).all())
    per_category = Counter(filed.get(cid) for _, _, cid in rows)
    return {
        "total": len(rows),
        "untagged": sum(1 for _, raw, _ in rows if not _tags_of(raw)),
        "unfiled": per_category.get(manager.UNCATEGORISED, 0) + per_category.get(None, 0),
        "orphans": sum(1 for i, _, _ in rows if i not in linked),
        "duplicate_tags": _duplicate_tags(counts),
        "lonely": sorted(name for name, n in per_category.items() if name and name != manager.UNCATEGORISED and n == 1),
    }


def _findings(found: dict) -> list[tuple[str, str]]:
    """Each thing worth fixing as (what is wrong, what to say to fix it)."""
    out: list[tuple[str, str]] = []
    if found["untagged"]:
        out.append((f"{realise.count_noun(found['untagged'], 'note')} with no tag", "say “tag my untagged notes”"))
    for group in found["duplicate_tags"][:3]:
        out.append((f"{' and '.join('#' + t for t in group[:3])} look like one tag", f"keep #{group[0]} by retagging the others, or ask me to tag the notes"))
    if found["unfiled"]:
        out.append((f"{realise.count_noun(found['unfiled'], 'note')} not filed in a category of its own", "open Notes, Tidy to file them"))
    if found["orphans"]:
        out.append((f"{realise.count_noun(found['orphans'], 'note')} linked to nothing", "say “link related notes”"))
    if found["lonely"]:
        out.append((f"{realise.count_noun(len(found['lonely']), 'category')} holding one note ({', '.join(found['lonely'][:4])})", "move the note or keep it as a start"))
    return out


def tidy(session: Session) -> str:
    found = audit(session)
    if not found["total"]:
        return "There are no notes yet, so there is nothing to tidy."
    findings = _findings(found)
    if not findings:
        return f"Nothing needs tidying: {realise.count_noun(found['total'], 'note')}, all tagged, filed and linked. I changed nothing."
    lines = "\n".join(f"{i}. {what}: {fix}." for i, (what, fix) in enumerate(findings, 1))
    return f"Tidy-ups, most worth doing first:\n\n{lines}\n\nI changed nothing. Say which you want done."


def health(session: Session) -> str:
    found = audit(session)
    if not found["total"]:
        return "There are no notes yet, so there is nothing to check."
    findings = _findings(found)
    lead = f"Your notebook has {realise.count_noun(found['total'], 'note')}."
    if not findings:
        return f"{lead} All are tagged, filed and linked. I changed nothing."
    lines = "\n".join(f"- {what}" for what, _ in findings)
    return f"{lead} What needs fixing, worst first:\n\n{lines}\n\nI changed nothing. “Tidy suggestions” says how to fix each."


def combine(session: Session) -> str:
    from tessellate.ai import commands, starter_acts

    entries = session.scalars(starter_acts._listed().order_by(starter_acts.Entry.id.desc()).limit(starter_acts.LINK_SCAN)).all()
    pairs = [p for p in starter_acts._best_pairs(entries, starter_acts._vectors(entries), starter_acts._linked(session)) if p[0] >= COMBINE_FLOOR]
    if not pairs:
        return "No two notes share enough words to be worth combining. I changed nothing."
    lines = "\n".join(f"- #{a.id} {commands._title(a)} and #{b.id} {commands._title(b)}" for _, a, b in pairs)
    return f"These pairs share the most words, so they may be one note:\n\n{lines}\n\nI combined nothing and deleted nothing."


REPORTS = {"tidy": tidy, "health": health, "combine": combine}

