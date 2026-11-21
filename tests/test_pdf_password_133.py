"""L-world-class-133 (WORLD_CLASS 28.4 row 8): a locked PDF asks once, and
the outline panel has the PDF's own bookmarks.

`pdf-info` used to answer a password-protected PDF with "couldn't be opened",
the same words as a broken file, and nothing in the app could open it. Now it
says `locked`, `pdf-unlock` takes the password once (kept in memory for this
run, never written), and every page route opens it after. The PDFs are built
by hand (the standard security handler, revision 2, RC4) so the suite carries
no binary fixture. Needs the pdfpages extra (the CI "Tests (PDF extra)" job).
"""

from __future__ import annotations

import hashlib

import pytest

from tessellate.core import pdfpages

needs_pdfium = pytest.mark.skipif(not pdfpages.available(), reason="the pdfpages extra is not installed")

PAD = bytes.fromhex("28BF4E5E4E758A4164004E56FFFA01082E2E00B6D0683E802F0CA9FE6453697A")
FILE_ID = b"0123456789abcdef"
PASSWORD = "harbour"


def _rc4(key: bytes, data: bytes) -> bytes:
    box = list(range(256))
    j = 0
    for i in range(256):
        j = (j + box[i] + key[i % len(key)]) % 256
        box[i], box[j] = box[j], box[i]
    out, i, j = bytearray(), 0, 0
    for byte in data:
        i = (i + 1) % 256
        j = (j + box[i]) % 256
        box[i], box[j] = box[j], box[i]
        out.append(byte ^ box[(box[i] + box[j]) % 256])
    return bytes(out)


def _padded(password: str) -> bytes:
    return (password.encode("latin-1") + PAD)[:32]


def _pdf(body: bytes, *, password: str | None = None, outline: bool = False) -> bytes:
    """One page with `body` as its text, optionally locked (R2, 40-bit RC4)
    and optionally with two bookmarks pointing at it."""
    content = b"BT /F1 24 Tf 20 40 Td (" + body + b") Tj ET\n"
    catalog = b"<</Type/Catalog/Pages 2 0 R" + (b"/Outlines 6 0 R" if outline else b"") + b">>"
    trailer_extra = b""
    if password is not None:
        perms = -4
        owner = _rc4(hashlib.md5(_padded(password)).digest()[:5], _padded(password))
        key = hashlib.md5(_padded(password) + owner + perms.to_bytes(4, "little", signed=True) + FILE_ID).digest()[:5]
        user = _rc4(key, PAD)
        obj_key = hashlib.md5(key + (4).to_bytes(3, "little") + (0).to_bytes(2, "little")).digest()[:10]
        content = _rc4(obj_key, content)
        trailer_extra = b"/Encrypt 9 0 R/ID[<" + FILE_ID.hex().encode() + b"><" + FILE_ID.hex().encode() + b">]"
    objects = [
        b"1 0 obj" + catalog + b"endobj\n",
        b"2 0 obj<</Type/Pages/Kids[3 0 R]/Count 1>>endobj\n",
        b"3 0 obj<</Type/Page/Parent 2 0 R/MediaBox[0 0 200 100]/Contents 4 0 R/Resources<</Font<</F1 5 0 R>>>>>>endobj\n",
        b"4 0 obj<</Length " + str(len(content)).encode() + b">>stream\n" + content + b"\nendstream endobj\n",
        b"5 0 obj<</Type/Font/Subtype/Type1/BaseFont/Helvetica>>endobj\n",
    ]
    if outline:
        objects += [
            b"6 0 obj<</Type/Outlines/First 7 0 R/Last 8 0 R/Count 2>>endobj\n",
            b"7 0 obj<</Title(Introduction)/Parent 6 0 R/Next 8 0 R/Dest[3 0 R/Fit]>>endobj\n",
            b"8 0 obj<</Title(Results)/Parent 6 0 R/Prev 7 0 R/Dest[3 0 R/Fit]>>endobj\n",
        ]
    if password is not None:
        objects.append(
            b"9 0 obj<</Filter/Standard/V 1/R 2/O<" + owner.hex().encode() + b">/U<" + user.hex().encode()
            + b">/P " + str(perms).encode() + b">>endobj\n"
        )
    return b"%PDF-1.4\n" + b"".join(objects) + b"trailer<</Root 1 0 R" + trailer_extra + b">>"


