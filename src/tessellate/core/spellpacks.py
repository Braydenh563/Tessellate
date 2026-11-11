"""Spelling packs for other languages (D30, owner decision 2026-11-11).

The packs are extras (`core/extras.py`, the download kind): a Hunspell word list per language,
fetched to `<data dir>/extras/spell-<lang>` on an Install click and never vendored. This module
is the page's view of them: which languages exist, which are installed, and where the two files
are. A disk look only; the network belongs to the Install click and nothing here touches it.
"""

from __future__ import annotations

from pathlib import Path

from tessellate.core import extras

#: The languages, in the order Settings lists them, with the name a person sees. The same three
#: as `extras._SPELL_PACKS`; a language there without a name here is a test failure.
NAMES = {"fr": "French", "de": "German", "es": "Spanish"}

#: The two files a pack serves, by the name the URL uses.
KINDS = ("aff", "dic")


def extra_id(lang: str) -> str:
    return f"spell-{lang}"


def installed(lang: str) -> bool:
    return files(lang, "aff") is not None


def files(lang: str, kind: str) -> Path | None:
    """The installed `.aff` or `.dic` of a language, or None for an unknown language or file or
    a pack that is not installed."""
    if lang not in NAMES or kind not in KINDS:
        return None
    folder = extras.download_ready(extra_id(lang))
    if folder is None:
        return None
    path = folder / f"{lang}.{kind}"
    return path if path.is_file() else None


def listing() -> list[dict]:
    return [
        {"lang": lang, "id": extra_id(lang), "name": name, "installed": installed(lang)}
        for lang, name in NAMES.items()
        if extra_id(lang) in extras.EXTRAS_BY_ID
    ]
