"""Assists on a note: tag suggestions, added context, improved writing (decision 55, L-world-class-632).

The route parses the body, finds the note and maps the domain errors to
status codes; the work is here and imports nothing from the API layer.
`tests/test_suggest_tags_no_model.py`, `tests/test_kept_suggestions.py` and
`tests/test_entry_assist.py` hold it.
"""

from __future__ import annotations

import json
import logging

from sqlalchemy import delete as sa_delete
from sqlalchemy.orm import Session

from tessellate.ai import janitor, librarian
from tessellate.ai.ollama_client import OllamaError
from tessellate.core import deps
from tessellate.core.database import EmbeddingRecord
from tessellate.entry import manager, tag_reasons, tag_suggestions

logger = logging.getLogger(__name__)

#: Said once per process, not once per keystroke pause.
_SAID_ONCE: set[str] = set()


class NeedsReadable(RuntimeError):
    """A private note is edited in its own editor, not appended to."""


class NothingToImprove(ValueError):
    """The text or the custom instruction is empty."""


class NeedsModel(RuntimeError):
    """Rewording is writing: it needs a model; proofreading does not."""


class ModelFailed(RuntimeError):
    """The model answered with an error (its own text is in the log)."""


def draft_tags(session: Session, text: str, tags: list[str], title: str) -> dict:
    """Tag suggestions for a note that doesn't exist yet: the other half of
    a report that `/{entry_id}/reevaluate` only ever covered post-save:
    "the ai and application doesnt suggest tags either before creating a
    new note or after." Reuses `librarian.suggest_tags` directly on the
    draft's own text: it only ever needed a string and the tags already on
    it, never a saved `Entry`, so the Capture form can offer suggestions
    while the user is still typing."""
    content = text.strip()
    if title.strip() and content:
        content = f"# {title.strip()}\n\n{content}"
    if not content:
        return {"suggested_tags": [], "suggested_tag_reasons": {}}
    #: **No model, no model call** (measured on the running app: with none
    #: running, every pause in Capture asked the client for a completion from
    #: model "" and logged a WARNING with its traceback, three per note typed,
    #: and offered nothing). Then, and when the model fails, the notebook's own
    #: tags answer, the fallback filing already uses (`_suggest_after_filing`).
    model_manager, ollama = deps.get_model_manager(), deps.get_ollama()
    suggested: list[str] = []
    if model_manager.utility_model() and ollama.is_running():
        try:
            suggested = librarian.suggest_tags(
                content, tags, model_manager, ollama, vocabulary=tag_suggestions.tag_vocabulary(session)
            )
        except Exception:
            logger.info("tag suggestions from the model failed; using the notebook's own", exc_info=True)
    elif "no-model-tags" not in _SAID_ONCE:
        _SAID_ONCE.add("no-model-tags")
        logger.info("no model running: tag suggestions come from the notebook's own tags")
    offered = tag_suggestions.engine_tags(session, content, tags, suggested, None)
    return {"suggested_tags": offered, "suggested_tag_reasons": tag_reasons.reasons(content, offered)}


def _discard_tags(entry, discard: list[str], restore: list[str]) -> dict[str, str]:  # noqa: ANN001
    """Remember the tags turned down on this note (the last 200), and return the
    ones taken back, keyed by their folded form."""
    gone = tag_suggestions.json_tags(entry.discarded_tags)
    gone_folded = {tag.casefold() for tag in gone}
    gone += [tag.strip() for tag in discard if tag.strip() and tag.strip().casefold() not in gone_folded]
    restored = {tag.strip().casefold(): tag.strip() for tag in restore if tag.strip()}
    gone = [tag for tag in gone if tag.casefold() not in restored]
    entry.discarded_tags = json.dumps(gone[-200:])
    return restored


