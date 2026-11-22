"""/health says which build is running, since when, on which data folder and
whether it can write there (L-general-6): "is the app I am looking at the code
I just changed?" was answered by guessing."""

from __future__ import annotations

import os
from pathlib import Path

from tessellate.core import buildstamp


def _repo(tmp_path: Path, head: str, refs: dict[str, str] | None = None, packed: str = "") -> Path:
    git = tmp_path / ".git"
    (git / "refs" / "heads").mkdir(parents=True)
    (git / "HEAD").write_text(head, encoding="utf-8")
    for name, sha in (refs or {}).items():
        (git / "refs" / "heads" / name).write_text(sha + "\n", encoding="utf-8")
    if packed:
        (git / "packed-refs").write_text(packed, encoding="utf-8")
    return tmp_path


def test_the_commit_is_read_from_a_branch_a_packed_ref_or_a_detached_head(tmp_path):
    sha = "a" * 40
    assert buildstamp.read_commit(_repo(tmp_path / "1", "ref: refs/heads/main\n", {"main": sha})) == sha
    packed = f"# pack-refs with: peeled\n{'b' * 40} refs/heads/main\n"
    assert buildstamp.read_commit(_repo(tmp_path / "2", "ref: refs/heads/main\n", packed=packed)) == "b" * 40
    assert buildstamp.read_commit(_repo(tmp_path / "3", "c" * 40 + "\n")) == "c" * 40


def test_a_worktree_reads_its_head_and_the_shared_refs(tmp_path):
    main = _repo(tmp_path / "main", "ref: refs/heads/main\n", {"main": "d" * 40, "side": "e" * 40})
    gitdir = main / ".git" / "worktrees" / "wt"
    gitdir.mkdir(parents=True)
    (gitdir / "HEAD").write_text("ref: refs/heads/side\n", encoding="utf-8")
    (gitdir / "commondir").write_text("../..\n", encoding="utf-8")
    tree = tmp_path / "wt"
    tree.mkdir()
    (tree / ".git").write_text(f"gitdir: {gitdir}\n", encoding="utf-8")
    assert buildstamp.read_commit(tree) == "e" * 40


def test_no_git_is_an_empty_commit_not_an_error(tmp_path):
    assert buildstamp.read_commit(tmp_path) == ""
    (tmp_path / ".git").mkdir()
    (tmp_path / ".git" / "HEAD").write_text("ref: refs/heads/gone\n", encoding="utf-8")
    assert buildstamp.read_commit(tmp_path) == ""


def test_health_carries_the_stamp(client, app_state):
    body = client.get("/health").json()
    assert set(body) >= {"source_commit", "started_at", "data_dir_id", "data_dir_writable"}
    assert body["started_at"].endswith("Z")
    assert body["data_dir_writable"] is True
    data_dir = str(Path(app_state.data_dir).resolve())
    assert len(body["data_dir_id"]) == 12 and data_dir not in str(body), "the folder's path is never sent"
    assert body["data_dir_id"] == buildstamp.data_dir_id(app_state.data_dir)


def test_a_read_only_data_folder_is_reported(tmp_path, monkeypatch):
    monkeypatch.setattr(os, "access", lambda path, mode: False)
    assert buildstamp.writable(tmp_path) is False
