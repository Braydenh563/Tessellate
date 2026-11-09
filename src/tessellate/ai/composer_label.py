"""A bare label sentence ("Plot 14.") asked by its words (R9-3, composer audit round 9).

"What is plot 14" and "what's my allotment plot number" are answered by the note's own two-word line, which a
quoted list of other sentences ("Plant garlic in November") used to push aside. Questions are read
whitespace-normalised with literal spaces, so the patterns stay linear."""

from __future__ import annotations

import re

from tessellate.ai import composer_lists

_WHAT_IS = re.compile(r"^what(?:'s| is) (?:my |the |our )?(?P<label>[a-z]{2,20} \d{1,6})$", re.I)
_WHICH_NUMBER = re.compile(r"^what(?:'s| is) (?:my |the |our )?(?P<owner>[a-z]{2,20}) (?P<noun>[a-z]{2,20}) (?:number|no)$", re.I)
_LABEL_LINE = re.compile(r"^(?P<noun>[A-Za-z]{2,20}) (?P<number>\d{1,6})$")


def _labels(views: list):  # noqa: ANN202
    for view in views:
        for s in view.sentences:
            found = _LABEL_LINE.match(s.text.strip().rstrip("."))
            if found:
                yield view, s, found


def answer(out, asked: str, views: list) -> bool:  # noqa: ANN001
    """Say the label line the question asks for (with its note); False when it is none of these."""
    text = " ".join(str(asked or "").split()).rstrip("?.! ")
    if len(text) > 120:
        return False
    named = _WHAT_IS.match(text)
    owned = _WHICH_NUMBER.match(text)
    for view, s, label in _labels(views):
        said = f"{label['noun']} {label['number']}".lower()
        if named and named["label"].lower() == said:
            line = f"{s.text.strip().rstrip('.')} is your {str(view.title).lower()}." if view.titled else f"{s.text.strip()}"
        elif owned and owned["noun"].lower() == label["noun"].lower() and owned["owner"].lower() in f"{view.title} {view.note.get('content')}".lower():
            line = f"{s.text.strip().rstrip('.')} ({composer_lists._title(view)})."  # noqa: SLF001
        else:
            continue
        out.lines.append(line)
        composer_lists._cite(out, view, s, line)  # noqa: SLF001
        return True
    return False
