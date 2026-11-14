"""`POST /whiteboard/convert`: other tools' diagrams read into the board's graph (L-whiteboard-41, 45).

One route for the Import dialog: the client sends the text of a GraphML, Miro JSON or PlantUML file (or an
EMF as base64) and gets back a plain graph the board places with the placer its Mermaid import uses. It
reads and answers; it writes nothing and fetches nothing. Readers, caps and XML hardening: `wb_convert.py`.
"""

from __future__ import annotations

from fastapi import APIRouter
from pydantic import BaseModel, Field, field_validator

from tessellate.api import wb_config, wb_convert

router = APIRouter(prefix="/whiteboard", tags=["whiteboard"])


class ConvertRequest(BaseModel):
    format: str = "auto"
    #: Over the cap is a 413 from the reader with a sentence, so the field's own limit sits a little above it.
    content: str | None = Field(default=None, max_length=wb_convert.MAX_CONVERT_CHARS + 1)
    data_b64: str | None = Field(default=None, max_length=wb_convert.MAX_EMF_BYTES * 4 // 3 + 16)

    @field_validator("format")
    @classmethod
    def _known(cls, value: str) -> str:
        if value not in wb_convert.FORMATS:
            raise ValueError("Unknown format: expected one of " + ", ".join(wb_convert.FORMATS))
        return value


@router.post("/convert")
def convert_board_file(body: ConvertRequest) -> dict:
    return wb_convert.convert(body.format, body.content, body.data_b64)


class ConfigCheckRequest(BaseModel):
    content: str = Field(max_length=wb_config.MAX_CONFIG_CHARS + 1)


@router.post("/config/check")
def check_board_config(body: ConfigCheckRequest) -> dict:
    """A board configuration file's text, checked and cleaned (L-whiteboard-44). Stores nothing: the client applies it."""
    return wb_config.check_config(body.content)
