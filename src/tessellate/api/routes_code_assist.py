"""`POST /documents/{id}/code-assist`: the code panel's assistant (INBOX 788).

The client sends the code it means (the selection, or the file as it is on
screen, saved or not), the ask and, for a fix, the diagnostic at the caret;
`ai/code_assist.py` answers through the documents feature's model, or needle
choosing a deterministic tool, or says what needs a model. Nothing is
written: a change comes back for the person to apply or reject, as
`/ai-edit`'s proposals do.
"""

from __future__ import annotations

from typing import Literal

from fastapi import APIRouter, Depends
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from tessellate.ai import code_assist
from tessellate.core import deps, filetypes
from tessellate.repo import documents as documents_repo
from tessellate.core.deps import get_session

router = APIRouter(tags=["documents"])


class CodeAssistBody(BaseModel):
    action: Literal["ask", "explain", "fix", "tests", "refactor"]
    code: str = Field(default="", max_length=200_000)
    question: str = Field(default="", max_length=2000)
    diagnostic: str = Field(default="", max_length=2000)


@router.post("/documents/{document_id}/code-assist")
def code_assist_route(document_id: int, body: CodeAssistBody, session: Session = Depends(get_session)) -> dict:
    document = documents_repo.get(session, document_id)
    code = body.code if body.code.strip() else document.content or ""
    return code_assist.answer(
        body.action,
        filetypes.normalise(document.file_type),
        code,
        deps.get_model_manager().for_feature("documents"),
        deps.get_ollama(),
        question=body.question,
        diagnostic=body.diagnostic,
    )
