"""Audit 1030 extras, the small rows.

- Y4: every space row's actions were "Delete this space", "Rename this
  space": nine of each with nine spaces. Each names its space.
- Y8: a space named "ALL" sat beside "All spaces" in the switcher. "All",
  "All spaces" and "Everything" are refused as names (a restore keeps its own).
- Y13: no file manager for the lock card's logs folder answered 500, a server
  fault in the log; it is 503.
"""

from __future__ import annotations

from pathlib import Path

import pytest
from fastapi import HTTPException

from test_forgot_password import (  # noqa: F401  # the fixtures are autouse there
    _clean,
    _devices_already_allowed,
    _known_code,
    _local,
    _notebook,
)

ROOT = Path(__file__).resolve().parent.parent
SPACES_JS = (ROOT / "frontend" / "js" / "spaces-find.js").read_text(encoding="utf-8")


def test_each_space_action_names_its_space():
    assert "this space" not in SPACES_JS.split("function spaceMenuOption", 1)[1].split("\n}\n", 1)[0]
    for label in ("`Rename ${name}`", "`Delete ${name}`", "`Hide ${name} from All spaces`"):
        assert label in SPACES_JS


@pytest.mark.parametrize("name", ["ALL", "all spaces", " All  Spaces ", "Everything"])
def test_the_everything_view_names_are_not_space_names(client, name):
    response = client.post("/spaces", json={"name": name})
    assert response.status_code == 400, response.text
    assert "view of every space" in response.json()["detail"]


def test_an_ordinary_name_with_all_in_it_is_fine(client):
    response = client.post("/spaces", json={"name": "All hands"})
    assert response.status_code in (200, 201)


def test_a_reserved_name_cannot_come_in_by_rename(client):
    sid = client.post("/spaces", json={"name": "Garden plot"}).json()["id"]
    response = client.put(f"/spaces/{sid}", json={"name": "All"})
    assert response.status_code == 400


def test_no_file_manager_for_the_logs_folder_is_503(client, monkeypatch):
    from tessellate.api import routes_files

    _notebook(client)

    def refuse(folder, label):
        raise HTTPException(status_code=500, detail=f"no file manager for {folder}")

    monkeypatch.setattr(routes_files, "reveal_folder", refuse)
    response = _local(client).post("/auth/reset-code/open-logs")
    assert response.status_code == 503
    assert "/" not in response.json()["detail"]
