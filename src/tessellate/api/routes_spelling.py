"""`GET /spelling/own-words`: the words the person's own notes use twice or more
(INBOX 1731).

The spelling second opinion (`frontend/js/harper-worker.js`) never flags a word
the person has written at least twice: "arvo", "doco", a friend's surname. The
page sends this list to the worker, which keeps it in memory.

**Private notes never contribute.** A note or document marked private, and
every row in a private space, is left out whether or not the private spaces are
open this session: the list is sent to a worker and shown in nobody's menu, but
a word that only a private note uses must not become a word the checker knows,
because then the checker's silence about it would say something about the
private note.
"""

from __future__ import annotations

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from tessellate.core.deps import get_session
from tessellate.repo.spelling import own_words

router = APIRouter(tags=["spelling"])


@router.get("/spelling/own-words")
def get_own_words(session: Session = Depends(get_session)) -> dict:
    return {"words": own_words(session)}
