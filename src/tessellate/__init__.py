"""Tessellate: a 100% offline, local-first AI notebook."""

__version__ = "0.6.1"

#: Where a support bundle goes (the owner, 2026-09-14: "suggest that they
#: download the support bundle and send it to my email ... even open the
#: email dialogue for them"). The frontend carries the same string in
#: app.js; tests/test_support_email.py keeps the two equal.
SUPPORT_EMAIL = "brayden.hoyle@outlook.com"


def _adopt_old_environment() -> None:
    #: Settings written before the rename (a `.env`, a compose file, a
    #: shortcut) say `MEMORYMAP_*`. Each one is copied to its `TESSELLATE_*`
    #: name unless that is set, so every reader and every child process sees
    #: the new name (`core/envnames.py` has the per-read form).
    import os

    for key, value in list(os.environ.items()):
        if key.startswith("MEMORYMAP_"):  # brand: keep
            os.environ.setdefault("TESSELLATE_" + key[len("MEMORYMAP_"):], value)  # brand: keep


_adopt_old_environment()