@pytest.fixture(autouse=True)
def _forget_passwords():
    pdfpages._passwords.clear()
    yield
    pdfpages._passwords.clear()


@needs_pdfium
def test_a_locked_pdf_says_so_and_opens_once_its_password_is_given(tmp_path):
    path = tmp_path / "locked.pdf"
    path.write_bytes(_pdf(b"Hello", password=PASSWORD))
    assert pdfpages.details(path) == {"pages": 0, "locked": True, "outline": []}
    assert pdfpages.render_page(path, 0) is None
    assert pdfpages.unlock(path, "wrong") is False
    assert pdfpages.unlock(path, PASSWORD) is True
    assert pdfpages.details(path)["pages"] == 1
    assert pdfpages.page_count(path) == 1
    assert (pdfpages.render_page(path, 0) or b"")[:8] == b"\x89PNG\r\n\x1a\n"


@needs_pdfium
def test_the_password_follows_the_bytes_not_the_path(tmp_path):
    """A private space's file opens through a fresh temp copy every time."""
    first, copy = tmp_path / "a.pdf", tmp_path / "copy.pdf"
    first.write_bytes(_pdf(b"Hello", password=PASSWORD))
    copy.write_bytes(first.read_bytes())
    assert pdfpages.unlock(first, PASSWORD)
    assert pdfpages.details(copy)["pages"] == 1


@needs_pdfium
def test_the_outline_lists_the_bookmarks_with_their_pages(tmp_path):
    path = tmp_path / "book.pdf"
    path.write_bytes(_pdf(b"Hello", outline=True))
    got = pdfpages.details(path)
    assert got["pages"] == 1 and not got["locked"]
    assert got["outline"] == [
        {"title": "Introduction", "page": 0, "level": 0},
        {"title": "Results", "page": 0, "level": 0},
    ]


@needs_pdfium
def test_the_routes_ask_once_and_then_serve_pages(client):
    up = client.post("/media/upload", files={"file": ("locked.pdf", _pdf(b"Hello", password=PASSWORD), "application/pdf")})
    assert up.status_code in (200, 201), up.text
    name = up.json()["url"].split("/")[-1]
    info = client.get(f"/media/pdf-info/{name}").json()
    assert info["locked"] is True and info["available"] is False
    assert "password" in info["message"]
    wrong = client.post(f"/media/pdf-unlock/{name}", json={"password": "wrong"})
    assert wrong.status_code == 422
    right = client.post(f"/media/pdf-unlock/{name}", json={"password": PASSWORD})
    assert right.status_code == 200, right.text
    assert right.json()["available"] is True and right.json()["pages"] == 1
    page = client.get(f"/media/pdf-page/{name}/0")
    assert page.status_code == 200 and page.content[:4] == b"\x89PNG"


def test_a_locked_pdf_is_never_called_broken():
    from tessellate.api import routes_files

    assert "password" not in routes_files.PDF_UNREADABLE
    assert "password" in routes_files.PDF_LOCKED


def test_the_workspace_and_the_viewer_ask_once_and_list_contents():
    from tests._app_js import app_js_text

    js = app_js_text()
    library = open("frontend/js/library.js", encoding="utf-8").read()
    known = library[library.index("async function ocrKnownPages"):library.index("function ocrRailActive")]
    assert "askPdfPassword(" in known
    ask = js[js.index("async function askPdfPassword"):js.index("askPdfPassword.asked = new Set()")]
    assert "if (askPdfPassword.asked.has(unlockUrl)) return null;" in ask
    assert 'id: "contents"' in library and "const outlineRail = (image) =>" in library
    lightbox = open("frontend/js/lightbox-view.js", encoding="utf-8").read()
    assert "askPdfPassword(" in lightbox
