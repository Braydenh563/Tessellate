"""The bytes of a private space's files, sealed at rest (L-world-class-52).

L697 sealed a private space's recordings, library uploads and note files in
the database; their bytes (`data/recordings`, `data/media`, `data/uploads`)
were still plain. This seals them with the same key and the same cipher as
every sealed column (`crypto.encrypt`: the vault key, AES-GCM from
`cryptography`), framed so a recording can grow ten seconds at a time and an
audio Range read decrypts only the frames it touches.

A sealed file is `MAGIC` (a prefix and a format version) then frames of
`length (4 bytes) | nonce | ciphertext and tag`, each at most `FRAME` plain
bytes. A frame's associated data is the magic, its index and whether it is
the last, so frames cannot be reordered, dropped or swapped, and a file cut
back (at a frame boundary or inside one) raises `SealedDamaged` instead of
reading as a shorter file. An append writes its frames (the new last one
flagged), then re-seals the old last frame as not last; a crash between the
two leaves a "last" frame in the middle, which a reader accepts, since only
the key holder can write one.

A file without the magic is plain and is read as it is, so files written
before this, or outside a private space, keep working; a plain write that
starts with the prefix is refused (`LooksSealed`), so a plain file is never
mistaken for a sealed one. `seal` and `unseal` rewrite one in place (a temp
file in the same folder, fsynced, then `os.replace`). A reader that needs a
path (a PDF renderer, Whisper) gets one through `readable`, a private temp
copy under `data_dir/tmp`, removed when it is done and swept at boot.
"""

from __future__ import annotations

import os
import shutil
import struct
import tempfile
import threading
from collections.abc import Iterator
from contextlib import contextmanager
from pathlib import Path

from cryptography.exceptions import InvalidTag
from cryptography.hazmat.primitives.ciphers.aead import AESGCM

from tessellate.core import crypto

PREFIX = b"TSLSEAL"
VERSION = 2
MAGIC = PREFIX + bytes([VERSION])
#: Plain bytes per frame: a Range read decrypts at most this much past its ends.
FRAME = 1 << 20
_LEN = struct.Struct(">I")
_NONCE = crypto.NONCE_BYTES
_TAG = 16
_MAX = FRAME + _TAG
OPEN_PREFIX = "tessellate-open-"
TMP_GLOB = ".seal-*.tmp"


class SealedError(RuntimeError):
    """A sealed file that cannot be read for this caller."""


class SealedLocked(SealedError):
    """The file is sealed and this caller has no key: unlock first."""


class SealedDamaged(SealedError):
    """The file is sealed but does not open with this key, or was cut or changed."""


class LooksSealed(ValueError):
    """A plain file may not start the way a sealed one does."""


LOCKED_DETAIL = "This private space is locked. Unlock it first."
DAMAGED_DETAIL = "This file is damaged or does not open with this key."
LOOKS_SEALED_DETAIL = "This file starts the way a sealed file does, so it can't be stored."

_locks: dict[str, threading.RLock] = {}
_locks_guard = threading.Lock()
#: path -> (inode, size, mtime_ns, frame count, end of whole frames, last offset, last length)
_layouts: dict[str, tuple[int, int, int, int, int, int, int]] = {}


def _lock_for(path: Path) -> threading.RLock:
    """One lock per file, so seal, unseal, append and a write-back never interleave."""
    name = os.path.abspath(path)
    with _locks_guard:
        return _locks.setdefault(name, threading.RLock())


def _key() -> bytes:
    from tessellate.core import vault

    key = vault.key()
    if key is None:
        raise SealedLocked(LOCKED_DETAIL)
    return key


def is_sealed(path: Path) -> bool:
    """The magic with this version and a first frame length that can be one."""
    try:
        with open(path, "rb") as fh:
            head = fh.read(len(MAGIC) + _LEN.size)
    except OSError:
        return False
    if len(head) < len(MAGIC) + _LEN.size or head[: len(MAGIC)] != MAGIC:
        return False
    (length,) = _LEN.unpack(head[len(MAGIC) :])
    return _TAG <= length <= _MAX


