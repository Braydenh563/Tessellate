"""The Tesseract engine as one status, one language, and errors that say what to do.

INBOX 443 (3), the owner: "using tesseract and how it operates in the ocr
workspace is still annoying to use and manage." Measured before this: with the
program missing, "Read this image" returned a 200 with no text, and the
workspace announced "Read <file>." over an empty panel; there was no language
choice; and the two halves of the engine (the program, the Python wrapper)
were one word, "installed".
"""

from __future__ import annotations

import base64
import sys

import pytest

from tessellate.core import deps, ocr


@pytest.fixture(autouse=True)
def _fresh_language_cache(app_state):
    # `saved_language` reads the settings, which without an app state are built
    # in the repo's own `data/` folder.
    ocr.clear_language_cache()
    yield
    ocr.clear_language_cache()


def _engine(monkeypatch, *, binary=True, package=True, languages=("eng", "deu", "osd")):
    monkeypatch.setattr(ocr, "tesseract_available", lambda: binary)
    monkeypatch.setattr(ocr, "packages_available", lambda: package)
    monkeypatch.setattr(ocr, "installed_languages", lambda: [c for c in languages if c != "osd"] if binary else [])
    monkeypatch.setattr(ocr, "tesseract_version", lambda: "5.3.4" if binary else "")


def test_status_names_which_half_is_missing(monkeypatch):
    _engine(monkeypatch, binary=False, package=False)
    both = ocr.engine_status()
    assert both["ready"] is False and both["fix"] == "install"
    assert "isn't installed" in both["reason"]

    _engine(monkeypatch, binary=False, package=True)
    assert "program" in ocr.engine_status()["reason"]

    _engine(monkeypatch, binary=True, package=False)
    assert "connects Tesseract" in ocr.engine_status()["reason"]


def test_status_when_ready_lists_languages_and_version(monkeypatch):
    _engine(monkeypatch)
    status = ocr.engine_status()
    assert status["ready"] is True and status["fix"] == "" and status["reason"] == ""
    assert status["version"] == "5.3.4"
    assert [lang["code"] for lang in status["languages"]] == ["eng", "deu"]
    assert status["languages"][1]["name"] == "German"


def test_unavailable_reason_says_where_to_go(monkeypatch):
    _engine(monkeypatch, binary=False, package=False)
    reason = ocr.unavailable_reason()
    assert "Settings, Packages" in reason and "AI vision model" in reason
    assert "\u2014" not in reason
    _engine(monkeypatch)
    assert ocr.unavailable_reason() == ""


def test_installed_languages_parses_the_programs_list(monkeypatch):
    monkeypatch.setattr(ocr.shutil, "which", lambda name: "/usr/bin/tesseract")

    class _Done:
        stdout = ""
        stderr = "List of available languages (3):\neng\nosd\nchi_sim\n"

    monkeypatch.setattr(ocr.subprocess, "run", lambda *a, **k: _Done())
    assert ocr.installed_languages() == ["eng", "chi_sim"]


def test_language_is_remembered_and_validated(monkeypatch, client):
    _engine(monkeypatch)
    assert ocr.saved_language() == ""
    body = client.post("/ocr/language", json={"language": "deu"})
    assert body.status_code == 200
    assert body.json()["language"] == "deu"
    assert ocr.saved_language() == "deu"
    # Persisted where every other preference is, not in the page.
    assert deps.get_config().get_preference("ocr_language") == "deu"
    # A pack that is not installed is refused with the way forward.
    refused = client.post("/ocr/language", json={"language": "fra"})
    assert refused.status_code == 422
    assert "fra" in refused.json()["detail"] and "isn't installed" in refused.json()["detail"]
    # Garbage never reaches the command line.
    assert client.post("/ocr/language", json={"language": "eng; rm -rf /"}).status_code == 422
    # Back to the default.
    assert client.post("/ocr/language", json={"language": ""}).json()["language"] == ""
    assert ocr.saved_language() == ""


def test_a_removed_pack_falls_back_to_the_default_and_says_so(monkeypatch, client):
    _engine(monkeypatch)
    ocr.set_language("deu")
    _engine(monkeypatch, languages=("eng",))
    status = ocr.engine_status()
    assert status["language"] == ""
    assert "no longer installed" in status["language_note"]
    ocr.set_language("")


