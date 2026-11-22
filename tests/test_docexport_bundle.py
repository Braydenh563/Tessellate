"""A document leaves with its pictures.

DOCUMENTS_PLAN Phase 7. `export.md` hands over the text alone, and a document
with images in it then lands somewhere else with `/media/…` links that resolve
to nothing, because the pictures live in this notebook and the file does not.
The bundle is the answer to that, and the two things worth testing about it are
the two that would be silently wrong: that the picture is really in the zip, and
that the markdown's own link now points at it.

The Word export is written in the browser now (`documents-word.js`,
`tests/test_word_files_b42.py`); the python-docx extra is retired (Brief 42).
"""

from __future__ import annotations

import io
import zipfile


from tessellate.core import docexport

PNG = bytes.fromhex(
    "89504e470d0a1a0a0000000d4948445200000001000000010806000000"
    "1f15c4890000000a49444154789c6300010000050001"
    "0d0a2db40000000049454e44ae426082"
)


def _document_with_image(client, app_state) -> tuple[int, str]:
    """A document that references one upload, with the file really on disk."""
    media = app_state.data_dir / "media"
    media.mkdir(parents=True, exist_ok=True)
    (media / "dot.png").write_bytes(PNG)
    #: The row as well as the file: `referenced_names` reads the text, but a
    #: bundle that carried a file with no upload row behind it would be
    #: testing something the app never produces.
    from tessellate.core import deps
    from tessellate.core.database import MediaUpload

    with deps.get_db().session() as session:
        session.add(MediaUpload(filename="dot.png", original_name="dot.png"))
        session.commit()
    content = "# Notes\n\nHere it is:\n\n![a dot](/media/dot.png)\n"
    created = client.post(
        "/documents", json={"title": "With a picture", "content": content}
    ).json()
    return created["id"], content


def test_the_bundle_carries_the_picture_and_points_at_it(client, app_state):
    document_id, _ = _document_with_image(client, app_state)

    response = client.get(f"/documents/{document_id}/export.zip")

    assert response.status_code == 200
    assert response.headers["content-type"] == "application/zip"
    assert "With-a-picture.zip" in response.headers["content-disposition"]
    assert response.headers["X-Assets"] == "1"
    archive = zipfile.ZipFile(io.BytesIO(response.content))
    names = set(archive.namelist())
    assert "assets/dot.png" in names
    markdown = next(name for name in names if name.endswith(".md"))
    body = archive.read(markdown).decode("utf-8")
    assert "![a dot](assets/dot.png)" in body
    assert "/media/dot.png" not in body
    assert body.startswith("# With a picture")
    assert archive.read("assets/dot.png") == PNG


def test_a_link_to_a_file_that_is_gone_is_left_alone(client, app_state):
    """Better an honest `/media/` link than a relative one to nothing."""
    content = "![missing](/media/not-here.png)"
    created = client.post(
        "/documents", json={"title": "Missing", "content": content}
    ).json()

    response = client.get(f"/documents/{created['id']}/export.zip")

    assert response.headers["X-Assets"] == "0"
    archive = zipfile.ZipFile(io.BytesIO(response.content))
    body = archive.read("Missing.md").decode("utf-8")
    assert "/media/not-here.png" in body
    assert "assets/" not in body


def test_a_comment_travels_as_a_footnote_in_the_bundle(client, app_state):
    created = client.post(
        "/documents",
        json={"title": "Remarks", "content": "Some ==words== %%about them%%.\n"},
    ).json()

    response = client.get(f"/documents/{created['id']}/export.zip")

    archive = zipfile.ZipFile(io.BytesIO(response.content))
    body = archive.read("Remarks.md").decode("utf-8")
    assert "[^c1]" in body
    assert "[^c1]: about them" in body
    assert "%%" not in body


def test_a_code_document_is_refused_a_bundle(client, app_state):
    created = client.post(
        "/documents",
        json={"title": "Script", "content": "print('hi')", "file_type": "py"},
    ).json()

    response = client.get(f"/documents/{created['id']}/export.zip")

    assert response.status_code == 400
    assert "markdown" in response.json()["detail"]


def test_a_name_cannot_climb_out_of_the_media_folder(app_state, tmp_path):
    """The names come out of a document's own text, which is user input."""
    secret = tmp_path / "secret.txt"
    secret.write_text("not yours", encoding="utf-8")
    media = app_state.data_dir / "media"
    media.mkdir(parents=True, exist_ok=True)

    data, carried = docexport.bundle(
        "Climb", "![x](/media/x.png)", media, {"../secret.txt", "secret.txt"}
    )

    assert carried == []
    assert set(zipfile.ZipFile(io.BytesIO(data)).namelist()) == {"Climb.md"}


def test_citations_leave_as_footnotes():
    text = "Claim [@lamport] and [@missing].\n\n```\n[@lamport] in code\n```\n\n[@lamport]: <https://example.org/paper>\n"
    out = docexport.citations_to_footnotes(text)
    assert "Claim [^lamport] and [@missing]." in out
    assert "[@lamport] in code" in out
    assert "[^lamport]: <https://example.org/paper>" in out
    assert docexport.citations_to_footnotes("no keys [@x]") == "no keys [@x]"


def test_export_md_carries_citations_as_footnotes(client):
    doc = client.post("/documents", json={"title": "Cited", "content": "# Cited\n\nA claim [@a].\n\n[@a]: the source\n"}).json()
    body = client.get(f"/documents/{doc['id']}/export.md").text
    assert "A claim [^a]." in body and "[^a]: the source" in body
