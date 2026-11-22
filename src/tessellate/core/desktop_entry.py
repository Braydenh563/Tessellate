"""The launcher module, registered rather than imported (L-world-class-791).

`tessellate.__main__` imports the app, which imports Settings, which needs the
launcher's restart verbs: an `import` (or `importlib`) in Settings closed a
cycle through the whole app. The launcher registers itself here when it is
imported, and Settings asks here, so the dependency points one way.
"""

from __future__ import annotations

import sys
from types import ModuleType

_registered: ModuleType | None = None


def register(module: ModuleType) -> None:
    global _registered
    _registered = module


def current() -> ModuleType:
    """The desktop entry module, the one actually running.

    `sys.modules["__main__"]` first: a packaged build runs `__main__.py` as
    `__main__`, and PyInstaller bundles no second copy under the name
    `tessellate.__main__`. From source, `python -m tessellate` is the same
    module under the same key. The registered module is the fallback for
    everything else (tests, `uvicorn --factory`), where the running
    `__main__` is not ours.
    """
    running = sys.modules.get("__main__")
    if running is not None and hasattr(running, "restart_in_console_mode"):
        return running
    if _registered is None:
        raise RuntimeError("the desktop launcher is not loaded")
    return _registered