def test_the_language_reaches_tesseract_only_when_chosen(monkeypatch, tmp_path):
    _engine(monkeypatch)
    seen: list[dict] = []

    class _Image:
        def __enter__(self):
            return self

        def __exit__(self, *a):
            return False

    class _Tess:
        @staticmethod
        def image_to_string(img, **kwargs):
            seen.append(kwargs)
            return "text"

    image_module = type("M", (), {"open": staticmethod(lambda path: _Image())})
    monkeypatch.setitem(sys.modules, "pytesseract", _Tess())
    monkeypatch.setitem(sys.modules, "PIL", type("P", (), {"Image": image_module}))
    monkeypatch.setitem(sys.modules, "PIL.Image", image_module)
    path = tmp_path / "a.png"
    path.write_bytes(b"x")
    ocr.set_language("")
    ocr.extract_text(path)
    ocr.set_language("deu")
    try:
        ocr.extract_text(path)
    finally:
        ocr.set_language("")
    assert seen == [{}, {"lang": "deu"}]


#: A real 1x1 PNG, so the test needs no imaging library.
_PNG = base64.b64decode(
    "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mP8z8BQDwAEhQGAhKmMIQAAAABJRU5ErkJggg=="
)


def _upload_png(client, direct: bool = True) -> int:
    response = client.post(
        "/media/upload",
        files={"file": ("page.png", _PNG, "image/png")},
        data={"direct": "true" if direct else "false"},
    )
    assert response.status_code == 200, response.text
    return response.json()["id"]


def test_reading_without_the_engine_is_an_error_with_a_way_forward(monkeypatch, client):
    media_id = _upload_png(client)
    _engine(monkeypatch, binary=False, package=False)
    response = client.post(f"/media/{media_id}/ocr", json={})
    assert response.status_code == 409
    assert "Settings, Packages" in response.json()["detail"]


def test_a_hand_typed_correction_still_works_without_the_engine(monkeypatch, client):
    media_id = _upload_png(client)
    _engine(monkeypatch, binary=False, package=False)
    response = client.post(f"/media/{media_id}/ocr", json={"text": "fixed by hand"})
    assert response.status_code == 200
    assert response.json()["ocr_text"] == "fixed by hand"


def test_the_readers_endpoint_carries_the_engine(monkeypatch, client):
    _engine(monkeypatch)
    body = client.get("/ocr-readers").json()
    assert body["engine"]["ready"] is True
    assert body["tesseract"] is True


def test_the_packages_row_is_installed_only_when_the_engine_can_read(monkeypatch):
    """The OCR row showed a green tick when only the Python wrapper was there
    (`find_spec` of pytesseract), on a machine whose Library read nothing. It
    also meant the Install button was refused as "already installed"."""
    from tessellate.core import extras

    extra = extras.EXTRAS_BY_ID["ocr"]
    monkeypatch.setattr(extras.importlib.util, "find_spec", lambda name: object())
    monkeypatch.setattr(ocr, "tesseract_available", lambda: False)
    assert extras.is_installed(extra) is False
    monkeypatch.setattr(ocr, "tesseract_available", lambda: True)
    assert extras.is_installed(extra) is True
    monkeypatch.setattr(extras.importlib.util, "find_spec", lambda name: None)
    assert extras.is_installed(extra) is False


def test_read_again_really_reads_again(monkeypatch, client):
    """Found driving the workspace: with a reading already on the row,
    `extract_and_store`'s write-once guard made "Read again" a no-op, and the
    stored rectangles from the first look came back for the second."""
    from tessellate.api import routes_files
    from tessellate.core.database import PageRead

    #: Staged, not direct: a direct upload starts its own background read,
    #: which raced this test for the first answer (seen after a merge).
    media_id = _upload_png(client, direct=False)
    _engine(monkeypatch)
    answers = iter(["first reading", "second reading"])
    monkeypatch.setattr(ocr, "extract_text", lambda path: next(answers))
    first = client.post(f"/media/{media_id}/ocr", json={})
    assert first.json()["ocr_text"] == "first reading"
    # A stored look at the page, as the regions route leaves behind.
    with deps.get_db().session() as session:
        session.add(PageRead(kind="upload", source_id=media_id, page=0, regions='{"x": 1}'))
        session.commit()
    second = client.post(f"/media/{media_id}/ocr", json={})
    assert second.json()["ocr_text"] == "second reading"
    with deps.get_db().session() as session:
        row = session.query(PageRead).filter_by(kind="upload", source_id=media_id, page=0).one()
        assert row.regions == ""
    assert routes_files._page_read_key(None, media_id) == ("upload", media_id)
