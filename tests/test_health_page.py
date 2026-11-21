"""The Health page's backend (WORLD_CLASS_PLAN 28.1 rule 14): the last
backup, the last error, what is running, the data dir's size and an
integrity check in one click, each field present and dated."""

from __future__ import annotations

import logging

from tessellate.core import activity


def test_health_carries_every_rule_14_field_dated(client):
    logging.getLogger("tessellate.test").error("a planted failure")
    job = activity.start("generation", "Answering in Chat", stoppable=True)
    try:
        body = client.get("/debug/health").json()
    finally:
        activity.finish(job)
    trust = body["trust"]
    assert trust["checked_at"]
    assert set(trust) >= {"last_backup", "last_error", "running", "data_dir_bytes", "integrity"}
    assert trust["last_backup"] == {"at": None, "name": ""}, "no backup yet is a dated-or-none answer"
    assert trust["last_error"]["at"] and "planted" in trust["last_error"]["line"]
    assert any(row["kind"] == "generation" for row in trust["running"])
    assert trust["data_dir_bytes"] > 0


def test_a_backup_is_named_with_its_date(client):
    made = client.post("/backups")
    assert made.status_code == 201
    trust = client.get("/debug/health").json()["trust"]
    assert trust["last_backup"]["at"] and trust["last_backup"]["name"].startswith("tessellate-")


def test_the_integrity_check_runs_in_one_call_and_is_remembered(client):
    checked = client.post("/debug/health/integrity").json()
    assert checked["ok"] is True and checked["result"] == "ok"
    assert checked["at"] and "notes" in checked["index"]
    trust = client.get("/debug/health").json()["trust"]
    assert trust["integrity"]["at"] == checked["at"]


def test_health_names_the_running_build_to_this_computer(client):
    """L-general-6: commit, start time, notebook id and whether its folder
    takes writes, for this computer's page (Settings > About shows them)."""
    body = client.get("/health").json()
    assert set(body) >= {"source_commit", "started_at", "data_dir_id", "data_dir_writable"}
    assert body["data_dir_writable"] is True
    assert len(body["data_dir_id"]) == 12
    assert body["source_commit"] == "" or len(body["source_commit"]) == 40


def test_the_commit_is_read_from_a_worktree_without_running_git(tmp_path):
    from tessellate.core import build_stamp

    sha = "a" * 40
    main = tmp_path / "main" / ".git"
    (main / "refs" / "heads").mkdir(parents=True)
    (main / "packed-refs").write_text(f"# pack-refs\n{sha} refs/heads/topic\n", encoding="utf-8")
    wt_git = main / "worktrees" / "wt"
    wt_git.mkdir(parents=True)
    (wt_git / "HEAD").write_text("ref: refs/heads/topic\n", encoding="utf-8")
    (wt_git / "commondir").write_text("../..\n", encoding="utf-8")
    wt = tmp_path / "wt"
    wt.mkdir()
    (wt / ".git").write_text(f"gitdir: {wt_git}\n", encoding="utf-8")
    assert build_stamp.source_commit.__wrapped__(wt) == sha


def test_a_build_stamp_beats_the_checkout(monkeypatch, tmp_path):
    from tessellate.core import build_stamp

    monkeypatch.setenv("TESSELLATE_SOURCE_COMMIT", "B" * 40)
    assert build_stamp.source_commit.__wrapped__(tmp_path) == "b" * 40
