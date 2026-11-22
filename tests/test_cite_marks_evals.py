"""L-chat-59 on the real model: does it write the brief's `[Sn]` ids back?

Same seam as `test_skills_evals.py` (TESSELLATE_EVALS_URL and
TESSELLATE_EVALS_MODEL); without them this is skipped. Measured 2026-11-14 on
qwen2.5 1.5B over the showcase eval's twelve marked prompts: 10 of 12 answers
cite an id that grounds an answer sentence (0 of 12 when the ask sat above the
notes rather than after the question).
"""

from __future__ import annotations

import json
import os
import urllib.request

import pytest

from tessellate.ai import cite_marks, librarian
from tests import _composer_eval as ev

EVALS_URL = os.environ.get("TESSELLATE_EVALS_URL", "").strip().rstrip("/")
EVALS_MODEL = os.environ.get("TESSELLATE_EVALS_MODEL", "").strip()

pytestmark = [
    pytest.mark.evals,
    pytest.mark.skipif(not (EVALS_URL and EVALS_MODEL), reason="no real model: export TESSELLATE_EVALS_URL and TESSELLATE_EVALS_MODEL"),
]


def _answer(messages: list[dict]) -> str:
    body = json.dumps(
        {"model": EVALS_MODEL, "messages": [{"role": m["role"], "content": m["content"]} for m in messages], "temperature": 0, "max_tokens": 200}
    ).encode()
    request = urllib.request.Request(f"{EVALS_URL}/chat/completions", body, {"Content-Type": "application/json"})
    with urllib.request.urlopen(request, timeout=180) as response:  # noqa: S310  # the developer's own local server
        return json.load(response)["choices"][0]["message"]["content"]


def test_the_model_cites_the_brief_by_id():
    rows = [r for r in ev.context_rows() if r["brief"] and r["brief"]["marks"]]
    assert len(rows) == 12
    grounded = 0
    for row in rows:
        scrubber = cite_marks.MarkScrubber(row["brief"]["marks"])
        text = scrubber.feed(_answer(librarian.build_messages(row["question"], row["brief"]["notes"]))) + scrubber.flush()
        assert "[S" not in text
        grounded += bool(cite_marks.rows(text, scrubber))
    assert grounded >= 8, grounded
