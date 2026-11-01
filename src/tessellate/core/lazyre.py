"""A regular expression compiled on first use, not at import.

The composer's import budget is 0.2 s cold (tests/test_engine_budgets.py), and
`ai/recognise.py` alone spent about 20 ms of it compiling 64 patterns that a
given question mostly never reaches. A `LazyPattern` answers everything a
compiled pattern does (`search`, `sub`, `finditer`, `pattern`, `flags`) and
compiles once, on the first call that needs the engine.

It is not a `re.Pattern`: pass it to its own methods (`P.sub(...)`), never as
the first argument of `re.sub(P, ...)`.
"""

from __future__ import annotations

import re
import threading

_lock = threading.Lock()


class LazyPattern:
    __slots__ = ("pattern", "flags", "_compiled")

    def __init__(self, pattern: str, flags: int = 0) -> None:
        self.pattern = pattern
        self.flags = flags
        self._compiled: re.Pattern[str] | None = None

    def compiled(self) -> re.Pattern[str]:
        if self._compiled is None:
            with _lock:
                if self._compiled is None:
                    self._compiled = re.compile(self.pattern, self.flags)
        return self._compiled

    def __getattr__(self, name: str):
        return getattr(self.compiled(), name)

    def __repr__(self) -> str:
        return f"LazyPattern({self.pattern!r})"


def lazy_compile(pattern: str, flags: int = 0) -> LazyPattern:
    return LazyPattern(pattern, flags)
