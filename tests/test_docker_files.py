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


def test_the_image_reports_its_own_health():
    """L-general-5: an orchestrator could not tell a container whose app had died from a live one.
    The slim image has no curl, so the check is the interpreter asking /health on the served port."""
    match = re.search(r"^HEALTHCHECK\b(.*?)CMD (\[.*\])$", DOCKERFILE.replace("\\\n", " "), re.M)
    assert match, "no HEALTHCHECK"
    assert "--interval=" in match.group(1) and "--start-period=" in match.group(1)
    cmd = match.group(2)
    assert cmd.startswith('["python"') and "/health" in cmd and "TESSELLATE_PORT" in cmd
    assert re.search(r"TESSELLATE_PORT=8000", DOCKERFILE)


def test_the_build_context_never_carries_the_notebook_or_a_venv():
    """The whole context goes to the daemon before any COPY runs."""
    ignore = (ROOT / ".dockerignore").read_text(encoding="utf-8")
    entries = {line.strip() for line in ignore.splitlines() if line.strip() and not line.startswith("#")}
    for private in ("data", ".venv", ".git", "*.db"):
        assert private in entries, private
    import fnmatch

    for line in DOCKERFILE.splitlines():
        if not line.startswith("COPY ") or "--from=" in line:
            continue
        for source in line.split()[1:-1]:
            top = source.rstrip("/").split("/")[0]
            assert not any(fnmatch.fnmatch(top, e) or fnmatch.fnmatch(source, e) for e in entries), source


def test_the_licence_and_notices_ship_in_the_image():
    """L-general-3, the Docker part: AGPL-3.0 travels with every copy of the program."""
    assert re.search(r"^COPY [^\n]*\bLICENSE\b", DOCKERFILE, re.M)
    assert re.search(r"^COPY [^\n]*docs/THIRD_PARTY\.md", DOCKERFILE, re.M)
    assert "COPY --from=build /app /app" in DOCKERFILE


def test_ci_lints_the_dockerfile_with_hadolint():
    """L-general-5: the official action reads docker/Dockerfile on every pull request."""
    ci = (ROOT / ".github" / "workflows" / "ci.yml").read_text(encoding="utf-8")
    job = re.search(r"\n  dockerfile:\n(.*?)(?=\n  \w[\w-]*:\n)", ci, re.S)
    assert job, "no hadolint job in ci.yml"
    assert "uses: hadolint/hadolint-action@" in job.group(1)
    assert "dockerfile: docker/Dockerfile" in job.group(1)
    assert "failure-threshold" not in job.group(1), "the default threshold is the check"
