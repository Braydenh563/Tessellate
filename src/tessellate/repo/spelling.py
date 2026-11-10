"""The words the person's own notes and documents use twice or more, for the
spelling second opinion (INBOX 1731; `api/routes_spelling.py`). Private notes,
private documents and every row of a private space never contribute, open or
shut: the checker's silence about a word must say nothing about a private note.
"""

from __future__ import annotations

import re
from collections import Counter

from sqlalchemy import select
from sqlalchemy.orm import Session

from tessellate.core.database import Document, Entry, _private_space_ids

#: A word as a person writes it: letters, with an inner apostrophe.
_WORD = re.compile(r"[A-Za-z][A-Za-z']*[A-Za-z]|[A-Za-z]")
#: Most rows read and most words sent: the list is a convenience, so a very
#: large notebook gets its most recently written part rather than a slow call.
MAX_ROWS = 3000
MAX_WORDS = 20000
MAX_CHARS_PER_ROW = 20000


def own_words(session: Session) -> list[str]:
    """Words used at least twice across the non-private notes and documents."""
    private_spaces = _private_space_ids(session)
    counts: Counter[str] = Counter()

    def feed(text: str | None) -> None:
        for word in _WORD.findall((text or "")[:MAX_CHARS_PER_ROW]):
            folded = word.lower()
            if folded.endswith("'s"):
                folded = folded[:-2]
            if 2 <= len(folded) <= 30:
                counts[folded] += 1

    entries = select(Entry.content).where(Entry.is_private.is_(False))
    documents = select(Document).where(Document.is_private.is_(False))
    if private_spaces:
        entries = entries.where(Entry.workspace_id.not_in(private_spaces))
        documents = documents.where(Document.workspace_id.not_in(private_spaces))
    for (content,) in session.execute(entries.order_by(Entry.id.desc()).limit(MAX_ROWS)):
        feed(content)
    for document in session.scalars(documents.order_by(Document.id.desc()).limit(MAX_ROWS)):
        feed(document.title)
        feed(document.content)
    return sorted(word for word, seen in counts.most_common(MAX_WORDS) if seen >= 2)
