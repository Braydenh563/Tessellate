"""What counts as blank, and what two names are the same name.

Its own module with no imports from the app, for the reason `tagnames.py` is:
the HTTP models, the managers and the routes all need the same answer, and a
rule kept in three copies is how a note of nothing but zero-width spaces got
saved (audit 1029 N6, N15, rank 10).

Applies to what arrives. Nothing here rewrites a stored value.
"""

from __future__ import annotations

import re
import unicodedata

#: Zero-width joiner: it glues an emoji sequence (a family, a flag with a
#: skin tone) into one picture, so `clean_name` keeps it. It still draws
#: nothing, so `is_blank` and `name_key` count it as nothing.
_JOINER = "‍"


def _format(ch: str) -> bool:
    """A format character: zero-width space, word joiner, byte-order mark,
    bidi controls, soft hyphen. It draws nothing."""
    return unicodedata.category(ch) == "Cf"


def is_blank(text: str | None) -> bool:
    """True for nothing, spaces, and spaces mixed with invisible characters."""
    return all(ch.isspace() or _format(ch) for ch in text or "")


def strip_invisible(text: str | None) -> str:
    """`text` without its invisible characters (a joiner stays: it holds an
    emoji together)."""
    return "".join(ch for ch in text or "" if ch == _JOINER or not _format(ch))


def clean_name(text: str | None) -> str:
    """A name as it is stored: invisible characters dropped, every run of
    spacing one space, the ends trimmed."""
    return re.sub(r"\s+", " ", strip_invisible(text)).strip()


def name_key(text: str | None) -> str:
    """What two names are compared by: the same name whatever its case,
    spacing, or invisible characters (a joiner included)."""
    return " ".join("".join(ch for ch in text or "" if not _format(ch)).split()).casefold()


def import_path(name: str | None, fallback: str = "") -> str:
    """The name an imported note remembers as its `source_path` (audit 1031
    N22): forward slashes, relative, no `.` or `..` step, no invisible
    characters, 500 at most. A browser's directory picker sends `vault/a.md`,
    which stays; `../../evil.md` becomes `evil.md`."""
    parts = [
        piece
        for piece in strip_invisible(str(name or "")).replace("\\", "/").split("/")
        if piece.strip() and piece.strip() not in (".", "..")
    ]
    return "/".join(parts)[:500] or fallback
