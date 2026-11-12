"""The desk panel's fit() asks the window size with set_size(width, height, state); a rename in 62101c34 sent it to
set_figure_size(name), which takes one argument, so pywebview raised "takes 2 positional arguments but 4 were
given" on the owner's machine (2026-11-07 log) and the panel never fitted its content."""

from __future__ import annotations

import inspect
import re
from pathlib import Path

from tessellate.core.desk_companion import DeskApi

JS = (Path(__file__).resolve().parent.parent / "frontend" / "js" / "desk-companion.js").read_text(encoding="utf-8")


def _arity(name: str) -> int:
    return len(inspect.signature(getattr(DeskApi, name)).parameters) - 1  # without self


def test_fit_asks_set_size_with_width_height_state() -> None:
    body = JS[JS.index("function fit()"):]
    body = body[: body.index("\n  }\n")]
    assert 'ask("set_size", SIZES[state][0], height, state)' in body


def test_every_ask_passes_no_more_arguments_than_the_api_takes() -> None:
    for name, args in re.findall(r'ask\("([a-z_]+)"((?:, [^;]*?)?)\)\)*;?', JS):
        if not hasattr(DeskApi, name):
            continue
        given = len([a for a in re.split(r",(?![^(\[]*[)\]])", args) if a.strip()])
        assert given <= _arity(name), (name, given, _arity(name))
