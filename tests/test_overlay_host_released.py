"""L-general-71: a stopped overlay runner stays alive on Python 3.11. Its window procedure is a ctypes callback that
holds the host's bound method; the host holds it back, and 3.11's collector cannot see through the callback, so the
cycle (and the runner's pictures, about 170 MB at 2560x1504 and dpi 192) was never freed. Twenty runners in one test
worker reached 6 GB and the kernel killed it (CI Tests 3.11 leg 1 lost its runner). Teardown drops the callback once
the window class is gone, as Windows does on UnregisterClassW. Fixed clock."""

from __future__ import annotations

import gc
import weakref

import pytest

pytest.importorskip("PIL")

from tests.test_overlay_runner import make  # noqa: E402


def test_a_stopped_runner_and_its_host_are_freed() -> None:
    r, fake, *_ = make()
    assert r.start()
    host = weakref.ref(r.host)
    runner = weakref.ref(r)
    r.stop()
    assert host()._proc is None and fake.wndproc is None
    del r, fake, _
    gc.collect()
    assert host() is None and runner() is None
