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
