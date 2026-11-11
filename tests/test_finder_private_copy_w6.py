"""Find anything says private notes are not searched when the notebook holds some (W6, sweep-1028b:
"Ctrl+P Sara ... No note holds Sara" while private note 1 held it; private notes are never indexed)."""

import json
import shutil
import subprocess
from pathlib import Path

import pytest

SEARCH = (Path(__file__).resolve().parents[1] / "frontend" / "js" / "search.js").read_text(encoding="utf-8")


def _why(kind: str, entries: list[dict]) -> str:
    node = shutil.which("node")
    if not node:
        pytest.skip("node is not installed")
    a = SEARCH.index("function finderWhyNothing(")
    b = SEARCH.index("async function finderOffer(")
    script = (
        f"const FINDER_KINDS = {json.dumps([{'key': 'note', 'many': 'notes'}, {'key': 'document', 'many': 'documents'}])};"
        f"let finderKind = {json.dumps(kind)}; const allEntries = {json.dumps(entries)};"
        + SEARCH[a:b]
        + "console.log(JSON.stringify(finderWhyNothing('Sara')));"
    )
    return json.loads(subprocess.run([node, "-e", script], capture_output=True, text=True, check=True).stdout)


def test_the_empty_copy_names_private_notes_when_there_are_some():
    assert _why("", [{"is_private": True}]).endswith("Private notes are not searched.")
    assert _why("note", [{"is_private": True}]).endswith("Private notes are not searched.")


def test_no_private_notes_or_another_kind_leaves_the_copy_alone():
    assert "Private" not in _why("", [{"is_private": False}])
    assert "Private" not in _why("", [])
    assert "Private" not in _why("document", [{"is_private": True}])
