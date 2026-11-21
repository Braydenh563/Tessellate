"""Untrusted files are parsed in a child process with a time and memory limit
(L-world-class-321, SECURITY.md T19): a hang is killed at the time limit, a
memory blow-up is refused, a crash is an error and not the server's death, and
a normal answer comes back as plain data. The parsers here are fakes
(`tests/_parse_fakes.py`) run in the real child."""

from __future__ import annotations

import sys

import pytest

from tessellate.core import parse_child, parse_sandbox

posix_only = pytest.mark.skipif(sys.platform == "win32", reason="setrlimit is POSIX only")

FAKES = "tests._parse_fakes"


@pytest.fixture()
def box():
    sandbox = parse_sandbox.Sandbox(memory_mb=512)
    yield sandbox
    sandbox.close()


def test_the_normal_path_returns_plain_data(box):
    value = box.call(f"{FAKES}:echo", "text", b"\x89PNG", 3, None, [b"a", b"b"], timeout=30)
    assert value == ["text", b"\x89PNG", 3, None, [b"a", b"b"]]


def test_one_child_answers_many_calls(box):
    first = box.call(f"{FAKES}:pid", timeout=30)
    assert box.call(f"{FAKES}:pid", timeout=30) == first


def test_a_hang_is_killed_at_the_time_limit(box):
    before = box.call(f"{FAKES}:pid", timeout=30)
    with pytest.raises(parse_sandbox.ParseRefused) as refused:
        box.call(f"{FAKES}:hang", timeout=0.5)
    assert refused.value.kind == "timeout"
    assert "too long" in str(refused.value)
    assert box.call(f"{FAKES}:pid", timeout=30) != before, "the hung child is gone, a fresh one answers"


@posix_only
def test_a_cpu_spin_is_stopped_by_the_cpu_limit(box):
    with pytest.raises(parse_sandbox.ParseRefused) as refused:
        box.call(f"{FAKES}:spin", timeout=60, cpu_seconds=1)
    assert refused.value.kind == "timeout"


@posix_only
def test_a_memory_blow_up_is_refused(box):
    with pytest.raises(parse_sandbox.ParseRefused) as refused:
        box.call(f"{FAKES}:blow_up", timeout=30)
    assert refused.value.kind == "memory"
    assert "memory" in str(refused.value)
    assert box.call(f"{FAKES}:echo", 1, timeout=30) == [1]


def test_a_crash_returns_the_error_and_the_next_call_works(box):
    with pytest.raises(parse_sandbox.ParseRefused) as refused:
        box.call(f"{FAKES}:crash", timeout=30)
    assert refused.value.kind == "crashed"
    assert box.call(f"{FAKES}:echo", "again", timeout=30) == ["again"]


def test_a_parser_exception_is_a_plain_failure(box):
    with pytest.raises(parse_sandbox.ParseRefused) as refused:
        box.call(f"{FAKES}:fail", timeout=30)
    assert refused.value.kind == "failed"
    assert "not a PDF" in refused.value.detail, "the library's words stay for the log"
    assert "not a PDF" not in str(refused.value), "and out of the sentence a person reads"


def test_a_parser_printing_to_stdout_cannot_corrupt_the_answer(box):
    assert box.call(f"{FAKES}:chatter", timeout=30) == "still read"


@pytest.mark.parametrize("kind", sorted(parse_sandbox.MESSAGES))
def test_every_message_is_one_plain_sentence(kind):
    text = parse_sandbox.MESSAGES[kind]
    assert text[0].isupper() and text.endswith(".")
    assert "!" not in text and chr(0x2014) not in text and "Oops" not in text


def test_the_wire_never_unpickles():
    """The child is the untrusted side: what it sends back is decoded as JSON
    plus raw bytes, so a compromised child cannot hand the server code to run."""
    for module in (parse_child, parse_sandbox):
        with open(module.__file__, encoding="utf-8") as handle:
            text = handle.read()
        assert "import pickle" not in text and "marshal" not in text and ".recv(" not in text
    blob = parse_child.encode({"ok": True, "value": [b"\x00\x01", "x", {"k": b"y"}]})
    assert parse_child.decode_frame(blob) == {"ok": True, "value": [b"\x00\x01", "x", {"k": b"y"}]}


def test_a_frame_over_the_cap_is_refused():
    huge = (parse_child.MAX_FRAME + 1).to_bytes(4, "big")
    with pytest.raises(ValueError):
        parse_child.decode_frame(huge + b"{}")


def test_an_import_stopped_at_the_limit_says_so(client, monkeypatch):
    from tessellate.api import routes_settings_transfer

    monkeypatch.setattr(routes_settings_transfer.importer, "markitdown_available", lambda: True)

    def stopped(_path):
        raise parse_sandbox.ParseRefused("timeout", "markdown passed 120 s")

    monkeypatch.setattr(routes_settings_transfer.importer, "convert_to_markdown", stopped)
    response = client.post("/import/document", files={"file": ("big.docx", b"junk", "application/x")})
    assert response.status_code == 422
    assert response.json()["detail"] == "That file took too long to read, so it was stopped."


def test_the_word_and_pdf_parsers_are_not_imported_by_the_server():
    """Replace, not layer: no in-process path is left for PDFium or markitdown."""
    import ast
    from pathlib import Path

    src = Path(parse_sandbox.__file__).resolve().parents[1]
    for path in src.rglob("*.py"):
        if path.name == "parse_jobs.py":
            continue
        for node in ast.walk(ast.parse(path.read_text(encoding="utf-8"))):
            names = []
            if isinstance(node, ast.Import):
                names = [alias.name for alias in node.names]
            elif isinstance(node, ast.ImportFrom):
                names = [node.module or ""]
            assert not any(n.split(".")[0] in {"pypdfium2", "markitdown"} for n in names), path
