"""What the assistant learns: a saved preference, and the audit of link reasons, learned notes and contradictions.

Moved whole from `__init__.py` (audit AR3, gods-2): the code is unchanged, and
`__init__` re-exports every name here that anything reads. Imports run one way,
down the layer list in `__init__.py`'s docstring, never back to `__init__`.
"""

from __future__ import annotations

from sqlalchemy.orm import Session
from tessellate.ai.tools._common import ToolError
from tessellate.core import deps, private_turn
from tessellate.ai import memory
from sqlalchemy import select

#: The longest standing preference the model may write, and the most it may
#: keep. Both are caps on *the system prompt*, not on storage: every active
#: preference is replayed to the model on every round of every turn (see
#: `agent._persona_with_memory`), so an unbounded list is a slow squeeze on the
#: window that ends with the user's actual question falling off the front.
#: `content` is a String(500) column and SQLite will not enforce that for us.
MAX_PREFERENCE_CHARS = memory.MAX_PREFERENCE_CHARS
MAX_ACTIVE_PREFERENCES = 40


def _save_user_preference(session: Session, args: dict) -> dict:
    """Remember a standing instruction from the user (the memory stream).

    Worth being careful with, because this is the one tool whose output
    becomes part of the model's own system prompt on every later turn: text
    that arrives here is text the model will later read as an instruction. So
    it is length-capped, de-duplicated, and count-capped, a model that decides
    to write itself a new rule every turn otherwise fills its own window with
    its own voice.
    """
    from tessellate.core.database import UserPreference

    if private_turn.active():
        #: The agent is not offered this tool in a private chat; this is the
        #: write's own refusal, for a path that offers the whole registry.
        raise ToolError("Nothing is saved from a private chat.")
    pref = str(args.get("preference") or "").strip()
    if not pref:
        raise ToolError("Must provide 'preference'.")
    if len(pref) > MAX_PREFERENCE_CHARS:
        raise ToolError(
            f"That preference is too long, keep it under {MAX_PREFERENCE_CHARS} "
            "characters. Save the rule, not the explanation."
        )

    # Everything already on file, proposals included: re-proposing something
    # the user declined an hour ago is worse than not proposing at all.
    existing = list(session.scalars(select(UserPreference)))
    if any((row.content or "").strip().lower() == pref.lower() for row in existing):
        return {
            "already_known": True,
            "label": "ph:brain Already remembered",
            "message": f"That preference was already saved: {pref}",
        }
    active = [row for row in existing if row.active]
    if len(active) >= MAX_ACTIVE_PREFERENCES:
        raise ToolError(
            f"There are already {len(active)} saved preferences, which is the "
            "limit. Ask the user which one to drop before saving another."
        )

    # **Proposed, not saved.** Asked for directly: "can the ai pick up things
    # and suggest the user adds it as a preference in that section with an
    # accept or deny or similar popup??", and the old behaviour is the reason
    # that is the right shape. This tool used to write a standing instruction
    # into every future system prompt with no confirmation of any kind (its own
    # description said "quietly append"), so a model that misread one sentence
    # gave itself a permanent rule the user never agreed to and would only find
    # by opening a settings page they had no reason to visit.
    #
    # `active=False, proposed=True` is a third state, not "off": it is out of
    # the prompt, and the chat and Settings both show it as waiting for an
    # answer. The model is told plainly that it is not in force yet, so it does
    # not go on to behave as though it were.
    row = UserPreference(content=pref, active=False, proposed=True)
    session.add(row)
    session.commit()
    session.refresh(row)
    return {
        "label": "ph:brain Suggested remembering this",
        "message": (
            f"Suggested remembering: {pref}: it is NOT in force until the user "
            "accepts it. Do not assume it applies yet."
        ),
        # The chat renders an Accept/Not this time card from these.
        "proposal": {"id": row.id, "content": pref},
    }

# There is no `generate_skill` here, and there was briefly: a second
# skill-writing tool that built a raw dict and pushed it straight into
# preferences. `save_skill` above is the same intent done safely, it runs
# `skills.normalise`, which validates the shape and checks every declared tool
# name against this registry, refuses to shadow a built-in, and honours
# `skills.MAX_SKILLS`. The duplicate did none of those, and a skill's `tools`
# list is its allowlist for the run, so "the model may invent that list
# unchecked" was the part that mattered. One tool for one job, as
# `_save_skill`'s own docstring argues.


