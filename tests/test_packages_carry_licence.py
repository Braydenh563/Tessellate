"""Every build ships the AGPL text and the bundled parts' notices (L-general-3).

A copy of the program is a copy under AGPL-3.0, and docs/THIRD_PARTY.md names the licences of what
is bundled. Before, no build file named either. Each package is built from PyInstaller's folder, so
the two PyInstaller specs carry them, and each package's own file is checked to package that folder.
"""

from __future__ import annotations

import re
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]


@pytest.mark.parametrize("spec", ["packaging/windows/tessellate.spec", "packaging/linux/tessellate.spec"])
def test_the_frozen_folder_holds_the_licence_and_the_notices(spec):
    text = (ROOT / spec).read_text(encoding="utf-8")
    datas = text[text.index("datas=[") : text.index("],", text.index("datas=["))]
    assert '(str(REPO_ROOT / "LICENSE"), ".")' in datas
    assert '(str(REPO_ROOT / "docs" / "THIRD_PARTY.md"), ".")' in datas
    assert (ROOT / "LICENSE").is_file() and (ROOT / "docs" / "THIRD_PARTY.md").is_file()


def test_the_installer_packages_the_frozen_folder_whole():
    """It copies only that folder (tests/test_packaging_launchers.py), so the licence rides in it."""
    iss = (ROOT / "packaging/windows/installer.iss").read_text(encoding="utf-8")
    assert 'Source: "..\\..\\dist\\Tessellate\\*"' in iss[iss.index("[Files]") :]


def test_the_msi_harvests_the_same_folder():
    wxs = (ROOT / "packaging/windows/installer.wxs").read_text(encoding="utf-8")
    assert '<Files Include="$(var.DistDir)\\**" />' in wxs


def test_the_linux_zip_is_the_frozen_folder():
    release = (ROOT / ".github/workflows/release.yml").read_text(encoding="utf-8")
    assert re.search(r'zip -qr "\.\./Tessellate-\$\{VERSION\}-linux-x86_64\.zip" "Tessellate"', release)
