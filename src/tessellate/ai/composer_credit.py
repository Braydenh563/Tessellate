"""Who made a work, said from the notes or said as not written (R9-9, composer audit round 9).

"Who wrote Wolf Hall" is answered by a sentence that names the work and its maker ("by Hilary Mantel"); a note that only
mentions the work ("Started Wolf Hall") is not an answer, so the reply says the notes do not say. The question is read
whitespace-normalised, with literal spaces and bounded lengths, so it stays linear."""

from __future__ import annotations

import re

from tessellate.ai import composer_lists

_WHO_MADE = re.compile(r"^who (?P<verb>wrote|authored|directed|painted|composed|created|designed|sang|performed) (?P<what>.{1,80})$", re.I)
_CREDIT = re.compile(r"\bby [A-Z][a-z]+|\b(?:wrote|written|authored|author|directed|painted|composed|created|designed)\b")
_SKIP = frozenset({"the", "a", "an", "of", "my", "it"})


def _words(text: str) -> list[str]:
    return [w for w in re.findall(r"[a-z0-9']+", text.lower()[:200]) if w not in _SKIP]


def answer(out, asked: str, views: list) -> bool:  # noqa: ANN001
    """Say who made the work asked about, or that no note says; False when `asked` is not a "who wrote X" or no note names X."""
    text = " ".join(str(asked or "").split()).rstrip("?.! ")
    found = _WHO_MADE.match(text) if len(text) < 300 else None
    wanted = _words(found["what"]) if found else []
    if not wanted:
        return False
    naming = [(v, s) for v in views for s in v.sentences if all(w in s.text.lower() for w in wanted)]
    if not naming:
        return False
    for view, s in naming:
        if _CREDIT.search(s.text):
            line = f"{s.text.strip().rstrip('.')} ({composer_lists._title(view)})."  # noqa: SLF001
            out.lines.append(line)
            composer_lists._cite(out, view, s, line)  # noqa: SLF001
            return True
    line = f"Your notes do not say who {found['verb'].lower()} {found['what'].strip()}."
    out.lines.append(line)
    composer_lists._cite(out, naming[0][0], naming[0][1], line)  # noqa: SLF001
    return True
