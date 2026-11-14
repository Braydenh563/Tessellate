"""L-world-class-52 review: the sealed file format holds against damage.

A sealed file's last frame is bound as the last (a final flag in each frame's
associated data), so a file cut back, a frame dropped, swapped or flipped,
or a partial frame left at the end raises `SealedDamaged` rather than reading
as a shorter file. Appends drop a partial tail first and re-seal the old last
frame; temp copies live under the data folder and are swept at boot.
"""

from __future__ import annotations

import os
from pathlib import Path

import pytest

from tessellate.core import deps, sealed_files

KEY = bytes(range(32))
OTHER = bytes(range(1, 33))
FRAME = sealed_files.FRAME


@pytest.fixture()
def keyed(app_state, monkeypatch):
    monkeypatch.setattr(sealed_files, "_key", lambda: KEY)
    return deps.get_config().data_dir


def _three_frames(path):
    data = os.urandom(FRAME * 2 + 1000)
    sealed_files.append(path, data[:FRAME], sealed=True)
    sealed_files.append(path, data[FRAME : 2 * FRAME], sealed=True)
    sealed_files.append(path, data[2 * FRAME :], sealed=True)
    return data


def _offsets(path):
    with open(path, "rb") as fh:
        return [(offset, length) for _i, offset, length in sealed_files._frames(fh)]


def _damaged(path):
    with pytest.raises(sealed_files.SealedDamaged):
        sealed_files.read(path)


def test_a_whole_file_reads_and_each_kind_of_damage_is_refused(keyed, tmp_path):
    path = tmp_path / "a.bin"
    data = _three_frames(path)
    assert sealed_files.read(path) == data
    good = path.read_bytes()
    frames = _offsets(path)
    head = len(sealed_files.MAGIC)
    starts = [offset - 4 for offset, _length in frames]
    # Cut back to a frame boundary: the old last frame is not flagged final.
    path.write_bytes(good[: starts[2]])
    _damaged(path)
    # A partial trailing frame.
    path.write_bytes(good[:-10])
    _damaged(path)
    # A middle frame dropped.
    path.write_bytes(good[: starts[1]] + good[starts[2] :])
    _damaged(path)
    # Two frames swapped.
    first, second = good[head : starts[1]], good[starts[1] : starts[2]]
    path.write_bytes(good[:head] + second + first + good[starts[2] :])
    _damaged(path)
    # One byte flipped in a ciphertext.
    flipped = bytearray(good)
    flipped[frames[1][0] + 40] ^= 1
    path.write_bytes(bytes(flipped))
    _damaged(path)
    with pytest.raises(sealed_files.SealedDamaged):
        sealed_files.read_range(path, FRAME + 1, FRAME + 2)


def test_a_wrong_key_is_damage_not_a_lock(keyed, tmp_path, monkeypatch):
    path = tmp_path / "a.bin"
    sealed_files.append(path, b"secret", sealed=True)
    monkeypatch.setattr(sealed_files, "_key", lambda: OTHER)
    _damaged(path)


def test_an_empty_sealed_file_is_still_bound_and_appends_grow_it(keyed, tmp_path):
    path = tmp_path / "e.bin"
    path.write_bytes(sealed_files.seal_bytes(b""))
    assert sealed_files.is_sealed(path) and sealed_files.read(path) == b""
    sealed_files.append(path, b"more", sealed=True)
    assert sealed_files.read(path) == b"more"


def test_an_append_after_a_partial_frame_drops_the_partial_first(keyed, tmp_path):
    path = tmp_path / "a.bin"
    sealed_files.append(path, b"one ", sealed=True)
    sealed_files.append(path, b"two ", sealed=True)
    with open(path, "ab") as fh:
        fh.write(b"\x00\x00\x01\x00half a frame")
    sealed_files.append(path, b"three", sealed=True)
    assert sealed_files.read(path) == b"one two three"
    assert sealed_files.plain_size(path) == len(b"one two three")


