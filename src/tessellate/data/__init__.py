"""Static tables, kept as JSON beside this module and read on first use.

Brief 62 (LEDGER L699): the composer's word tables ran to 280 KB of Python
literals that were compiled into dicts on every start whether or not a
question was ever typed. They live here as files now. `table(name)` reads one
once and keeps it; `LazyTable` stands in for a module-level dict so call sites
(`word in SLANG`, `SLANG[word]`, `SLANG.update(...)`) stay as they were while
the file is read only at the first lookup. Packaged by `pyproject.toml`
(`package-data`) and the two PyInstaller specs.
"""

from __future__ import annotations

import json
from collections.abc import Callable, Iterator, MutableMapping
from pathlib import Path

DATA_DIR = Path(__file__).parent
_LOADED: dict[str, object] = {}


def table(name: str) -> object:
    """The parsed content of `name` (a file in this folder), read once."""
    if name not in _LOADED:
        _LOADED[name] = json.loads((DATA_DIR / name).read_text(encoding="utf-8"))
    return _LOADED[name]


def loaded() -> frozenset[str]:
    """The files read so far (the import-time test asserts importing reads none)."""
    return frozenset(_LOADED)


class LazyTable(MutableMapping):
    """A dict whose file is read on first use. Insertion order is the file's."""

    def __init__(self, name: str, convert: Callable[[object], dict] = dict) -> None:
        self._name = name
        self._convert = convert
        self._data: dict | None = None

    @property
    def data(self) -> dict:
        if self._data is None:
            self._data = self._convert(table(self._name))
        return self._data

    def __getitem__(self, key):  # noqa: ANN001
        return self.data[key]

    def __setitem__(self, key, value) -> None:  # noqa: ANN001
        self.data[key] = value

    def __delitem__(self, key) -> None:  # noqa: ANN001
        del self.data[key]

    def __iter__(self) -> Iterator:
        return iter(self.data)

    def __len__(self) -> int:
        return len(self.data)

    def __contains__(self, key: object) -> bool:
        return key in self.data

    def __repr__(self) -> str:
        return f"LazyTable({self._name!r})"


def deep_tuple(value: object) -> object:
    """JSON lists back to the tuples the Python literals were (nested too)."""
    if isinstance(value, list):
        return tuple(deep_tuple(v) for v in value)
    return value
