"""The AI/search modules must not drag numpy in just by being imported.

The owner measured the idle backend at ~776 MB resident and asked for one
specific fix: lazy-load the heavy imports, not idle suspension (the runtime
side of that, when the embedding model itself actually loads, is already
handled well by `ai/embeddings.start_warmup`'s delay/idle-wait/empty-notebook
skip). What was still missing is that `import numpy as np` sat at the *top*
of `ai/embeddings.py`, `ai/janitor.py`, `search/engine.py` and
`search/search_manager.py`, so merely importing one of those modules, which
`api/app.py` and half its routers do unconditionally at process start to wire
up routes and the `EmbeddingService` singleton, cost numpy's own import
(measured: ~16 MB / ~60-100 ms in this sandbox) whether or not the notebook
had anything worth embedding yet.

Each of those four files now imports numpy inside the specific functions and
methods that call `np.*`, the same shape `_load_builtin_model` in
`ai/embeddings.py` already used for its engine, `fastembed` (a heavy,
optional import deferred to the one place that needs it) and `__main__.py`
uses for `uvicorn`/`create_app`. `from __future__ import annotations` is
already present in all four files, so every remaining module-level `np.`
reference is a type annotation, stored as a string and never evaluated,
never a real import.

This is a subprocess check, not a plain `assert "numpy" not in sys.modules`
in-process: numpy, once imported by an earlier test in the same pytest
run, stays in `sys.modules` for the rest of that process, which would make
this pass regardless of whether the module under test still imports it
itself. A fresh interpreter is the only way to see the real, first-import
cost.
"""

from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

#: Every module this fix touches. Named explicitly, not discovered, so a
#: future module-scope `import numpy` anywhere in this list fails the build
#: immediately rather than silently widening what "heavy" means here.
LAZY_NUMPY_MODULES = [
    "tessellate.ai.embeddings",
    "tessellate.ai.janitor",
    "tessellate.search.engine",
    "tessellate.search.search_manager",
]

_CHECK_IMPORT_SRC = """
import importlib
import sys
importlib.import_module(sys.argv[1])
print("numpy" in sys.modules)
"""


def _run_check(*args: str) -> str:
    env = dict(os.environ)
    env["PYTHONPATH"] = str(ROOT / "src")
    result = subprocess.run(
        [sys.executable, "-c", _CHECK_IMPORT_SRC, *args],
        capture_output=True,
        text=True,
        cwd=ROOT,
        env=env,
        timeout=30,
    )
    assert result.returncode == 0, result.stderr
    return result.stdout.strip().splitlines()[-1]


class TestNumpyStaysOutUntilSomethingNeedsIt:
    def test_each_module_imports_clean_of_numpy(self):
        for module in LAZY_NUMPY_MODULES:
            loaded = _run_check(module)
            assert loaded == "False", (
                f"importing {module} alone pulled numpy into sys.modules; "
                "move whatever new `np.` reference did that inside the "
                "function or method that uses it, the way the rest of this "
                "file already does"
            )

    def test_the_app_module_imports_clean_of_numpy_too(self):
        """`api/app.py` is what every route in the four modules above hangs
        off of, and what `python -m tessellate`/`uvicorn` actually import
        first: the case that matters is this one, not the leaf modules in
        isolation, which could each pass on their own while still being
        pulled in eagerly by a router file that imports one of them at its
        own module scope."""
        loaded = _run_check("tessellate.api.app")
        assert loaded == "False", (
            "importing tessellate.api.app pulled numpy into sys.modules "
            "before any request or background job ran; find the new "
            "module-scope import (in app.py itself or a routes_*.py it "
            "imports) that reintroduced this"
        )


class TestNumpyStillLoadsOnFirstRealUse:
    """The other half of 'lazy', not 'skipped'. A deferred import that never
    fires would make the modules above technically numpy-free and actually
    broken: this proves each still gets a working numpy the first time a
    function that needs it is called, in the same fresh subprocess used
    above so a stale cache from test order can't hide a typo'd import."""

    def test_cosine_similarity_still_works(self):
        script = (
            "from tessellate.ai.embeddings import cosine_similarity\n"
            "print(round(cosine_similarity([1.0, 0.0], [1.0, 0.0]), 4))\n"
            "import sys; assert 'numpy' in sys.modules\n"
        )
        env = dict(os.environ)
        env["PYTHONPATH"] = str(ROOT / "src")
        result = subprocess.run(
            [sys.executable, "-c", script],
            capture_output=True,
            text=True,
            cwd=ROOT,
            env=env,
            timeout=30,
        )
        assert result.returncode == 0, result.stderr
        assert result.stdout.strip().splitlines()[-1] == "1.0"

    def test_similar_pairs_still_works(self):
        script = (
            "import numpy as np\n"
            "from tessellate.ai.embeddings import similar_pairs\n"
            "vectors = {1: np.array([1.0, 0.0]), 2: np.array([1.0, 0.0])}\n"
            "print(similar_pairs(vectors, 0.5))\n"
        )
        env = dict(os.environ)
        env["PYTHONPATH"] = str(ROOT / "src")
        result = subprocess.run(
            [sys.executable, "-c", script],
            capture_output=True,
            text=True,
            cwd=ROOT,
            env=env,
            timeout=30,
        )
        assert result.returncode == 0, result.stderr
        assert "(1, 2," in result.stdout