def test_a_crash_between_appending_and_resealing_the_old_last_still_reads(keyed, tmp_path, monkeypatch):
    path = tmp_path / "a.bin"
    sealed_files.append(path, b"one ", sealed=True)
    monkeypatch.setattr(sealed_files, "_reseal_not_final", lambda *a, **k: None)
    sealed_files.append(path, b"two", sealed=True)
    monkeypatch.undo()
    monkeypatch.setattr(sealed_files, "_key", lambda: KEY)
    assert sealed_files.read(path) == b"one two"
    sealed_files.append(path, b"!", sealed=True)
    assert sealed_files.read(path) == b"one two!"


def test_append_does_not_rescan_the_file(keyed, tmp_path, monkeypatch):
    path = tmp_path / "a.bin"
    sealed_files.append(path, b"a", sealed=True)
    sealed_files.append(path, b"b", sealed=True)
    scans = []
    real = sealed_files._frames
    monkeypatch.setattr(sealed_files, "_frames", lambda fh: scans.append(1) or real(fh))
    for _ in range(5):
        sealed_files.append(path, b"c", sealed=True)
    assert scans == []
    monkeypatch.undo()
    monkeypatch.setattr(sealed_files, "_key", lambda: KEY)
    assert sealed_files.read(path) == b"abccccc"


def test_is_sealed_wants_the_version_and_a_sane_first_frame(keyed, tmp_path):
    path = tmp_path / "x.bin"
    path.write_bytes(sealed_files.MAGIC)
    assert not sealed_files.is_sealed(path)
    path.write_bytes(sealed_files.MAGIC + b"\xff\xff\xff\xff" + b"\x00" * 40)
    assert not sealed_files.is_sealed(path)
    path.write_bytes(b"TSLSEAL\x09" + sealed_files.seal_bytes(b"hi")[8:])
    assert not sealed_files.is_sealed(path)
    path.write_bytes(sealed_files.seal_bytes(b"hi"))
    assert sealed_files.is_sealed(path)


def test_a_plain_write_that_starts_with_the_magic_is_refused(keyed, tmp_path):
    path = tmp_path / "p.bin"
    with pytest.raises(sealed_files.LooksSealed):
        sealed_files.append(path, sealed_files.MAGIC + b"\x00\x00\x00\x20" + b"x" * 64, sealed=False)
    assert not path.exists()


def test_seal_unseal_and_append_share_a_lock(keyed, tmp_path):
    path = tmp_path / "a.bin"
    assert sealed_files._lock_for(path) is sealed_files._lock_for(tmp_path / "." / "a.bin")


def test_rewrite_fsyncs_the_temp_file_and_the_folder(keyed, tmp_path, monkeypatch):
    path = tmp_path / "a.bin"
    path.write_bytes(b"plain")
    synced = []
    real = os.fsync
    monkeypatch.setattr(sealed_files.os, "fsync", lambda fd: synced.append(fd) or real(fd))
    assert sealed_files.seal(path)
    assert len(synced) >= 2


def test_temp_copies_live_under_the_data_folder_and_boot_sweeps_leftovers(keyed, tmp_path):
    data_dir = keyed
    path = tmp_path / "a.pdf"
    sealed_files.append(path, b"%PDF-1.4 secret", sealed=True)
    with sealed_files.readable(path) as copy:
        assert Path(copy).is_relative_to(data_dir / "tmp")
        assert Path(copy).read_bytes() == b"%PDF-1.4 secret"
    left = data_dir / "tmp" / "tessellate-open-abc"
    left.mkdir(parents=True)
    (left / "x.pdf").write_bytes(b"plain secret")
    (data_dir / "media").mkdir(exist_ok=True)
    stray = data_dir / "media" / ".seal-xyz.tmp"
    stray.write_bytes(b"plain secret")
    kept = data_dir / "media" / "keep.png"
    kept.write_bytes(b"png")
    sealed_files.sweep_leftovers(data_dir)
    assert not left.exists() and not stray.exists() and kept.exists()


def test_a_full_sealed_read_streams_frame_by_frame(keyed, tmp_path):
    path = tmp_path / "a.bin"
    data = _three_frames(path)
    pieces = list(sealed_files.iter_plain(path))
    assert len(pieces) == 3 and b"".join(pieces) == data
    path.write_bytes(path.read_bytes()[: _offsets(path)[2][0] - 4])
    with pytest.raises(sealed_files.SealedDamaged):
        sealed_files.iter_plain(path)