def plain_file(path: Path) -> bool:
    """A file that is there and not sealed: what a keyless background reader may open."""
    return Path(path).is_file() and not is_sealed(path)


def _aad(index: int, final: bool) -> bytes:
    return MAGIC + index.to_bytes(8, "big") + (b"\x01" if final else b"\x00")


def _frames(fh) -> Iterator[tuple[int, int, int]]:  # noqa: ANN001
    """(index, offset of the nonce, ciphertext length) of each whole frame."""
    size = os.fstat(fh.fileno()).st_size
    at, index = len(MAGIC), 0
    while at + _LEN.size <= size:
        fh.seek(at)
        (length,) = _LEN.unpack(fh.read(_LEN.size))
        end = at + _LEN.size + _NONCE + length
        if not _TAG <= length <= _MAX or end > size:
            return
        yield index, at + _LEN.size, length
        at, index = end, index + 1


def _whole(fh) -> list[tuple[int, int, int]]:  # noqa: ANN001
    """Every whole frame, or SealedDamaged when there is none. Bytes after the
    last whole frame are a partial frame a crash mid-append left (the next
    append drops them) and are not read; a cut that leaves a whole frame last
    is still refused, since that frame is not flagged as the last."""
    frames = list(_frames(fh))
    if not frames:
        raise SealedDamaged(DAMAGED_DETAIL)
    return frames


def _layout(path: Path, fh) -> tuple[int, int, int, int]:  # noqa: ANN001
    """(frame count, end of the whole frames, last offset, last length),
    remembered per file so an append does not scan the headers again."""
    st = os.fstat(fh.fileno())
    known = _layouts.get(os.path.abspath(path))
    if known and known[:3] == (st.st_ino, st.st_size, st.st_mtime_ns):
        return known[3:]
    count, end, last = 0, len(MAGIC), (0, 0)
    for index, offset, length in _frames(fh):
        count, end, last = index + 1, offset + _NONCE + length, (offset, length)
    return count, end, *last


def _remember(path: Path, fh, layout: tuple[int, int, int, int]) -> None:  # noqa: ANN001
    st = os.fstat(fh.fileno())
    _layouts[os.path.abspath(path)] = (st.st_ino, st.st_size, st.st_mtime_ns, *layout)


def _encrypt(key: bytes, data: bytes, start: int) -> bytes:
    """Frames for `data` from index `start`, the last flagged as the last."""
    aead = AESGCM(key)
    out = bytearray()
    offsets = range(0, len(data), FRAME) or range(1)
    for n, at in enumerate(offsets):
        nonce = os.urandom(_NONCE)
        body = aead.encrypt(nonce, data[at : at + FRAME], _aad(start + n, n == len(offsets) - 1))
        out += _LEN.pack(len(body)) + nonce + body
    return bytes(out)


def _open_frame(aead: AESGCM, fh, index: int, offset: int, length: int, last: bool) -> bytes:  # noqa: ANN001
    """The last frame must say it is the last; a middle one may (a crash
    between an append and re-sealing the old last frame)."""
    fh.seek(offset)
    nonce, body = fh.read(_NONCE), fh.read(length)
    for final in (True,) if last else (False, True):
        try:
            return aead.decrypt(nonce, body, _aad(index, final))
        except InvalidTag:
            continue
    raise SealedDamaged(DAMAGED_DETAIL)


def seal_bytes(data: bytes) -> bytes:
    """`data` as a whole sealed file's contents."""
    return MAGIC + _encrypt(_key(), data, 0)


def iter_plain(path: Path, start: int = 0, end: int | None = None) -> Iterator[bytes]:
    """The plain bytes `start` to `end` inclusive of a sealed file, a frame at
    a time. The key and the last frame are checked before this returns, so a
    locked or cut file fails before a response starts, not part way."""
    aead = AESGCM(_key())
    fh = open(path, "rb")  # noqa: SIM115  # closed by the generator
    try:
        frames = _whole(fh)
        _open_frame(aead, fh, *frames[-1], last=True)
    except BaseException:
        fh.close()
        raise
    return _stream(aead, fh, frames, start, end)