def answer_tags(
    session: Session, entry, *, take: list[str], discard: list[str], restore: list[str], mute: bool | None  # noqa: ANN001
) -> None:
    """Take or discard the tags filing suggested (INBOX 440). A taken tag is
    added like one typed by hand; a discarded one is remembered so no later
    filing pass offers it on this note again."""
    if mute is not None:
        entry.tag_suggest_off = mute
    offered = {tag.casefold(): tag for tag in tag_suggestions.json_tags(entry.suggested_tags)}
    taken = [offered.get(tag.casefold(), tag.strip()) for tag in take if tag.strip()]
    if taken:
        have = manager.entry_tags(entry)
        folded = {tag.casefold() for tag in have}
        manager.update_entry(session, entry, tags=have + [tag for tag in taken if tag.casefold() not in folded])
    restored = _discard_tags(entry, discard, restore)
    answered = {tag.casefold() for tag in [*taken, *discard]}
    kept = [tag for tag in tag_suggestions.json_tags(entry.suggested_tags) if tag.casefold() not in answered]
    kept_folded = {tag.casefold() for tag in kept}
    entry.suggested_tags = json.dumps(kept + [tag for key, tag in restored.items() if key not in kept_folded])
    session.commit()


def add_context(session: Session, entry, text: str) -> str | None:  # noqa: ANN001
    """Append context to a note and let the janitor rethink the category with
    the fuller picture; a note the user filed themselves keeps its category.
    Returns how it was refiled, or None."""
    # Appending to the ciphertext made the note unreadable for good, and the
    # filing below would read its text: a private note is edited in its own
    # editor (same refusal as generate-title and remove-title).
    if entry.is_private:
        raise NeedsReadable("Make this note readable first: private notes can't be edited here.")
    entry.content = f"{entry.content}\n\n--- added context ---\n{text.strip()}"
    manager.mark_edited(entry)
    manager.log_action(session, "edited", "entry", entry.id, "context added")
    session.commit()

    # The old vector describes the old text, refresh it, best effort.
    try:
        session.execute(sa_delete(EmbeddingRecord).where(EmbeddingRecord.entry_id == entry.id))
        session.commit()
    except Exception:  # noqa: BLE001  # never fail the edit over the index
        logging.getLogger("tessellate.embeddings").warning(
            "couldn't clear the stale vector for entry %s", entry.id, exc_info=True
        )
        session.rollback()
    else:
        deps.store_quietly(session, entry)

    filed_by = None
    if not entry.user_filed:
        try:
            category, confidence, filed_by = janitor.categorise(
                session,
                entry.content,
                deps.get_embeddings(),
                deps.get_model_manager(),
                deps.get_ollama(),
                exclude_entry_id=entry.id,  # don't let it anchor to itself
            )
            if filed_by != "none":
                manager.record_filing(
                    session, entry, category,
                    by=janitor.filed_by_label(
                        filed_by, confidence, deps.get_model_manager(), deps.get_embeddings()
                    ),
                )
                entry.ai_confidence = confidence
                # The same two lines as the create paths: a category the AI
                # chose here is one a later move by hand corrects, and without
                # the flag that correction went unrecorded (Brief 13).
                if janitor.settled_state(filed_by) != "done":
                    entry.filing_state = janitor.settled_state(filed_by)
                session.commit()
        except Exception:
            logger.warning("re-filing after new context failed", exc_info=True)
            filed_by = None  # AI down, the note keeps its old category
    return filed_by


def improve(text: str, mode: str, custom_instruction: str | None) -> dict:
    """An AI-polished version of some note text without saving it: the UI
    shows a before/after and the user decides. Never touches a note."""
    text = text.strip()
    if not text:
        raise NothingToImprove("There's no text to improve.")
    custom = (custom_instruction or "").strip()
    if mode == "custom" and not custom:
        raise NothingToImprove("Say what you want changed, then try again.")
    if not deps.get_ollama().is_running():
        #: O7 (INBOX 904 B33): proofreading is the app's own with no model;
        #: rewording is writing, and says so.
        if mode != "proofread":
            raise NeedsModel("Rewording needs a model (Settings, Models). Proofread works without one.")
        from tessellate.ai import proofread

        improved, changes = proofread.proofread(text)
        return {
            "original": text, "improved": improved, "mode": mode, "by": "composer",
            "said": proofread.said(changes, text), "truncated": proofread.covered(text) < len(text),
        }
    try:
        improved = librarian.improve_writing(
            text, mode, deps.get_model_manager(), deps.get_ollama(), custom_instruction=custom
        )
    except OllamaError as exc:
        # The provider's own text names the model and carries the transport's
        # error; it belongs in the log, not in the toast.
        logger.warning("improve writing failed", exc_info=True)
        raise ModelFailed(librarian.AI_FAILED_MESSAGE) from exc
    return {"original": text, "improved": improved, "mode": mode}
