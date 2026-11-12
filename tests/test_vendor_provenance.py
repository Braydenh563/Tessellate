"""frontend/vendor/PROVENANCE.json says where every vendored file came from.

The hashes are recomputed here, so a vendored file edited by hand (or swapped
for a different build) fails until the file is regenerated with
`python scripts/vendor_provenance.py` and the change is reviewed (L-general-4).
"""

from __future__ import annotations

import hashlib
import json
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
VENDOR = ROOT / "frontend" / "vendor"
ENTRIES = json.loads((VENDOR / "PROVENANCE.json").read_text(encoding="utf-8"))["files"]


def test_every_vendored_file_is_listed_and_nothing_else():
    on_disk = {p.relative_to(VENDOR).as_posix() for p in VENDOR.rglob("*") if p.is_file()}
    on_disk.discard("PROVENANCE.json")
    assert {e["path"] for e in ENTRIES} == on_disk


@pytest.mark.parametrize("entry", ENTRIES, ids=lambda e: e["path"])
def test_the_hash_and_size_match_the_file(entry):
    data = (VENDOR / entry["path"]).read_bytes()
    assert hashlib.sha256(data).hexdigest() == entry["sha256"]
    assert len(data) == entry["size"]


def test_every_entry_names_its_library_licence_and_upstream():
    for e in ENTRIES:
        assert e["library"] and e["licence"] and e["upstream"].startswith("http"), e["path"]