def _stream(aead: AESGCM, fh, frames, start: int, end: int | None) -> Iterator[bytes]:  # noqa: ANN001
    at = 0
    with fh:
        for index, offset, length in frames:
            size = length - _TAG
            if end is not None and at > end:
                return
            if at + size > start:
                plain = _open_frame(aead, fh, index, offset, length, index == len(frames) - 1)
                yield plain[max(0, start - at) : None if end is None else end - at + 1]
            at += size


def read(path: Path) -> bytes:
    """The plain bytes, sealed or not. SealedLocked without the key."""
    path = Path(path)
    with _lock_for(path):
        if not is_sealed(path):
            return path.read_bytes()
        return b"".join(iter_plain(path))


def plain_size(path: Path) -> int:
    path = Path(path)
    if not is_sealed(path):
        return path.stat().st_size
    with open(path, "rb") as fh:
        return sum(length - _TAG for _i, _o, length in _whole(fh))


def read_range(path: Path, start: int, end: int) -> bytes:
    """Plain bytes `start` to `end` inclusive, decrypting only the frames they touch."""
    path = Path(path)
    if not is_sealed(path):
        with open(path, "rb") as fh:
            fh.seek(start)
            return fh.read(end - start + 1)
    with _lock_for(path):
        return b"".join(iter_plain(path, start, end))


def append(path: Path, data: bytes, *, sealed: bool) -> None:
    """Add `data` to the end, sealed when the file is (or, new, when `sealed`).
    A write cut short (a full disk) is cut back to where it was, and the error
    goes on, so a retry starts where the saved bytes end."""
    path = path if isinstance(path, Path) else Path(path)
    with _lock_for(path):
        before = _size(path)
        if before and is_sealed(path):
            _append_sealed(path, data)
        elif not before and sealed:
            _write_new_sealed(path, data)
        else:
            if not before and data.startswith(PREFIX):
                raise LooksSealed(LOOKS_SEALED_DETAIL)
            try:
                with path.open("ab") as out:
                    out.write(data)
            except OSError:
                with path.open("ab") as out:
                    out.truncate(before)
                raise


def _size(path: Path) -> int:
    """Bytes on disk now, 0 for no file, read from a handle (an upload's
    size is counted as it streams, `test_media_size_backfill`)."""
    try:
        with open(path, "rb") as fh:
            return fh.seek(0, os.SEEK_END)
    except FileNotFoundError:
        return 0


