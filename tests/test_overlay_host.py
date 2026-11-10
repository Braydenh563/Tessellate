"""The overlay's Win32 layer (BACKLOG 16, O1) against a fake `win32`: nothing
here runs on Windows, so what is checked is the shape of every call."""

from __future__ import annotations

import re
import threading
import time
from pathlib import Path
from typing import Any

import pytest

from tessellate.core.overlay import host as host_mod
from tessellate.core.overlay import win32 as k
from tests._overlay_fake import FakeWin32

PKG = Path(k.__file__).parent
DLL_CALL = re.compile(r"\b(user32|kernel32|gdi32|shcore|shell32|dwmapi)\.([A-Za-z0-9_]+)")


def wait_for(cond: Any, timeout: float = 2.0) -> bool:
    end = time.monotonic() + timeout
    while time.monotonic() < end:
        if cond():
            return True
        time.sleep(0.005)
    return False


@pytest.fixture
def started():
    events: list[tuple[str, int, int]] = []
    fake = FakeWin32()
    host = host_mod.OverlayHost(fake, on_event=lambda kind, x, y: events.append((kind, x, y)) if kind != "ready" else None)
    assert host.start()
    yield fake, host, events
    host.stop()


# --- declarations ---------------------------------------------------------------

def test_every_function_the_package_calls_has_a_signature() -> None:
    table = k.signatures()
    used = set()
    for path in PKG.glob("*.py"):
        text = path.read_text(encoding="utf-8")
        used |= {m for m in DLL_CALL.findall(text)}
    assert used
    for dll, fn in sorted(used):
        if dll not in table:
            continue
        assert fn in table[dll], f"{dll}.{fn} is called but has no restype and argtypes in win32.signatures()"


def test_every_signature_has_restype_and_argtypes_applied() -> None:
    class Func:
        pass

    class Dll:
        def __init__(self, names: Any) -> None:
            for n in names:
                setattr(self, n, Func())

    dlls = {name: Dll(fns) for name, fns in k.signatures().items()}
    assert k.apply_signatures(dlls) == []
    for name, fns in k.signatures().items():
        for fn, (res, args) in fns.items():
            func = getattr(dlls[name], fn)
            assert func.restype is res and func.argtypes == args and isinstance(func.argtypes, list)


def test_old_windows_may_lack_only_the_optional_functions() -> None:
    class Func:
        pass

    class Bare:
        pass

    dlls = {}
    for name, fns in k.signatures().items():
        d = Bare()
        for fn in fns:
            if fn not in k.OPTIONAL:
                setattr(d, fn, Func())
        dlls[name] = d
    assert set(k.apply_signatures(dlls)) == {
        "user32.SetThreadDpiAwarenessContext", "shcore.GetDpiForMonitor", "shell32.SHQueryUserNotificationState",
        "dwmapi.DwmGetWindowAttribute", "shell32.SHAppBarMessage",  # intent moved (research T1): the taskbar state is optional too
    }
    del dlls["user32"].CreateWindowExW
    with pytest.raises(AttributeError):
        k.apply_signatures(dlls)


def test_the_shared_windll_is_never_touched() -> None:
    for path in PKG.glob("*.py"):
        code = "\n".join(line for line in path.read_text(encoding="utf-8").splitlines() if not line.lstrip().startswith(("#", '"', "`")))
        assert "windll" not in code.replace("shared `ctypes.windll", ""), path.name or path


def test_load_refuses_off_windows(monkeypatch) -> None:
    monkeypatch.setattr(k.sys, "platform", "linux")
    with pytest.raises(OSError):
        k.load()


def test_ctypes_is_imported_only_in_the_overlay_files() -> None:
    assert "ctypes" in (PKG / "win32.py").read_text(encoding="utf-8")
    assert (PKG / "__init__.py").read_text(encoding="utf-8").count("import ctypes") == 0


# --- window ------------------------------------------------------------------------

def test_window_is_a_layered_noactivate_topmost_toolwindow(started) -> None:
    fake, host, _ = started
    create = next(a for d, fn, a in fake.calls if fn == "CreateWindowExW")
    style = create[0]
    for flag in (k.WS_EX_LAYERED, k.WS_EX_TOOLWINDOW, k.WS_EX_TOPMOST, k.WS_EX_NOACTIVATE):
        assert style & flag
    assert not style & 0x20  # WS_EX_TRANSPARENT would ignore the shape
    assert create[3] == k.WS_POPUP
    assert host.hwnd == 1234


def test_the_thread_asks_for_per_monitor_v2_awareness(started) -> None:
    fake, host, _ = started
    call = next(a for d, fn, a in fake.calls if fn == "SetThreadDpiAwarenessContext")
    assert call == (k.DPI_PER_MONITOR_V2,)


