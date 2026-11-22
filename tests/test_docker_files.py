"""The Docker files, read as text (OPEN ledger 317, 318): no daemon runs in
the test environment, so what is checked is what a first real build would trip
on, taken from the files themselves. A build is "needs device"."""

from __future__ import annotations

import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DOCKERFILE = (ROOT / "docker" / "Dockerfile").read_text(encoding="utf-8")
COMPOSE = (ROOT / "docker" / "compose.yaml").read_text(encoding="utf-8")


def test_the_compose_build_context_is_the_repo_root():
    """compose resolves `context` against the compose file's own folder, so
    `docker/` plus `..` is the repo; `../..` was this repo's parent and the
    first `docker compose build` found no requirements.txt."""
    match = re.search(r"context:\s*(\S+)", COMPOSE)
    assert match
    context = (ROOT / "docker" / match.group(1)).resolve()
    assert context == ROOT
    dockerfile = re.search(r"dockerfile:\s*(\S+)", COMPOSE).group(1)
    assert (context / dockerfile).is_file()


def test_every_copy_source_exists_in_the_context():
    for line in DOCKERFILE.splitlines():
        if not line.startswith("COPY ") or "--from=" in line:
            continue
        sources = line.split()[1:-1]
        for source in sources:
            assert (ROOT / source).exists(), f"COPY of a missing path: {source}"


def test_the_data_and_model_folders_belong_to_the_user_the_app_runs_as():
    """A named volume takes the owner of the image's folder when one exists
    and root's otherwise: without the chown the app, run as `mm`, could not
    write its notebook."""
    assert re.search(r"mkdir -p /data /models\s*&&\s*chown[^\n]*mm[^\n]*/data /models", DOCKERFILE.replace("\\\n", " "))
    assert DOCKERFILE.index("chown") < DOCKERFILE.index("VOLUME")
    assert DOCKERFILE.index("VOLUME") < DOCKERFILE.index("USER mm")


def test_the_proxy_host_variable_is_offered_in_compose():
    assert "TESSELLATE_ALLOWED_HOSTS" in COMPOSE


def test_the_ignore_file_is_the_one_a_root_context_build_reads():
    """The build context is the repo root, and Docker reads either
    `<context>/.dockerignore` or `<Dockerfile>.dockerignore` beside the
    Dockerfile; `docker/.dockerignore` is read by neither, so `.venv`, `.git`
    and the local `data/` notebook were sent with every build (L-general-5)."""
    assert not (ROOT / "docker" / ".dockerignore").exists()
    ignore = (ROOT / "docker" / "Dockerfile.dockerignore").read_text(encoding="utf-8").split()
    for heavy in (".venv", ".git", "data", "tests", "scratchpad"):
        assert heavy in ignore, heavy


def test_the_image_reports_its_health_from_the_health_route():
    """A HEALTHCHECK on /health so `docker ps` and compose's depends_on see a
    hung server, with Python (the slim image has no curl) on the port the app
    binds."""
    match = re.search(r"^HEALTHCHECK (.+?)(?<!\\)$", DOCKERFILE.replace("\\\n", " "), re.M)
    assert match, "no HEALTHCHECK"
    check = match.group(1)
    assert "/health" in check and "TESSELLATE_PORT" in check
    assert "python" in check and "curl" not in check
    assert DOCKERFILE.index("HEALTHCHECK") > DOCKERFILE.index("TESSELLATE_PORT=8000")
