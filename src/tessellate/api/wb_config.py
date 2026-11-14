"""A board's configuration as a file (L-whiteboard-44): default styles, palettes and the shape-library choices.

**What "plugins" means here, decided 2026-11-14 on the row:** draw.io's plugins are third-party JavaScript the
page runs. This app's CSP forbids that (no `unsafe-eval`, no remote or inline script), and an offline,
local-first notebook should not run code that arrived in a file. So the equivalent is *declarative*: this
JSON, which can set what a board starts with and nothing else. It is data, checked against a schema, and it
cannot name a script, a URL or a function.

The file::

    {"format": "tessellate-board-config", "version": 1,
     "board": {"defaults": {"shape": {...}, "link": {...}}, "grid_size": 24, "guides": true, "paper": "a4", ...},
     "palettes": [{"name": "Brand", "colours": ["#336699", ...]}],
     "shape_libraries_off": ["drawio-bpmn"]}

`board` is the same set of fields `BoardBackground` already validates (default styles, grid, paper, units,
switches), minus the picture: an image is an upload of this notebook's and does not travel in a file. Every
field is checked by that model, so an import cannot store what the board's own Format panel could not.
"""

from __future__ import annotations

import json
import re

from fastapi import HTTPException
from pydantic import BaseModel, ConfigDict, Field, ValidationError, field_validator

from tessellate.api.wb_board import BOARD_BG_COLOR_RE, BoardBackground

CONFIG_FORMAT = "tessellate-board-config"
CONFIG_VERSION = 1
MAX_CONFIG_CHARS = 100_000
MAX_PALETTES = 8
MAX_LIBRARIES = 60
#: A built-in set's key: words, digits and the few marks a set key carries ("drawio-basic", "icons").
_SET_KEY = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]{0,63}$")
#: What the board section may hold. `image` and `color` are left out on purpose: a picture is an upload of this
#: notebook's, and the colour belongs to the theme a person chose.
BOARD_FIELDS = (
    "defaults",
    "grid_size",
    "grid_color",
    "guides",
    "page_view",
    "shadow_default",
    "sticky_fold",
    "rough",
    "paper",
    "orientation",
    "units",
    "paper_w",
    "paper_h",
)


class ConfigPalette(BaseModel):
    model_config = ConfigDict(extra="forbid")

    name: str = Field(min_length=1, max_length=60)
    colours: list[str] = Field(min_length=1, max_length=16)

    @field_validator("name")
    @classmethod
    def _plain_name(cls, value: str) -> str:
        return " ".join(value.split())

    @field_validator("colours")
    @classmethod
    def _hex(cls, value: list[str]) -> list[str]:
        for colour in value:
            if not isinstance(colour, str) or not BOARD_BG_COLOR_RE.match(colour):
                raise ValueError("A palette colour is #rrggbb")
        return list(dict.fromkeys(c.lower() for c in value))


class BoardConfig(BaseModel):
    model_config = ConfigDict(extra="forbid")

    format: str
    version: int
    board: dict = Field(default_factory=dict)
    palettes: list[ConfigPalette] = Field(default_factory=list, max_length=MAX_PALETTES)
    shape_libraries_off: list[str] = Field(default_factory=list, max_length=MAX_LIBRARIES)

    @field_validator("format")
    @classmethod
    def _ours(cls, value: str) -> str:
        if value != CONFIG_FORMAT:
            raise ValueError("That is not a Tessellate board configuration file")
        return value

    @field_validator("version")
    @classmethod
    def _known_version(cls, value: int) -> int:
        if value != CONFIG_VERSION:
            raise ValueError(
                f"This configuration is version {value}; this app reads version {CONFIG_VERSION}"
            )
        return value

    @field_validator("board")
    @classmethod
    def _board(cls, value: dict) -> dict:
        unknown = sorted(set(value) - set(BOARD_FIELDS))
        if unknown:
            raise ValueError(
                "The board section has a setting this app does not read: " + ", ".join(unknown[:3])
            )
        try:
            checked = BoardBackground(**value)
        except ValidationError as exc:
            raise ValueError(exc.errors()[0]["msg"]) from exc
        return checked.model_dump(exclude_none=True)

    @field_validator("shape_libraries_off")
    @classmethod
    def _sets(cls, value: list[str]) -> list[str]:
        for key in value:
            if not isinstance(key, str) or not _SET_KEY.match(key):
                raise ValueError("A shape library is named by its set key")
        return list(dict.fromkeys(value))


def _sentence(text: str) -> str:
    """A validator's message as a sentence for a toast: the library's "Value error, " lead off, a full stop on."""
    text = text.removeprefix("Value error, ").strip()
    return text if text.endswith((".", "?")) else text + "."


def check_config(text: str) -> dict:
    """The file's text as a clean configuration, or a 422 that says which part is wrong."""
    if len(text) > MAX_CONFIG_CHARS:
        raise HTTPException(status_code=413, detail="That configuration file is larger than 100 KB, which is more than a configuration needs.")
    try:
        raw = json.loads(text)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail="That file is not a board configuration. Choose one saved by Export board configuration.") from exc
    if not isinstance(raw, dict):
        raise HTTPException(status_code=422, detail="That file is not a board configuration.")
    try:
        config = BoardConfig(**raw)
    except ValidationError as exc:
        raise HTTPException(status_code=422, detail=_sentence(exc.errors()[0]["msg"])) from exc
    return config.model_dump()
