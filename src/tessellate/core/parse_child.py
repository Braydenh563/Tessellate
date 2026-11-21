"""The child side of `core/parse_sandbox.py`: a loop that reads one request,
runs one parser and writes one answer (L-world-class-321, SECURITY.md T19).

**Standard library only, on purpose.** This module is what a cold child
imports before it can answer, and `tessellate.core.deps` alone costs about
1.1 s to import (measured); this file costs the interpreter's own ~25 ms. The
parsers themselves (`core/parse_jobs.py`) import pypdfium2 or markitdown on
the first call that needs them.

**The wire is JSON plus raw bytes, never pickle.** The child is the side that
reads untrusted files, so it is the side that may be compromised; what it
sends back is decoded by `decode` as data and nothing else, so a parser bug
cannot become code run by the server. A frame is a 4-byte length and a JSON
header, then each byte string the header points at (``{"$b": index}``) as a
4-byte length and its bytes. Every length is capped (`MAX_FRAME`), so a child
cannot make the server allocate whatever it likes.

**Limits are set by the child on itself** (POSIX ``setrlimit``): address
space once, at the handshake, and processor seconds before each job, as
"what this process has used so far plus this job's allowance", since one
child serves many jobs and ``RLIMIT_CPU`` counts the whole life of a
process. Windows has no ``setrlimit``: there the parent's wall-clock timeout
is the only limit (documented in SECURITY.md T19).
"""

from __future__ import annotations

import importlib
import json
import os
import sys

#: The largest single length a frame may declare: a header or one byte
#: string. A rendered page is a few MB; 256 MB is far past any honest answer.
MAX_FRAME = 256 * 1024 * 1024
_MAX_BLOBS = 4096


def _pack(value, blobs: list[bytes]):  # noqa: ANN001, ANN202  # JSON-shaped data
    if isinstance(value, (bytes, bytearray, memoryview)):
        blobs.append(bytes(value))
        return {"$b": len(blobs) - 1}
    if isinstance(value, (list, tuple)):
        return [_pack(item, blobs) for item in value]
    if isinstance(value, dict):
        return {str(key): _pack(item, blobs) for key, item in value.items()}
    return value


def _unpack(value, blobs: list[bytes]):  # noqa: ANN001, ANN202
    if isinstance(value, list):
        return [_unpack(item, blobs) for item in value]
    if isinstance(value, dict):
        if len(value) == 1 and isinstance(value.get("$b"), int):
            index = value["$b"]
            if not 0 <= index < len(blobs):
                raise ValueError("a frame pointed at a byte string it did not carry")
            return blobs[index]
        return {key: _unpack(item, blobs) for key, item in value.items()}
    return value


def encode(message: dict) -> bytes:
    blobs: list[bytes] = []
    header = json.dumps({"v": _pack(message, blobs), "n": len(blobs)}).encode("utf-8")
    parts = [len(header).to_bytes(4, "big"), header]
    for blob in blobs:
        parts += [len(blob).to_bytes(4, "big"), blob]
    return b"".join(parts)


def _length(read) -> int:  # noqa: ANN001
    size = int.from_bytes(read(4), "big")
    if size > MAX_FRAME:
        raise ValueError("a frame declared more than the cap")
    return size


def decode(read) -> dict:  # noqa: ANN001  # read(n) returns exactly n bytes or raises EOFError
    header = json.loads(read(_length(read)).decode("utf-8"))
    count = header.get("n") if isinstance(header, dict) else None
    if not isinstance(count, int) or not 0 <= count <= _MAX_BLOBS:
        raise ValueError("a frame header was not one")
    blobs = [read(_length(read)) for _ in range(count)]
    message = _unpack(header.get("v"), blobs)
    if not isinstance(message, dict):
        raise ValueError("a frame carried no message")
    return message


def reader(stream):  # noqa: ANN001, ANN201
    """`read(n)` over a binary stream: exactly n bytes, or EOFError."""

    def read(size: int) -> bytes:
        chunks, left = [], size
        while left:
            chunk = stream.read(left)
            if not chunk:
                raise EOFError
            chunks.append(chunk)
            left -= len(chunk)
        return b"".join(chunks)

    return read


def decode_frame(frame: bytes) -> dict:
    """One whole frame from bytes in hand (tests)."""
    import io

    return decode(reader(io.BytesIO(frame)))


def _limit_memory(megabytes: int) -> None:
    try:
        import resource
    except ImportError:
        return  # Windows: the wall-clock timeout is the only limit
    limit = int(megabytes) * 1024 * 1024
    _soft, hard = resource.getrlimit(resource.RLIMIT_AS)
    if hard != resource.RLIM_INFINITY:
        limit = min(limit, hard)
    resource.setrlimit(resource.RLIMIT_AS, (limit, hard))


def _limit_cpu(seconds: float | None) -> None:
    try:
        import resource
    except ImportError:
        return
    if not seconds:
        return
    used = resource.getrusage(resource.RUSAGE_SELF)
    soft = int(used.ru_utime + used.ru_stime + float(seconds)) + 1
    _old, hard = resource.getrlimit(resource.RLIMIT_CPU)
    if hard != resource.RLIM_INFINITY:
        soft = min(soft, hard)
    resource.setrlimit(resource.RLIMIT_CPU, (soft, hard))


def handle(request: dict) -> dict:
    """One request to one answer. Never raises for a parser's sake."""
    if "path" in request:
        sys.path[:] = [str(entry) for entry in request["path"]]
        _limit_memory(request.get("memory_mb") or 2048)
        return {"ok": True, "value": "ready"}
    module_name, _, name = str(request.get("job", "")).partition(":")
    try:
        function = getattr(importlib.import_module(module_name), name)
        _limit_cpu(request.get("cpu"))
        return {"ok": True, "value": function(*request.get("args", []))}
    except MemoryError:
        return {"ok": False, "kind": "memory", "detail": "MemoryError"}
    except Exception as exc:  # noqa: BLE001  # a parser's failure is an answer, not the child's death
        return {"ok": False, "kind": "failed", "detail": f"{type(exc).__name__}: {exc}"[:500]}


def _claim_pipes():  # noqa: ANN202
    """The request and answer pipes, kept to this loop: fd 1 is pointed at
    stderr and fd 0 at nothing, so a parser that prints (markitdown's
    converters can) or reads cannot corrupt or read the wire."""
    inbound = os.fdopen(os.dup(0), "rb", buffering=0)
    outbound = os.fdopen(os.dup(1), "wb", buffering=0)
    os.dup2(2, 1)
    devnull = os.open(os.devnull, os.O_RDONLY)
    os.dup2(devnull, 0)
    os.close(devnull)
    sys.stdout = sys.stderr
    return inbound, outbound


def main() -> None:
    sys.dont_write_bytecode = True
    inbound, outbound = _claim_pipes()
    read = reader(inbound)
    while True:
        try:
            request = decode(read)
        except (EOFError, OSError, ValueError):
            return  # the server went away or spoke nonsense: nothing left to serve
        try:
            frame = encode(handle(request))
        except (TypeError, ValueError) as exc:  # an answer the wire cannot carry
            frame = encode({"ok": False, "kind": "failed", "detail": f"unsendable answer: {exc}"[:500]})
        outbound.write(frame)


if __name__ == "__main__":
    main()
