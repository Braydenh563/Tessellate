"""L-world-class-185: the backend and AI streamlining list, each item measured.

Measured 2026-11-22 on the fake OpenAI server (scratchpad/fake_openai_server.py),
four chat turns warm: `toolwords._compile` rebuilt every cue pattern on every
`score_groups` call, 64 compiles and 108 ms of the turns' 458 ms. The patterns
are a function of a constant table, so they are built once per table.
"""

from __future__ import annotations

import re

from tessellate.ai import toolwords


def test_cue_patterns_are_compiled_once_per_table(monkeypatch):
    groups = [(("tag_note",), ("tag", "add a tag")), (("pin_note",), ("pin",))]
    toolwords.score_groups("tag this note", groups)
    built = []
    real = re.compile
    monkeypatch.setattr(toolwords.re, "compile", lambda *a, **k: built.append(a) or real(*a, **k))
    for _ in range(3):
        ranked, fired = toolwords.score_groups("tag this note and pin it", groups)
    assert built == []
    assert fired == ["tag", "pin"]
