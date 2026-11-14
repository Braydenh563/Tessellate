"""The bytes of a private space's files, sealed at rest (L-world-class-52).

L697 sealed a private space's recordings, library uploads and note files in
the database; their bytes (`data/recordings`, `data/media`, `data/uploads`)
were still plain. This seals them with the same key and the same cipher as
every sealed column (`crypto.encrypt`: the vault key, AES-GCM from
`cryptography`), framed so a recording can grow ten seconds at a time and an
audio Range read decrypts only the frames it touches.

A sealed file is `MAGIC` then frames of `length (4 bytes) | nonce | ciphertext
and tag`, each at most `FRAME` plain bytes. A frame's associated data is the
magic and its index, so frames cannot be reordered or swapped between
positions; a file cut back to a frame boundary still opens (what a chunk
append rolled back to on a full disk is exactly that).

A file without the magic is plain and is read as it is, so files written
before this, or outside a private space, keep working; `seal` and `unseal`
rewrite one in place (a temp file in the same folder, then `os.replace`).
A reader that needs a path (a PDF renderer, Whisper) gets one through
`readable`, a private temp copy removed when it is done.
"""

from __future__ import annotations

import os
import shutil
import struct
import tempfile
from collections.abc import Iterator
from contextlib import contextmanager
from pathlib import Path

from cryptography.exceptions import InvalidTag
from cryptography.hazmat.primitives.ciphers.aead import AESGCM

from tessellate.core import crypto

MAGIC = b"TSLSEAL\x01"
#: Plain bytes per frame: a Range read decrypts at most this much past its ends.
FRAME = 1 << 20
_LEN = struct.Struct(">I")
_NONCE = crypto.NONCE_BYTES
_TAG = 16


class SealedLocked(RuntimeError):
    """The file is sealed and this caller has no key: unlock first."""


class SealedDamaged(RuntimeError):
    """The file is sealed but does not open with this key."""


LOCKED_DETAIL = "This private space is locked. Unlock it first."


def _key() -> bytes:
    from tessellate.core import vault

    key = vault.key()
    if key is None:
        raise SealedLocked(LOCKED_DETAIL)
    return key


def is_sealed(path: Path) -> bool:
    try:
        with open(path, "rb") as fh:
            return fh.read(len(MAGIC)) == MAGIC
    except OSError:
        return False


def plain_file(path: Path) -> bool:
    """A file that is there and not sealed: what a keyless background reader may open."""
    return Path(path).is_file() and not is_sealed(path)


def _aad(index: int) -> bytes:
    return MAGIC + index.to_bytes(8, "big")


def _frames(fh) -> Iterator[tuple[int, int, int]]:  # noqa: ANN001
    """(index, offset of the nonce, ciphertext length) of each whole frame."""
    fh.seek(len(MAGIC))
    index = 0
    while True:
        head = fh.read(_LEN.size)
        if len(head) < _LEN.size:
            return
        (length,) = _LEN.unpack(head)
        offset = fh.tell()
        fh.seek(_NONCE + length, os.SEEK_CUR)
        if fh.tell() > os.fstat(fh.fileno()).st_size:
            return
        yield index, offset, length
        index += 1


def _frame_count(path: Path) -> int:
    with open(path, "rb") as fh:
        return sum(1 for _ in _frames(fh))


def _encrypt(key: bytes, data: bytes, start: int) -> bytes:
    aead = AESGCM(key)
    out = bytearray()
    for n, at in enumerate(range(0, len(data), FRAME)):
        nonce = os.urandom(_NONCE)
        body = aead.encrypt(nonce, data[at : at + FRAME], _aad(start + n))
        out += _LEN.pack(len(body)) + nonce + body
    return bytes(out)


def _decrypt_frame(aead: AESGCM, fh, index: int, offset: int, length: int) -> bytes:  # noqa: ANN001
    fh.seek(offset)
    nonce = fh.read(_NONCE)
    try:
        return aead.decrypt(nonce, fh.read(length), _aad(index))
    except InvalidTag as exc:
        raise SealedDamaged("This file does not open with this key.") from exc