def _audit_link_reasons(session: Session, args: dict) -> dict:
    """Rewrite a batch of vague link reasons (see `ai.links.audit_vague_links`).

    Uses `deps.get_model_manager()` / `deps.get_ollama()`, the same source
    every other tool handler in this module gets its model deps from (e.g.
    `_create_note`'s janitor call, `summarise_turns` above): not a fresh
    `ModelManager`/`OllamaClient` built from `config.get_config()`, which was
    the previous version here and doesn't even exist as a call
    (`tessellate.core.config` has no `get_config`): this tool raised
    `AttributeError` on every single invocation and had never actually run.
    Going through `deps` also means a test's `deps.override_ai(...)` fake
    reaches this tool the same way it reaches every other one.
    """
    from tessellate.ai import links

    limit = int(args.get("limit", 50))
    updated = links.audit_vague_links(session, deps.get_model_manager(), deps.get_ollama(), limit)
    return {"updated": updated, "message": f"Successfully audited and rewrote {updated} link reasons."}

def _check_learned(session: Session, args: dict) -> dict:
    """Check what it learned (decision 68, `ai/learned_audit_run.py`): re-read
    every learned claim and question against its note, retire what no longer
    holds and flag what needs a look. Every retirement is a tombstone with its
    run's stamp, which Settings, What it learned can undo."""
    from tessellate.ai import learned_audit_run
    from tessellate.core import jobruns

    with jobruns.job_run("learned-audit") as run:
        done = learned_audit_run.run_check(session)
        session.commit()
        learned_audit_run.say_lines(run, done)
        run.result = learned_audit_run.summary_words(done)
    shown = done["lines"][:10]
    return {
        "checked": done["checked"], "retired": len(done["retired"]), "flagged": len(done["flagged"]),
        "items": [{"action": row["action"], "text": row["text"][:200], "reason": row["reason"]} for row in shown],
        "run": done["run"], "message": f"Checked {run.result.removeprefix('checked ')}.",
    }


def _find_contradictions(session: Session, args: dict) -> dict:
    """Notes that appear to contradict each other (see `ai.tensions`).

    The agent's way into the Tensions review. Read-only on purpose: this
    *reports* what it found and never links anything, because the whole
    feature's rule is that accusing someone of contradicting themselves is
    a claim a person has to agree with first. The agent can say what it
    found and offer to link them; `link_notes` is the tool that does it,
    and the user is in that loop either way.

    Deps come from `deps.get_*` like every other handler here, so a test's
    `override_ai(...)` fake reaches this tool the same way.
    """
    from tessellate.ai import tensions
    from tessellate.ai.embeddings import similar_pairs

    ollama = deps.get_ollama()
    if not ollama.is_running():
        return {"tensions": [], "message": "No local model is running, so nothing can read the notes."}
    embeddings = deps.get_embeddings()
    if not embeddings.is_ready():
        return {
            "tensions": [],
            "message": "Semantic search is off, so there is no shortlist of notes to compare.",
        }

    limit = max(1, min(int(args.get("limit", 5)), 10))
    by_id, vectors, already = tensions.comparable_notes(session, embeddings)

    models = deps.get_model_manager()
    found: list[dict] = []
    checked = 0
    for a_id, b_id, _score in similar_pairs(vectors, 0.45):
        if checked >= tensions.MAX_PAIRS_PER_PASS or len(found) >= limit:
            break
        if frozenset((a_id, b_id)) in already:
            continue
        ordered = tensions.order_by_time(by_id[a_id], by_id[b_id])
        if ordered is None:
            continue
        checked += 1
        tension = tensions.compare_pair(ordered[0], ordered[1], models, ollama)
        if tension is None:
            continue
        found.append(tensions.agent_row(tension))
    if not found:
        return {
            "tensions": [],
            "message": (
                f"Read {checked} pair(s) of related notes and found no contradictions."
                if checked
                else "No notes were close enough in subject to be worth comparing."
            ),
        }
    return {
        "tensions": found,
        "message": (
            f"Found {len(found)} place(s) where the notes appear to disagree, from "
            f"{checked} pair(s) read. Nothing has been linked, offer to link any the "
            "user agrees with, using link_notes with link_type 'contradicts'."
        ),
    }
