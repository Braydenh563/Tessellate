"""L-world-class-411: Starlette's multipart reader stops at 1,000 files with
a bare 400 before the route runs, so a vault picked as a folder of more never
reached `/import/app`'s own cap. The import router parses the form with the
import's own cap first (`routes_import._ManyFilesRoute`, the base's fix; this
branch's `bounds.FolderUploadRoute` was the same fix and gave way to it)."""

from __future__ import annotations

from tessellate.api import routes_import


def test_twelve_hundred_files_reach_the_route(client):
    files = [("files", (f"vault/n{i}.md", f"# Note {i}\n\nbody {i}".encode(), "text/markdown")) for i in range(1200)]
    response = client.post("/import/app?source=obsidian", files=files)
    assert response.status_code == 201, response.text[:200]
    assert response.json()["imported"] == 1200
    assert routes_import.router.route_class is routes_import._ManyFilesRoute, "the import router parses with its own cap"
