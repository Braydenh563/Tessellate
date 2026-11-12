"""The retry of a digest answer that quoted one note (L93): read the notes it did not use."""

from __future__ import annotations


def unread(first: dict | None, notes: list[dict]) -> list[dict]:
    """The notes an answer that quoted exactly one note did not use: what a retry may read instead (L93)."""
    cited = {row["note_id"] for row in (first or {}).get("grounding") or []}
    return [n for n in notes if n.get("id") not in cited] if len(cited) == 1 else []


def varied(first: dict | None, notes: list[dict], answer) -> dict | None:  # noqa: ANN001
    """Ask again on an answer that quoted one note (a "when is", a "what is"): the same question over the notes
    the first answer did not use, kept only when one of them answers it the same way. An answer over several
    notes (a count, an overview) is left as it was: its figures are the same on every retry (audit 1031 C25)."""
    others = unread(first, notes)
    if not others:
        return first
    again = answer(others)
    return again if again and again.get("grounding") and again.get("shape") == first.get("shape") else first


def retried(first: dict | None, notes: list[dict], answer, attempt: int) -> dict | None:  # noqa: ANN001
    """A digest answer on a retry: over one quoted note it reads the others, or hands over to `compose`, which does (L93)."""
    if not attempt:
        return first
    again = varied(first, notes, answer)
    return None if again is first and unread(first, notes) else again
