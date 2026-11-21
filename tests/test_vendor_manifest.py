"""Every vendored file is credited (2026-10-10 triage, decisions 1 and 10;
the owner: "we should reference all the vendored repos and libraries
somewhere to give them credit").

docs/THIRD_PARTY.md names each library under src/tessellate/vendor/ and
frontend/vendor/ with its licence. A Python module vendored here also needs
its licence file beside it (`<name>.LICENSE.txt`); the browser bundles are held
to the same by tests/test_vendor_licences.py. A file that arrives without a
row fails here, which is how 15 MB of uncredited packages, a Windows .exe
among them, would have been caught before they were committed.
"""

from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
PY_VENDOR = ROOT / "src" / "tessellate" / "vendor"
WEB_VENDOR = ROOT / "frontend" / "vendor"
CREDITS = (ROOT / "docs" / "THIRD_PARTY.md").read_text(encoding="utf-8")


def _rows() -> list[str]:
    return [line for line in CREDITS.splitlines() if line.startswith("| ") and not line.startswith("| ---")]


def _credited(name: str) -> str | None:
    """The credits row naming `name` in its Files column, or None."""
    for row in _rows():
        cells = [cell.strip() for cell in row.strip("|").split("|")]
        if len(cells) >= 4 and f"`{name}`" in cells[1]:
            return row
    return None


def test_every_python_module_under_vendor_is_credited_with_a_licence() -> None:
    for path in sorted(PY_VENDOR.iterdir()):
        if path.name in ("__init__.py", "__pycache__") or path.name.endswith(".LICENSE.txt"):
            continue
        assert path.suffix == ".py" and path.is_file(), (
            f"src/tessellate/vendor/{path.name}: vendor single pure-Python modules only"
        )
        row = _credited(path.name)
        assert row, f"src/tessellate/vendor/{path.name} has no row in docs/THIRD_PARTY.md"
        licence = PY_VENDOR / f"{path.stem}.LICENSE.txt"
        assert licence.is_file(), f"{path.name} has no {licence.name} beside it"
        assert f"`{licence.name}`" in row, f"the credits row for {path.name} does not name {licence.name}"


def test_every_browser_bundle_under_vendor_is_credited() -> None:
    for path in sorted(WEB_VENDOR.iterdir()):
        # PROVENANCE.json is the generated manifest of these very files.
        if path.name.endswith(".LICENSE.txt") or path.name == "PROVENANCE.json":
            continue
        name = f"{path.name}/" if path.is_dir() else path.name
        assert _credited(name), f"frontend/vendor/{name} has no row in docs/THIRD_PARTY.md"


def test_the_board_library_data_is_credited_with_its_notices() -> None:
    """The draw.io stencils and the Phosphor path set ship outside vendor/."""
    board = ROOT / "frontend" / "board-library"
    assert _credited("drawio/"), "frontend/board-library/drawio/ has no row in docs/THIRD_PARTY.md"
    assert _credited("icons.json"), "frontend/board-library/icons.json has no row in docs/THIRD_PARTY.md"
    for notice in ("LICENSE", "NOTICE.txt"):
        assert (board / "drawio" / notice).is_file(), f"drawio/{notice} is missing beside the stencil data"
    assert (WEB_VENDOR / "phosphor" / "LICENSE").is_file()


def test_every_credits_row_names_a_licence_and_a_source() -> None:
    for row in _rows()[1:]:
        cells = [cell.strip() for cell in row.strip("|").split("|")]
        if cells[0] == "Library":
            continue
        assert cells[3] and cells[4].startswith("https://"), f"incomplete credits row: {row}"


def test_the_readme_links_the_credits() -> None:
    assert "docs/THIRD_PARTY.md" in (ROOT / "README.md").read_text(encoding="utf-8")
