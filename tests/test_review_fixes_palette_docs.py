"""Source-text and node-executed checks for the review-findings batch."""

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def _js(name: str) -> str:
    return (ROOT / "frontend" / "js" / name).read_text(encoding="utf-8")


def test_agent_commit_files_deletes_imported_documents_on_failure():
    src = _js("palette.js")
    body = src[src.index("async function agentCommitFiles") :]
    body = body[: body.index("\n}\n")]
    assert "for (const id of sent.documentIds)" in body
    assert "`/documents/${id}`" in body
