"""The server caps glibc's per-thread malloc arenas (L609): 8-way load grew RSS
393 MB to 1.2 GB over 15 minutes with 196 MB traced; two arenas held 385 to 400 MB."""

import subprocess
import sys

M_ARENA_MAX = -8


def _run(code: str, env_extra: dict | None = None) -> str:
    import os

    env = {**os.environ, "PYTHONPATH": "src"}
    env.pop("MALLOC_ARENA_MAX", None)
    env.update(env_extra or {})
    return subprocess.run([sys.executable, "-c", code], env=env, capture_output=True, text=True, check=True).stdout


PROBE = """
import ctypes
calls = []
real = ctypes.CDLL
class Spy:
    def __init__(self, lib): self.lib = lib
    def __getattr__(self, name):
        if name != "mallopt": return getattr(self.lib, name)
        def mallopt(opt, val):
            calls.append((opt, val)); return self.lib.mallopt(opt, val)
        return mallopt
ctypes.CDLL = lambda *a, **k: Spy(real(*a, **k))
import tessellate
print(calls)
"""


def test_import_asks_for_two_arenas():
    if not sys.platform.startswith("linux"):
        return
    assert _run(PROBE).strip() == str([(M_ARENA_MAX, 2)])


def test_a_persons_own_setting_wins():
    assert _run(PROBE, {"MALLOC_ARENA_MAX": "8"}).strip() == "[]"
