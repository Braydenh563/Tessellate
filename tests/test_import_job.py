"""The folder import is a durable pool job (Brief 9, the last kind of B2).

It used to run as a request task: a quit mid-way lost the rest of the folder
until the person chose it again. Its runner already skips a file by path and
text hash, so a resumed job finishes where the first stopped.
"""

from __future__ import annotations

import pytest
from sqlalchemy import select

from tessellate.core import deps, jobs, jobstore
from tessellate.core.database import DurableJob
from tests._pool_wait import pool_idle


@pytest.fixture()
def vault(tmp_path, monkeypatch):
    monkeypatch.setenv("HOME", str(tmp_path))
    monkeypatch.setenv("USERPROFILE", str(tmp_path))
    folder = tmp_path / "vault"
    folder.mkdir()
    for i in range(3):
        (folder / f"n{i}.md").write_text(f"vault note {i}", encoding="utf-8")
    return folder


def _contents(client):
    return sorted(e["content"] for e in client.get("/entries?limit=200").json())


def test_import_is_a_named_durable_kind_on_the_batch_lane():
    assert jobstore.HANDLERS["import"] == "tessellate.api.routes_settings:_run_directory_import"
    assert jobs.KIND_LANES["import"] == "batch"
    assert "import" in jobs.OWN_RUN_KINDS
    assert jobs.LABELS["import"]


def test_the_route_queues_a_job_and_the_folder_comes_in(client, vault):
    response = client.post("/import/directory", json={"path": str(vault)})
    assert response.status_code == 202
    assert response.json()["path"] == str(vault.resolve())
    assert pool_idle()
    assert _contents(client) == ["vault note 0", "vault note 1", "vault note 2"]
    with deps.get_db().session() as session:
        rows = list(session.scalars(select(DurableJob).where(DurableJob.kind == "import")))
    assert [r.state for r in rows] == ["done"]


def test_a_launch_after_a_quit_finishes_the_folder(client, vault):
    """A row left queued (the process ended before it ran) is run by resume."""
    db = deps.get_db()
    path = str(vault.resolve())
    jobstore.record("import", (path,), {}, name=vault.name, dedupe_key=("import", path), db=db)
    assert _contents(client) == []
    jobs.resume(db=db)
    assert pool_idle()
    assert _contents(client) == ["vault note 0", "vault note 1", "vault note 2"]
