"""Every build ships the licence and the third-party notices (L-general-3):
AGPL section 4 and the CC BY-SA and MIT notices in docs/THIRD_PARTY.md travel
with each copy. The Windows installer and the MSI package the PyInstaller
output whole, so the two specs carry them for the .exe, the .msi and the
Linux tarball and zip; the Docker image copies them itself."""

from __future__ import annotations

import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
NOTICES = ("LICENSE", "THIRD_PARTY.md")


def _spec_datas(path: Path) -> str:
    text = path.read_text(encoding="utf-8")
    return text[text.index("datas=[") :]


def test_both_pyinstaller_specs_bundle_the_licence_and_notices():
    """Each spec's datas names LICENSE and docs/THIRD_PARTY.md at the bundle root."""
    for spec in ("packaging/windows/tessellate.spec", "packaging/linux/tessellate.spec"):
        datas = _spec_datas(ROOT / spec)
        for name in NOTICES:
            assert re.search(rf'"{re.escape(name)}"\)?\s*\)?,\s*"\."\)', datas), f"{spec} does not ship {name}"


def test_the_installers_package_the_whole_pyinstaller_output():
    """installer.iss and installer.wxs take dist/Tessellate whole, so the spec's files reach both."""
    iss = (ROOT / "packaging/windows/installer.iss").read_text(encoding="utf-8")
    assert 'Source: "..\\..\\dist\\Tessellate\\*"' in iss and "recursesubdirs" in iss
    wxs = (ROOT / "packaging/windows/installer.wxs").read_text(encoding="utf-8")
    assert "DistDir" in wxs and "<Files " in wxs


def test_the_docker_image_copies_the_licence_and_notices():
    """The image's /app holds both, and the build context does not exclude them."""
    dockerfile = (ROOT / "docker/Dockerfile").read_text(encoding="utf-8")
    assert re.search(r"^COPY LICENSE docs/THIRD_PARTY\.md \./", dockerfile, re.M)
    ignored = (ROOT / "docker/Dockerfile.dockerignore").read_text(encoding="utf-8").split()
    assert not {"LICENSE", "docs", "docs/THIRD_PARTY.md", "*.md"} & set(ignored)


def test_the_notices_exist():
    """Both files are where the builds read them."""
    assert (ROOT / "LICENSE").is_file() and (ROOT / "docs/THIRD_PARTY.md").is_file()
