"""Where `search/engine.py` registers itself for the modules beneath it.

`search_manager`, `chunks` and `ai.embeddings` need the engine's vector matrix
while the engine imports all three; naming it with `import_module` kept the
cycle. The engine registers its own module here when it loads (and
`ai/wiring.py` imports it, so every entry point has it), and they ask for it.
Before it registers, `engine()` raises, which each caller already treats as
"the matrix is unavailable" and falls back.
"""

from __future__ import annotations

from types import ModuleType

_engine: ModuleType | None = None


def register(module: ModuleType) -> None:
    global _engine
    _engine = module


def engine() -> ModuleType:
    if _engine is None:
        raise RuntimeError("the search engine is not loaded")
    return _engine
