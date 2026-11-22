"""Tessellate: a 100% offline, local-first AI notebook."""

__version__ = "0.7.0"

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


def _single_thread_blas() -> None:
    #: The search matrix products are 5,000 x 384 (0.7 ms on one thread). OpenBLAS's
    #: default pool of one thread per core spins for longer than the product takes:
    #: measured on 4 vCPUs, `matrix @ query` 15.5 ms with four threads, 0.7 ms with one,
    #: and engine.search at 5,000 notes p50 50 ms (L635). Set before numpy loads;
    #: a person's own value still wins (`setdefault`).
    import os

    for name in ("OPENBLAS_NUM_THREADS", "OMP_NUM_THREADS"):
        os.environ.setdefault(name, "1")


_single_thread_blas()


def _cap_malloc_arenas() -> None:
    #: glibc gives each thread that allocates its own 64 MB arena, up to eight per core, and
    #: keeps what a request freed there. The server runs a pool of worker threads, so under
    #: eight parallel clients over 4,500 notes resident memory went 393 MB to 1.2 GB in 15
    #: minutes with only 196 MB of it traced by Python (anonymous mappings, 28 arenas); the
    #: same load with two arenas stayed at 385 to 400 MB for 8 minutes (L609). `mallopt`
    #: rather than the environment variable, which glibc reads at its first allocation,
    #: before any Python runs. A person's own `MALLOC_ARENA_MAX` still wins; on a libc
    #: without `mallopt` (macOS, Windows, musl) there is nothing to cap and nothing happens.
    import os

    if os.environ.get("MALLOC_ARENA_MAX"):
        return
    try:
        import ctypes

        ctypes.CDLL("libc.so.6").mallopt(-8, 2)  # M_ARENA_MAX
    except (OSError, AttributeError):
        pass


_cap_malloc_arenas()