def _write_new_sealed(path: Path, data: bytes) -> None:
    blob = MAGIC + _encrypt(_key(), data, 0)
    with open(path, "wb", buffering=0) as fh:
        try:
            fh.write(blob)
            os.fsync(fh.fileno())
        except OSError:
            fh.truncate(0)
            raise
        last = _last_body(data)
        _remember(path, fh, (max(1, -(-len(data) // FRAME)), len(blob), len(blob) - _NONCE - last, last))


def _last_body(data: bytes) -> int:
    """The ciphertext length of the last frame `_encrypt` writes for `data`."""
    return ((len(data) - 1) % FRAME + 1 if data else 0) + _TAG


def _append_sealed(path: Path, data: bytes) -> None:
    """Drop a partial frame left at the end, write the new frames, then
    re-seal the old last frame as not the last one."""
    key = _key()
    with open(path, "r+b", buffering=0) as fh:
        count, end, last_offset, last_length = _layout(path, fh)
        if end < os.fstat(fh.fileno()).st_size:
            fh.truncate(end)
            os.fsync(fh.fileno())
        if not data:
            _remember(path, fh, (count, end, last_offset, last_length))
            return
        blob = _encrypt(key, data, count)
        try:
            fh.seek(end)
            fh.write(blob)
            os.fsync(fh.fileno())
        except OSError:
            fh.truncate(end)
            raise
        if count:
            _reseal_not_final(key, fh, count - 1, last_offset, last_length)
        tail = _last_body(data)
        added = -(-len(data) // FRAME)
        _remember(path, fh, (count + added, end + len(blob), end + len(blob) - _NONCE - tail, tail))


def _reseal_not_final(key: bytes, fh, index: int, offset: int, length: int) -> None:  # noqa: ANN001
    """The old last frame, written again in place (same length) as a middle one."""
    aead = AESGCM(key)
    fh.seek(offset)
    nonce, body = fh.read(_NONCE), fh.read(length)
    try:
        plain = aead.decrypt(nonce, body, _aad(index, True))
    except InvalidTag:
        return
    fresh = os.urandom(_NONCE)
    fh.seek(offset)
    fh.write(fresh + aead.encrypt(fresh, plain, _aad(index, False)))
    os.fsync(fh.fileno())


def _fsync_folder(folder: Path) -> None:
    try:
        fd = os.open(folder, os.O_RDONLY)
    except OSError:
        return  # Windows cannot open a folder this way; its replace is durable enough.
    try:
        os.fsync(fd)
    except OSError:
        pass
    finally:
        os.close(fd)


def _rewrite(path: Path, contents: bytes) -> None:
    fd, tmp = tempfile.mkstemp(dir=path.parent, prefix=".seal-", suffix=".tmp")
    try:
        with os.fdopen(fd, "wb") as out:
            out.write(contents)
            out.flush()
            os.fsync(out.fileno())
        os.replace(tmp, path)
        _fsync_folder(path.parent)
    except BaseException:
        Path(tmp).unlink(missing_ok=True)
        raise
    finally:
        _layouts.pop(os.path.abspath(path), None)


def seal(path: Path) -> bool:
    """Seal a plain file in place. True when it changed; a missing file is nothing."""
    path = Path(path)
    with _lock_for(path):
        if not path.is_file() or is_sealed(path):
            return False
        _rewrite(path, seal_bytes(path.read_bytes()))
        return True


def unseal(path: Path) -> bool:
    """Write a sealed file back plain (its item left the private space)."""
    path = Path(path)
    with _lock_for(path):
        if not path.is_file() or not is_sealed(path):
            return False
        _rewrite(path, read(path))
        return True


def _tmp_root() -> Path:
    from tessellate.core import deps

    root = deps.get_config().data_dir / "tmp"
    root.mkdir(mode=0o700, parents=True, exist_ok=True)
    return root


@contextmanager
def readable(path: Path, *, write: bool = False) -> Iterator[Path]:
    """A path a path-only reader can open: the file itself when plain, else a
    temp copy in a private folder (0700) under `data_dir/tmp`, removed when
    the block ends. With `write`, what the block left in the copy is sealed
    back over the file."""
    path = Path(path)
    if not is_sealed(path):
        yield path
        return
    plain = read(path)
    folder = tempfile.mkdtemp(prefix=OPEN_PREFIX, dir=_tmp_root())
    try:
        copy = Path(folder) / path.name
        copy.write_bytes(plain)
        yield copy
        if write and copy.read_bytes() != plain:
            with _lock_for(path):
                _rewrite(path, seal_bytes(copy.read_bytes()))
    finally:
        shutil.rmtree(folder, ignore_errors=True)


def sweep_leftovers(data_dir: Path, folders: tuple[Path, ...] = ()) -> int:
    """At boot: plain temp copies and half-written rewrites a crash left behind."""
    data_dir = Path(data_dir)
    gone = 0
    for folder in (data_dir / "tmp").glob(OPEN_PREFIX + "*"):
        shutil.rmtree(folder, ignore_errors=True)
        gone += 1
    roots = {data_dir / "uploads", data_dir / "media", data_dir / "recordings", *map(Path, folders)}
    for root in roots:
        for stray in root.rglob(TMP_GLOB) if root.is_dir() else ():
            stray.unlink(missing_ok=True)
            gone += 1
    return gone


def wanted(session, workspace_id: str | None) -> bool:  # noqa: ANN001
    """Whether a file written now for a row of `workspace_id` is sealed."""
    from tessellate.core import database

    space = workspace_id or session.info.get("workspace_id") or "default"
    return space in database._private_space_ids(session)
