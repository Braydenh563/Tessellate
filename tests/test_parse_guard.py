"""Untrusted files are parsed in a child process with a time and memory limit
(L-world-class-321, SECURITY.md T19).

The fakes in `tests/_parse_fakes.py` stand in for a crafted file: a parser
that never returns, one that allocates without end, one that kills the
interpreter. Each must leave the server answering, give the person a
sentence, and leave the next file readable.
"""

from __future__ import annotations

import os
import sys

import pytest

from tessellate.api import routes_settings_transfer
from tessellate.core import ocr, parse_guard, pdfpages
from tessellate.core import docview
from tessellate.entry import importer
from tests import _parse_fakes as fakes


@pytest.fixture(autouse=True)
def _children(monkeypatch):
    monkeypatch.delenv("TESSELLATE_PARSE_INLINE", raising=False)
    yield
    parse_guard.stop_all()


def test_the_app_parses_in_a_child_unless_told_not_to(monkeypatch):
    assert parse_guard.enabled()
    monkeypatch.setenv("TESSELLATE_PARSE_INLINE", "1")
    assert not parse_guard.enabled()


def test_every_named_reader_is_wrapped():
    for fn in (
        importer.convert_to_markdown,
        docview.docx_to_markdown,
        pdfpages._count_pages,
        pdfpages._render_all,
        pdfpages._draw_page,
        ocr.extract_text,
        ocr.extract_region_text,
        ocr.extract_regions,
    ):
        assert hasattr(fn, "__wrapped__"), f"{fn.__name__} parses an upload in the server process"


def test_a_call_runs_in_another_process_and_the_child_is_kept():
    first_pid, value = fakes.whose_process("a page")
    assert value == "a page"
    assert first_pid != os.getpid()
    assert fakes.whose_process("again")[0] == first_pid


def test_a_parser_that_never_returns_is_stopped_and_the_next_file_reads():
    before, _ = fakes.whose_process("before")
    with pytest.raises(parse_guard.ParseStopped) as stopped:
        fakes.loops_forever("crafted.pdf")
    assert str(stopped.value) == parse_guard.TIMED_OUT
    after, value = fakes.whose_process("after")
    assert value == "after" and after != before


@pytest.mark.skipif(sys.platform == "win32", reason="Windows has the time limit only (L-world-class-690)")
def test_a_huge_allocation_fails_in_the_child_not_the_server(monkeypatch):
    monkeypatch.setattr(parse_guard, "MEMORY_BYTES", 768 * 1024**2)
    with pytest.raises(parse_guard.ParseStopped) as stopped:
        fakes.allocates(4 * 1024**3)
    assert str(stopped.value) == parse_guard.TOO_BIG
    assert fakes.allocates(1024) == 1024


@pytest.mark.skipif(sys.platform == "win32", reason="SIGSEGV by signal is POSIX")
def test_a_parser_that_crashes_the_interpreter_leaves_the_server_up():
    with pytest.raises(parse_guard.ParseStopped) as stopped:
        fakes.crashes()
    assert str(stopped.value) == parse_guard.CRASHED
    assert fakes.whose_process("still here")[1] == "still here"


def test_an_ordinary_parse_error_comes_back_as_itself():
    with pytest.raises(ValueError, match="not a real document"):
        fakes.fails()


def test_a_never_raises_reader_answers_its_empty_value_when_stopped():
    assert fakes.pages_forever("crafted.pdf") == []


def test_inline_mode_runs_in_this_process(monkeypatch):
    monkeypatch.setenv("TESSELLATE_PARSE_INLINE", "1")
    assert fakes.whose_process("here")[0] == os.getpid()


def test_the_server_survives_a_document_that_hangs_and_says_why(client, monkeypatch):
    monkeypatch.setattr(routes_settings_transfer.importer, "markitdown_available", lambda: True)
    monkeypatch.setattr(routes_settings_transfer.importer, "convert_to_markdown", fakes.convert_forever)
    response = client.post(
        "/import/document", files={"file": ("crafted.pdf", b"%PDF-1.7 crafted", "application/pdf")}
    )
    assert response.status_code == 422
    assert response.json()["detail"].startswith("Reading that file was stopped because it took too long")
    assert client.get("/entries?limit=1").status_code == 200


class _FakeKernel32:
    """Stands in for `ctypes.WinDLL("kernel32")`: records each call."""

    def __init__(self, fail=None):
        self.calls = []
        self.fail = fail
        self.CreateJobObjectW = self._call("CreateJobObjectW", 77)
        self.GetCurrentProcess = self._call("GetCurrentProcess", 5)
        self.SetInformationJobObject = self._call("SetInformationJobObject", 1)
        self.AssignProcessToJobObject = self._call("AssignProcessToJobObject", 1)

    def _call(self, name, result):
        def call(*args):
            self.calls.append((name, args))
            return 0 if self.fail == name else result

        return call


def _fake_ctypes(kernel):
    import types

    class Structure:
        def __init__(self):
            for name, kind in self._fields_:
                setattr(self, name, kind() if isinstance(kind, type) and issubclass(kind, Structure) else 0)

    return types.SimpleNamespace(
        Structure=Structure,
        c_int64=int, c_uint32=int, c_uint64=int, c_size_t=int,
        c_void_p=lambda value=None: ("handle", value),
        WinDLL=lambda name, use_last_error=False: kernel,
        byref=lambda obj: obj,
        sizeof=lambda obj: 144,
    )


def test_windows_caps_the_child_with_a_job_object(monkeypatch):
    kernel = _FakeKernel32()
    monkeypatch.setattr(sys, "platform", "win32")
    monkeypatch.setitem(sys.modules, "ctypes", _fake_ctypes(kernel))
    monkeypatch.setattr(parse_guard, "_job_handle", None)
    parse_guard._limit_memory(123456)
    calls = dict(kernel.calls)
    assert set(calls) == {"CreateJobObjectW", "GetCurrentProcess", "SetInformationJobObject", "AssignProcessToJobObject"}
    assert kernel.calls[-1][0] == "AssignProcessToJobObject"
    set_call = calls["SetInformationJobObject"]
    assert set_call[1] == parse_guard.JOB_OBJECT_EXTENDED_LIMIT_INFORMATION
    info = set_call[2]
    assert info.BasicLimitInformation.LimitFlags == parse_guard.JOB_OBJECT_LIMIT_PROCESS_MEMORY == 0x100
    assert info.ProcessMemoryLimit == 123456
    assert calls["AssignProcessToJobObject"][0] == ("handle", 77)
    assert parse_guard._job_handle == 77


@pytest.mark.parametrize("failing", ["CreateJobObjectW", "SetInformationJobObject", "AssignProcessToJobObject"])
def test_a_failed_windows_cap_is_logged_and_the_reader_still_runs(monkeypatch, failing):
    kernel = _FakeKernel32(fail=failing)
    monkeypatch.setattr(sys, "platform", "win32")
    monkeypatch.setitem(sys.modules, "ctypes", _fake_ctypes(kernel))
    monkeypatch.setattr(parse_guard, "_job_handle", None)
    parse_guard._limit_memory(1)  # must not raise
    assert parse_guard._job_handle is None


def test_posix_still_caps_with_rlimit_as_not_a_job_object(monkeypatch):
    import types

    seen = []
    fake = types.SimpleNamespace(RLIMIT_AS=9, setrlimit=lambda which, pair: seen.append((which, pair)))
    monkeypatch.setattr(sys, "platform", "linux")
    monkeypatch.setitem(sys.modules, "resource", fake)
    parse_guard._limit_memory(4096)
    assert seen == [(9, (4096, 4096))]
