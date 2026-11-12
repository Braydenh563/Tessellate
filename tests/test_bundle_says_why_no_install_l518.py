"""L518 (audit 1029 W24): a bundle short of whole with nothing installable
says the package's own reason instead of a bare count. The Live captions
bundle is two packages and offers Install where they can be installed
(measured 2026-11-12: "0 of 2 installed" with Install); W27's doubled "No
model connected" in the Writing room measured once (#draft-offline only)."""

from __future__ import annotations

from pathlib import Path

from tessellate.core import extras

JS = Path(__file__).resolve().parents[1] / "frontend" / "js" / "settings-packages.js"


def test_live_captions_is_a_two_package_bundle():
    bundle = next(b for b in extras.bundles() if b["id"] == "captions")
    assert bundle["extras"] == ["captions", "captionmodel"]


def test_a_bundle_with_nothing_installable_says_why():
    js = JS.read_text(encoding="utf-8")
    at = js.index("} else if (installed < members.length && !body.running) {")
    block = js[at : at + 600]
    assert "!extra.installed && extra.unavailable)?.unavailable" in block
    assert "extras-bundle-why" in block
