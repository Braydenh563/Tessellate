"""A module that imports on first attribute use, for heavy imports a cold start does not need."""

from __future__ import annotations

import importlib


class LazyModule:
    """Stands in for a module; the first read, write or delete of an attribute
    imports it and forwards, so `monkeypatch.setattr(proxy, ...)` patches the real module."""

    __slots__ = ("_name",)

    @property
    def __dict__(self):  # type: ignore[override]
        # pytest's monkeypatch reads the old value from `__dict__`; the real module's is the truth.
        return vars(self._mod())

    def __init__(self, name: str) -> None:
        object.__setattr__(self, "_name", name)

    def _mod(self):
        return importlib.import_module(object.__getattribute__(self, "_name"))

    def __getattr__(self, attr: str):
        return getattr(self._mod(), attr)

    def __setattr__(self, attr: str, value) -> None:
        setattr(self._mod(), attr, value)

    def __delattr__(self, attr: str) -> None:
        delattr(self._mod(), attr)