def seal_bytes(data: bytes) -> bytes:
    """`data` as a whole sealed file's contents."""
    return MAGIC + _encrypt(_key(), data, 0)


def read(path: Path) -> bytes:
    """The plain bytes, sealed or not. SealedLocked without the key."""
    path = Path(path)
    if not is_sealed(path):
        return path.read_bytes()
    aead = AESGCM(_key())
    with open(path, "rb") as fh:
        return b"".join(_decrypt_frame(aead, fh, *frame) for frame in list(_frames(fh)))


def plain_size(path: Path) -> int:
    path = Path(path)
    if not is_sealed(path):
        return path.stat().st_size
    with open(path, "rb") as fh:
        return sum(length - _TAG for _i, _o, length in _frames(fh))


def read_range(path: Path, start: int, end: int) -> bytes:
    """Plain bytes `start` to `end` inclusive, decrypting only the frames they touch."""
    path = Path(path)
    if not is_sealed(path):
        with open(path, "rb") as fh:
            fh.seek(start)
            return fh.read(end - start + 1)
    aead = AESGCM(_key())
    out = bytearray()
    at = 0
    with open(path, "rb") as fh:
        for index, offset, length in list(_frames(fh)):
            size = length - _TAG
            if at + size > start and at <= end:
                plain = _decrypt_frame(aead, fh, index, offset, length)
                out += plain[max(0, start - at) : end - at + 1]
            at += size
            if at > end:
                break
    return bytes(out)


def append(path: Path, data: bytes, *, sealed: bool) -> None:
    """Add `data` to the end, sealed when the file is (or, new, when `sealed`).
    A write cut short (a full disk) is cut back to where it was, and the error
    goes on, so a retry starts where the saved bytes end."""
    path = path if isinstance(path, Path) else Path(path)
    before = path.stat().st_size if path.exists() else 0
    seal = is_sealed(path) if before else sealed
    if seal:
        blob = _encrypt(_key(), data, _frame_count(path) if before else 0)
        if not before:
            blob = MAGIC + blob
    else:
        blob = data
    try:
        with path.open("ab") as out:
            out.write(blob)
    except OSError:
        with path.open("ab") as out:
            out.truncate(before)
        raise


def _rewrite(path: Path, contents: bytes) -> None:
    fd, tmp = tempfile.mkstemp(dir=path.parent, prefix=".seal-", suffix=".tmp")
    try:
        with os.fdopen(fd, "wb") as out:
            out.write(contents)
        os.replace(tmp, path)
    except BaseException:
        Path(tmp).unlink(missing_ok=True)
        raise


def seal(path: Path) -> bool:
    """Seal a plain file in place. True when it changed; a missing file is nothing."""
    path = Path(path)
    if not path.is_file() or is_sealed(path):
        return False
    _rewrite(path, seal_bytes(path.read_bytes()))
    return True


def unseal(path: Path) -> bool:
    """Write a sealed file back plain (its item left the private space)."""
    path = Path(path)
    if not path.is_file() or not is_sealed(path):
        return False
    _rewrite(path, read(path))
    return True


@contextmanager
def readable(path: Path, *, write: bool = False) -> Iterator[Path]:
    """A path a path-only reader can open: the file itself when plain, else a
    temp copy in a private folder (0700), removed when the block ends. With
    `write`, what the block left in the copy is sealed back over the file."""
    path = Path(path)
    if not is_sealed(path):
        yield path
        return
    plain = read(path)
    folder = tempfile.mkdtemp(prefix="tessellate-open-")
    try:
        copy = Path(folder) / path.name
        copy.write_bytes(plain)
        yield copy
        if write and copy.read_bytes() != plain:
            _rewrite(path, seal_bytes(copy.read_bytes()))
    finally:
        shutil.rmtree(folder, ignore_errors=True)


def wanted(session, workspace_id: str | None) -> bool:  # noqa: ANN001
    """Whether a file written now for a row of `workspace_id` is sealed."""
    from tessellate.core import database

    space = workspace_id or session.info.get("workspace_id") or "default"
    return space in database._private_space_ids(session)
