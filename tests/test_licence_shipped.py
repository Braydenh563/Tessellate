"""The licence and the third-party credits travel inside every build.

AGPL-3.0 and the vendored libraries' notices must reach a person who gets the
installer, the MSI (harvested from the same PyInstaller output), the Linux
tarball or the Docker image. A build is not something a unit test can run, so
this reads each build file (L-general-3).
"""

from __future__ import annotations

import pathlib

ROOT = pathlib.Path(__file__).resolve().parent.parent


def _text(*parts: str) -> str:
    return ROOT.joinpath(*parts).read_text(encoding="utf-8")


def test_the_files_exist():
    assert (ROOT / "LICENSE").is_file()
    assert (ROOT / "docs" / "THIRD_PARTY.md").is_file()


def test_both_pyinstaller_specs_bundle_them():
    # The Windows installer, the MSI and the Linux tarball all take their files
    # from the PyInstaller output, so the specs are where they are added.
    for spec in (("packaging", "windows", "tessellate.spec"), ("packaging", "linux", "tessellate.spec")):
        text = _text(*spec)
        assert '"LICENSE"' in text and '"THIRD_PARTY.md"' in text, spec


def test_the_installer_and_msi_take_the_whole_bundle():
    assert "dist\\Tessellate\\*" in _text("packaging", "windows", "installer.iss")
    assert "dist" in _text("packaging", "windows", "installer.wxs")


def test_the_docker_image_copies_them():
    text = _text("docker", "Dockerfile")
    assert "LICENSE" in text and "THIRD_PARTY.md" in text
