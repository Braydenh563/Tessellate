"""Q34, WORLD_CLASS row 36: the sync routes. The merge itself is in test_folder_sync_q34.py."""

from __future__ import annotations


def test_a_first_run_writes_this_computers_file_and_remembers_the_folder(client, tmp_path):
    folder = tmp_path / "shared"
    folder.mkdir()
    client.post("/entries", json={"content": "A note to share"})
    status = client.get("/sync/folder").json()
    assert status["folder"] == "" and status["last"] == ""
    done = client.post("/sync/folder", json={"folder": str(folder), "passphrase": "correct horse battery"})
    assert done.status_code == 200 and done.json()["shared"] == 1
    assert len(list(folder.glob("tessellate-sync-*.json"))) == 1
    again = client.get("/sync/folder").json()
    assert again["folder"] == str(folder) and again["last"] and again["device"]
    # the passphrase is not kept anywhere
    from tessellate.core import deps

    assert "correct horse" not in (deps.get_config().data_dir / "folder_sync_state.json").read_text("utf-8")


def test_a_missing_folder_and_a_short_passphrase_are_said_plainly(client, tmp_path):
    folder = tmp_path / "shared"
    folder.mkdir()
    missing = client.post("/sync/folder", json={"folder": str(tmp_path / "nope"), "passphrase": "correct horse battery"})
    assert missing.status_code == 400 and "folder" in missing.json()["detail"]
    short = client.post("/sync/folder", json={"folder": str(folder), "passphrase": "short"})
    assert short.status_code == 400 and "passphrase" in short.json()["detail"]

