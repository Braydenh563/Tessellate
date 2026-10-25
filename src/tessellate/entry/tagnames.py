"""The one rule for what a list of tags may hold.

Its own module, with no imports from the app, because two layers need the
same rule and neither may import the other: `api/schemas.py` (every HTTP
write of tags) and `entry/manager.py` (every in-process write: the AI tools,
the librarian, imports, renames). A rule kept in two copies is how this bug
happened in the first place: the schema already dropped blanks while the
manager and the tag rename did not, so a blank tag still reached four notes
through `POST /tags/rename`.
"""

from __future__ import annotations

import re
from collections.abc import Iterable

#: A tag is a label. 50,000 characters was once accepted as one, which is a
#: chip 50,000 characters wide in every list the note appears in. 60 is twice
#: what `librarian.py` already allows itself when it suggests one.
MAX_TAG_LENGTH = 60


def normalise_tags(tags: Iterable[object] | None) -> list[str]:
    """Trimmed, clipped, blank-free, and each tag once regardless of case.

    The first spelling wins: a note tagged "Idea" that is then sent "idea" as
    well keeps "Idea", because that is the spelling the person chose first
    and the one already on screen. Folding by `casefold` rather than `lower`
    so "Straße" and "STRASSE" are the same label, as a reader would take
    them. Stored as sent, ['Idea', 'idea', 'IDEA'] was three chips and three
    rows in the tag list for one idea (measured 2026-10-03).

    Clipped rather than refused: a save that fails because one tag was long
    throws away the note, which is a worse answer than a shortened tag.
    """
    out: list[str] = []
    seen: set[str] = set()
    for raw in tags or ():
        if raw is None:
            continue
        #: "#biology" is the tag "biology": the mark is how a tag is drawn and
        #: written, not part of its name (it was stored as "##biology").
        tag = str(raw).strip().lstrip("#").strip()[:MAX_TAG_LENGTH].strip()
        if not tag:
            continue
        key = tag.casefold()
        if key in seen:
            continue
        seen.add(key)
        out.append(tag)
    return out


#: `#word` written in a note's own text (INBOX 434: "tag with #", the way
#: Bear, Obsidian and Drafts all read a note). A tag starts with a letter, so
#: `#42` (an issue number) and `# Heading` (a space after the mark) are not
#: tags; the mark must follow the start of a line, a space or an opening
#: bracket, so a URL's `page#section`, an HTML entity's `&#39;` and the
#: second `#` of `##` are not either. Letters, digits, `_`, `-` and `/` after
#: that, so `#project/garden` nests the way the tag list already draws it.
_INLINE_TAG = re.compile(r"(?:(?<=^)|(?<=[\s\[]))#([^\W\d_][\w/-]*)", re.MULTILINE)
#: Code is quoted text, never the writer's labels: a fenced block's
#: `#include` or a `#define` in backticks must not become a tag.
_FENCED = re.compile(r"^(`{3,}|~{3,})[^\n]*\n.*?^\1[ \t]*$", re.MULTILINE | re.DOTALL)
_CODE_SPAN = re.compile(r"`[^`\n]*`")
#: A colour (`#3b82f6`, `#ff0000`) is a value, not a label. Only hex with a
#: digit in it: `#cafe` and `#bed` are words a person may well tag with.
_HEX_COLOUR = re.compile(r"^(?=[0-9a-fA-F]*\d)(?:[0-9a-fA-F]{3,4}|[0-9a-fA-F]{6}|[0-9a-fA-F]{8})$")


def inline_tags(text: str | None) -> list[str]:
    """The `#tags` written in `text`, in the order they appear, each once.

    The marks stay in the text (as in Bear): the note reads as it was
    written, and the tag list is where the label is kept and searched."""
    if not text:
        return []
    body = _CODE_SPAN.sub(" ", _FENCED.sub(" ", text))
    found = []
    for match in _INLINE_TAG.finditer(body):
        tag = match.group(1).rstrip("-/")
        if tag and not _HEX_COLOUR.match(tag):
            found.append(tag)
    return normalise_tags(found)
