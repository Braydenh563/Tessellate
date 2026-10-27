"""The launchers no longer carry a torch path (the owner, 2026-10-27).

`TESSELLATE_SYSTEM_SITE_PACKAGES=1` existed so a CUDA torch installed
system-wide was not downloaded a second time, and `scripts/system_site_packages.py`
refused a venv whose torch fell outside requirements.txt's `torch>=X,<Y` line.
Search by meaning runs on fastembed now: requirements.txt has no torch line (the
script fell back to a made-up range) and the biggest package it adds is ONNX
Runtime at about 24 MB, so there is nothing worth sharing and a shared system
package can only shadow the one the app was tested with. The opt-in, its script
and its tests went; this holds the door shut.
"""

from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent


def test_the_script_that_checked_the_system_torch_is_gone():
    assert not (ROOT / "scripts" / "system_site_packages.py").exists()


def test_neither_launcher_builds_the_venv_with_the_system_packages():
    for name in ("start.sh", "start.bat"):
        text = (ROOT / name).read_text(encoding="utf-8")
        assert "SYSTEM_SITE_PACKAGES" not in text, name
        assert "system-site-packages" not in text, name
        assert "system_site_packages" not in text, name
    assert '"$PYTHON" -m venv .venv' in (ROOT / "start.sh").read_text(encoding="utf-8")
    assert "!PYTHON! -m venv .venv" in (ROOT / "start.bat").read_text(encoding="utf-8")


def test_the_install_guide_does_not_offer_to_share_a_torch():
    text = (ROOT / "docs" / "INSTALL.md").read_text(encoding="utf-8")
    assert "SYSTEM_SITE_PACKAGES" not in text
    assert "torch" not in text.lower()


def test_requirements_pin_no_torch():
    """The range the script read is gone from requirements.txt too."""
    lines = (ROOT / "requirements.txt").read_text(encoding="utf-8").splitlines()
    assert not [line for line in lines if line.strip().lower().startswith(("torch", "sentence-transformers"))]
