"""L-general-4: frontend/vendor/PROVENANCE.json names every vendored file
with its hash, size, version, upstream, licence and notice, and the bytes in
the repository are the bytes it names."""

import hashlib
import json
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
VENDOR = ROOT / "frontend" / "vendor"
MANIFEST = json.loads((VENDOR / "PROVENANCE.json").read_text(encoding="utf-8"))


def test_every_hash_and_size_matches_the_file_on_disk():
    for entry in MANIFEST:
        data = (ROOT / entry["path"]).read_bytes()
        assert hashlib.sha256(data).hexdigest() == entry["sha256"], f"{entry['path']} changed: rerun scripts/vendor_provenance.py"
        assert len(data) == entry["size"], entry["path"]


def test_every_vendored_file_is_listed_once_with_its_licence_and_notice():
    on_disk = {
        f"frontend/vendor/{p.relative_to(VENDOR).as_posix()}"
        for p in VENDOR.rglob("*")
        if p.is_file() and p.name != "PROVENANCE.json" and "__pycache__" not in p.parts
    }
    listed = [entry["path"] for entry in MANIFEST]
    assert sorted(listed) == sorted(on_disk) and len(set(listed)) == len(listed)
    for entry in MANIFEST:
        assert entry["upstream"].startswith("https://") and entry["licence"] and entry["version"], entry["path"]
        assert (ROOT / entry["notice"]).is_file(), entry["path"]


def test_the_manifest_is_what_the_script_writes_now():
    """A credits row edited without rerunning the script is caught here."""
    done = subprocess.run([sys.executable, "scripts/vendor_provenance.py", "--check"], cwd=ROOT, capture_output=True, text=True)
    assert done.returncode == 0, done.stdout
