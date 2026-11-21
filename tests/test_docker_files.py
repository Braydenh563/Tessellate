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


def test_the_image_reports_its_health_from_the_route_that_needs_no_password():
    """L-general-5: an orchestrator restarts a copy whose /health stops
    answering; Python, since the slim image has no curl."""
    check = DOCKERFILE[DOCKERFILE.index("HEALTHCHECK"):DOCKERFILE.index("\nCMD ")]
    assert "/health" in check and "TESSELLATE_PORT" in check and "curl" not in check
    assert DOCKERFILE.index("HEALTHCHECK") > DOCKERFILE.index("USER mm")


def test_the_ignore_file_is_the_one_buildkit_reads_for_this_dockerfile():
    """The context is the repo root and the Dockerfile is docker/Dockerfile,
    so BuildKit reads docker/Dockerfile.dockerignore (or a root one); the old
    docker/.dockerignore was never read and the notebook's data/ went in."""
    assert not (ROOT / "docker" / ".dockerignore").exists()
    ignored = (ROOT / "docker" / "Dockerfile.dockerignore").read_text(encoding="utf-8").split()
    assert {".venv", ".git", "data", "tests", "scratchpad"} <= set(ignored)


def test_the_dockerfile_is_linted_in_ci():
    lint = (ROOT / ".github" / "workflows" / "workflow-lint.yml").read_text(encoding="utf-8")
    assert re.search(r"hadolint-bin==\d", lint) and "hadolint --failure-threshold error docker/Dockerfile" in lint
    assert '"docker/**"' in lint


def test_every_build_carries_the_licence_and_notices():
    """L-general-3: AGPL and the vendored licences go with every copy. The
    installer, the MSI and the Linux archives all take the PyInstaller bundle
    root (installer.iss `dist\\Tessellate\\*`, installer.wxs `DistDir\\**`)."""
    assert "COPY LICENSE ./" in DOCKERFILE and "COPY docs/THIRD_PARTY.md ./" in DOCKERFILE
    for spec in ("linux", "windows"):
        text = (ROOT / "packaging" / spec / "tessellate.spec").read_text(encoding="utf-8")
        assert '(str(REPO_ROOT / "LICENSE"), "."),' in text, spec
        assert '(str(REPO_ROOT / "docs" / "THIRD_PARTY.md"), "."),' in text, spec
    iss = (ROOT / "packaging" / "windows" / "installer.iss").read_text(encoding="utf-8")
    wxs = (ROOT / "packaging" / "windows" / "installer.wxs").read_text(encoding="utf-8")
    assert 'Source: "..\\..\\dist\\Tessellate\\*"' in iss and '<Files Include="$(var.DistDir)\\**" />' in wxs