def test_present_draws_with_ulw_alpha_from_the_dib(started) -> None:
    fake, host, _ = started
    pixels = bytes([10, 20, 30, 128, 0, 0, 0, 0, 1, 2, 3, 255, 9, 9, 9, 9])  # 2x2 premultiplied BGRA
    host.present(pixels, 2, 2, 300, 200)
    assert wait_for(lambda: fake.layered)
    shot = fake.layered[-1]
    assert shot["pixels"] == pixels
    assert shot["at"] == (300, 200) and shot["size"] == (2, 2)
    assert shot["flags"] == k.ULW_ALPHA and shot["alpha_format"] == k.AC_SRC_ALPHA and shot["const_alpha"] == 255


def test_a_frame_of_the_wrong_length_is_refused_not_drawn(started) -> None:
    fake, host, _ = started
    host.present(b"\x00" * 5, 2, 2, 0, 0)
    time.sleep(0.1)
    assert fake.layered == []


def test_the_bitmap_is_reused_for_the_same_size_and_remade_for_another(started) -> None:
    fake, host, _ = started
    host.present(b"\x00" * 16, 2, 2, 0, 0)
    host.present(b"\x01" * 16, 2, 2, 5, 5)
    assert wait_for(lambda: len(fake.layered) == 2)
    assert fake.names("gdi32").count("CreateDIBSection") == 1
    host.present(b"\x00" * 36, 3, 3, 0, 0)
    assert wait_for(lambda: len(fake.layered) == 3)
    assert fake.names("gdi32").count("CreateDIBSection") == 2
    assert "DeleteObject" in fake.names("gdi32")


def test_a_move_is_a_bare_setwindowpos_without_size_zorder_or_focus(started) -> None:
    fake, host, _ = started
    host.move(40, 50)
    assert wait_for(lambda: any(fn == "SetWindowPos" for _, fn, _ in fake.calls))
    args = next(a for _, fn, a in fake.calls if fn == "SetWindowPos")
    assert args[1] is None and args[2:4] == (40, 50)
    assert args[6] == k.SWP_NOSIZE | k.SWP_NOZORDER | k.SWP_NOACTIVATE
    before = fake.names().count("SetWindowPos")
    host.move(40, 50)
    time.sleep(0.05)
    assert fake.names().count("SetWindowPos") == before  # same place: no call


def test_show_is_noactivate_and_logs_the_proof_line(started, caplog) -> None:
    caplog.set_level("INFO", logger=host_mod.logger.name)
    fake, host, _ = started
    host.show()
    assert wait_for(lambda: "ShowWindow" in fake.names())
    assert next(a for _, fn, a in fake.calls if fn == "ShowWindow")[1] == k.SW_SHOWNOACTIVATE
    assert wait_for(lambda: any("overlay: layered window ok, rect=(10, 20, 110, 170)" in r.getMessage() for r in caplog.records))


def test_input_messages_become_events_with_the_cursor_and_capture(started) -> None:
    fake, host, events = started
    fake.cursor = (321, 654)
    for msg in (k.WM_LBUTTONDOWN, k.WM_MOUSEMOVE, k.WM_LBUTTONUP, k.WM_RBUTTONUP):
        fake.post(msg)
    assert wait_for(lambda: len(events) == 4)
    assert events == [("down", 321, 654), ("move", 321, 654), ("up", 321, 654), ("right", 321, 654)]
    assert "SetCapture" in fake.names() and "ReleaseCapture" in fake.names()


def test_the_handler_picks_the_next_wake_and_a_timer_is_one_shot(started) -> None:
    fake, host, events = started
    host.on_event = lambda kind, x, y: 250 if kind == "tick" else None
    fake.post(k.WM_TIMER)
    assert wait_for(lambda: fake.timers.get(host_mod.TIMER_ID) == 250)
    assert "KillTimer" in fake.names()
    host.wake(1)
    assert wait_for(lambda: fake.timers.get(host_mod.TIMER_ID) == host_mod.MIN_WAKE_MS)


def test_system_messages_reassert_topmost_only_on_events(started) -> None:
    fake, host, events = started
    host.show()
    assert wait_for(lambda: host.visible)
    base = sum(1 for _, fn, a in fake.calls if fn == "SetWindowPos" and a[1] == k.HWND_TOPMOST)
    time.sleep(0.2)  # no timer re-asserts it
    assert sum(1 for _, fn, a in fake.calls if fn == "SetWindowPos" and a[1] == k.HWND_TOPMOST) == base
    fake.post(k.WM_DISPLAYCHANGE)
    fake.post(k.WM_POWERBROADCAST, k.PBT_APMRESUMEAUTOMATIC)
    fake.post(host._taskbar_msg)
    assert wait_for(lambda: sum(1 for _, fn, a in fake.calls if fn == "SetWindowPos" and a[1] == k.HWND_TOPMOST) == base + 3)
    kinds = [e[0] for e in events]
    assert "display" in kinds and "resume" in kinds and "taskbar" in kinds
    fake.post(k.WM_POWERBROADCAST, k.PBT_APMSUSPEND)
    assert wait_for(lambda: "suspend" in [e[0] for e in events])


