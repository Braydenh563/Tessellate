"""A stored attachment name cannot reach outside the uploads folder (audit 1028 K7, K8).

`stored_name` comes from the database, and a database restored from someone
else's backup is not trusted: `../secret` or a sibling folder such as
`uploads2` must not be served, read as text, or deleted.
"""

from __future__ import annotations

import io

from tessellate.core import deps
from tessellate.core.database import Attachment
from tessellate.entry import manager


def _attachment(client, session):
    entry = manager.create_entry(session, "a note that carries a file")
    session.commit()
    response = client.post(
        f"/entries/{entry.id}/files",
        files={"file": ("a.txt", io.BytesIO(b"hello"), "text/plain")},
    )
    assert response.status_code in (200, 201), response.text
    return session.get(Attachment, response.json()["attachments"][0]["id"])


def _outside(tmp_path_factory):
    folder = tmp_path_factory.mktemp("outside")
    secret = folder / "secret.txt"
    secret.write_text("private", encoding="utf-8")
    return secret


def test_a_stored_name_outside_the_folder_is_not_served(ai_client, session, tmp_path_factory):
    attachment = _attachment(ai_client, session)
    attachment.stored_name = str(_outside(tmp_path_factory))
    session.commit()
    assert ai_client.get(f"/files/{attachment.id}").status_code == 422
    assert ai_client.get(f"/files/{attachment.id}/text").status_code == 422


def test_a_sibling_folder_with_the_same_prefix_is_refused(ai_client, session):
    attachment = _attachment(ai_client, session)
    uploads = deps.get_config().uploads_dir
    sibling = uploads.parent / (uploads.name + "2")
    sibling.mkdir(exist_ok=True)
    (sibling / "x.txt").write_text("private", encoding="utf-8")
    attachment.stored_name = f"../{uploads.name}2/x.txt"
    session.commit()
    assert ai_client.get(f"/files/{attachment.id}").status_code == 422


def test_deleting_does_not_unlink_a_file_outside(ai_client, session, tmp_path_factory):
    attachment = _attachment(ai_client, session)
    secret = _outside(tmp_path_factory)
    attachment.stored_name = str(secret)
    session.commit()
    manager.delete_attachment(session, attachment, deps.get_config().uploads_dir)
    assert secret.exists()
