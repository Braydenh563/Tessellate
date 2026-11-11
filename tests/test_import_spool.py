"""K34: an upload is sized and opened from its spooled file, never read whole."""

from __future__ import annotations

import io
import zipfile

import pytest
from fastapi import HTTPException, UploadFile

from tessellate.api import routes_import
from tessellate.entry import app_import


class _NoWholeRead(io.BytesIO):
    """Fails on a read of the whole file; members come through the zip.

    A sizeless read is judged by what it would return: Python 3.11's zipfile reads the
    22-byte end record with a bare `read()` from 22 bytes before the end, which is not the upload."""

    def read(self, size: int | None = -1) -> bytes:
        wanted = len(self.getvalue()) - self.tell() if size is None or size < 0 else size
        if wanted > 1024 * 1024 or (self.tell() == 0 and wanted >= len(self.getvalue())):
            raise AssertionError("the upload was read whole")
        return super().read(size)


def _zip_bytes(members: dict[str, str]) -> bytes:
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w") as archive:
        for name, text in members.items():
            archive.writestr(zipfile.ZipInfo(name, date_time=(2026, 10, 1, 12, 0, 0)), text)
    return buffer.getvalue()


def test_received_hands_back_the_spooled_file_unread() -> None:
    upload = UploadFile(file=_NoWholeRead(b"x" * 5000), filename="vault.zip")
    [(name, handle)] = routes_import._received([upload])
    assert name == "vault.zip" and handle is upload.file


def test_received_refuses_past_the_cap(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(app_import, "MAX_ARCHIVE_BYTES", 10)
    with pytest.raises(HTTPException) as err:
        routes_import._received([UploadFile(file=io.BytesIO(b"x" * 11), filename="a.md")])
    assert err.value.status_code == 413


def test_expand_opens_a_zip_from_a_file_object() -> None:
    data = _zip_bytes({"a.md": "# A\n", "b/c.md": "# C\n"})
    out = dict(app_import.expand([("v.zip", _NoWholeRead(data))]))
    assert out == {"a.md": b"# A\n", "b/c.md": b"# C\n"}


def test_expand_reads_a_plain_file_object() -> None:
    out = app_import.expand([("n.md", io.BytesIO(b"# N\n"))])
    assert out == [("n.md", b"# N\n")]


def test_expand_still_skips_a_big_plain_file() -> None:
    skipped: list[str] = []
    out = app_import.expand([("n.md", io.BytesIO(b"x" * 20))], skipped, max_file=10)
    assert out == [] and "larger than" in skipped[0]