def test_a_failing_handler_or_command_never_leaves_the_window_procedure(started) -> None:
    fake, host, events = started

    def boom(kind: str, x: int, y: int) -> int:
        raise RuntimeError("bug")

    host.on_event = boom
    fake.post(k.WM_LBUTTONDOWN)
    host.present(b"\x00", 2, 2, 0, 0)  # wrong size: logged, loop continues
    fake.post(k.WM_MOUSEMOVE)
    host.move(1, 2)
    assert wait_for(lambda: any(fn == "SetWindowPos" for _, fn, _ in fake.calls))


def test_an_exception_in_the_procedure_answers_defwindowproc(started, monkeypatch) -> None:
    fake, host, _ = started
    monkeypatch.setattr(host, "_message", lambda *a: (_ for _ in ()).throw(ValueError("x")))
    before = fake.names().count("DefWindowProcW")
    assert host._wndproc(1234, k.WM_MOUSEMOVE, 0, 0) == 0
    assert fake.names().count("DefWindowProcW") == before + 1


def test_the_callback_is_kept_alive_in_a_module_reference(started) -> None:
    fake, host, _ = started
    assert host._proc in host_mod._CALLBACKS
    host.stop()
    assert host._proc not in host_mod._CALLBACKS


def test_all_win32_calls_run_on_the_overlay_thread_except_post(started) -> None:
    fake, host, _ = started
    host.present(b"\x00" * 16, 2, 2, 1, 1)
    host.move(3, 4)
    host.show()
    assert wait_for(lambda: host.visible)
    here = threading.get_ident()
    for fn in ("UpdateLayeredWindow", "ShowWindow", "CreateWindowExW", "CreateDIBSection"):
        ids = fake.threads.get(fn, set())
        assert ids and here not in ids, fn


def test_stop_posts_close_and_joins_within_a_second() -> None:
    fake = FakeWin32()
    host = host_mod.OverlayHost(fake)
    assert host.start()
    t0 = time.monotonic()
    assert host.stop(timeout=1.0)
    assert time.monotonic() - t0 < 1.0
    assert not host.alive
    names = fake.names()
    assert "DestroyWindow" in names and "UnregisterClassW" in names and "DeleteDC" in names
    assert host.stop()  # again: nothing to do


def test_a_failed_window_reports_and_ends_the_thread(caplog) -> None:
    class Failing(FakeWin32):
        def _CreateWindowExW(self, *a: Any) -> int:
            return 0

    host = host_mod.OverlayHost(Failing())
    assert host.start() is False
    assert "CreateWindowExW failed" in (host._error or "")
    assert host.stop()


def test_calls_before_start_or_after_stop_do_nothing() -> None:
    host = host_mod.OverlayHost(FakeWin32())
    host.present(b"\x00" * 4, 1, 1, 0, 0)
    host.show()
    assert not host.alive


def test_the_owner_hears_ready_once_on_the_overlay_thread_and_a_failure_there_fails_start() -> None:
    seen: list[tuple[str, int]] = []
    host = host_mod.OverlayHost(FakeWin32(), on_event=lambda kind, x, y: seen.append((kind, threading.get_ident())))
    assert host.start()
    assert [k for k, _ in seen] == ["ready"] and seen[0][1] != threading.get_ident()
    host.stop()

    def boom(kind: str, x: int, y: int) -> None:
        raise OSError("no frames")

    bad = host_mod.OverlayHost(FakeWin32(), on_event=boom)
    assert bad.start() is False and "no frames" in (bad._error or "")
    assert bad.stop()


def test_a_loop_that_ends_on_its_own_tells_the_owner_but_a_stop_does_not() -> None:
    gone: list[int] = []
    fake = FakeWin32()
    host = host_mod.OverlayHost(fake, on_exit=lambda: gone.append(1))
    assert host.start()
    fake.post(k.WM_QUIT)
    assert wait_for(lambda: gone)
    assert not host.alive
    fake2 = FakeWin32()
    quiet: list[int] = []
    host2 = host_mod.OverlayHost(fake2, on_exit=lambda: quiet.append(1))
    assert host2.start()
    host2.stop()
    time.sleep(0.05)
    assert not quiet


def test_a_window_that_comes_up_after_the_owner_gave_up_closes_itself() -> None:
    """INBOX 1692 (k): the frames loaded one second past a 3 s wait; the window then stayed on the desktop with no owner."""
    release = threading.Event()
    gone: list[int] = []

    def slow(kind: str, x: int, y: int) -> None:
        if kind == "ready":
            release.wait(2.0)

    host = host_mod.OverlayHost(FakeWin32(), on_event=slow, on_exit=lambda: gone.append(1))
    assert host.start(timeout=0.05) is False
    host.stop(timeout=0.01)  # what the runner does on a timeout
    release.set()
    assert wait_for(lambda: not host._thread.is_alive())  # noqa: SLF001
    assert not host.alive and gone == []
