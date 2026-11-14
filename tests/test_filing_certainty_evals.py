"""L214: the certainty a small model's filing shows, against how often it is right.

Needs a real model (`pytest -m evals`, TESSELLATE_EVALS_URL and _MODEL). Thirty held-out notes
from `tests/fixtures/filing/notes_c.json` are filed against a notebook seeded with the other
thirty-odd. Measured 2026-11-14 on qwen2.5-1.5b-instruct Q4_K_M: hit rate 17 of 30, the largest
shown number 84, filings shown at 70 to 89 right 13 of 17 (76%, mean shown about 80).
"""

from __future__ import annotations

import json
import os
from collections import defaultdict
from pathlib import Path

import pytest

URL = os.environ.get("TESSELLATE_EVALS_URL", "").strip()
MODEL = os.environ.get("TESSELLATE_EVALS_MODEL", "").strip()
pytestmark = pytest.mark.skipif(not (URL and MODEL), reason="no real model: export TESSELLATE_EVALS_URL and _MODEL")
NOTES = json.loads((Path(__file__).parent / "fixtures" / "filing" / "notes_c.json").read_text(encoding="utf-8"))
#: How far the mean shown number of the filings the model made may sit above the share it got right.
MAX_OVERCLAIM = 20


@pytest.mark.evals
def test_a_small_models_shown_certainty_never_reads_100_and_tracks_its_hit_rate(app_state, fake_embeddings):
    from tessellate.ai import janitor, lexical_filing
    from tessellate.ai.openai_client import OpenAICompatClient
    from tessellate.core import deps
    from tessellate.entry import manager

    client = OpenAICompatClient(base_url=URL)
    deps.override_ai(ollama=client)
    config = deps.get_config()
    config.set_preference("llm_provider", "openai")
    config.set_preference("llm_base_url", URL)
    config.set_preference("chat_model", MODEL)
    per = defaultdict(list)
    for note in NOTES:
        per[note["category"]].append(note)
    cats = sorted(per)
    held = [n for c in cats for n in per[c][3:]] + [per[c][2] for c in cats[:6]]
    seeded = [n for c in cats for n in per[c][:3] if n not in held]
    rows = []
    with deps.get_db().session() as session:
        lexical_filing.forget_corpus()
        for note in seeded:
            manager.create_entry(session, note["content"], category_name=note["category"], tags=[])
        session.commit()
        for note in held:
            cat, shown, method = janitor.categorise(
                session, note["content"], deps.get_embeddings(), deps.get_model_manager(), client
            )
            rows.append((note["category"].lower() == cat.lower(), shown, method))
    filed = [r for r in rows if r[2] == "llm"]
    assert filed, "the model filed nothing"
    assert max(r[1] for r in rows) < 100
    hit_rate = 100 * sum(r[0] for r in filed) / len(filed)
    mean_shown = sum(r[1] for r in filed) / len(filed)
    assert mean_shown - hit_rate <= MAX_OVERCLAIM, f"shown {mean_shown:.0f}% for a {hit_rate:.0f}% hit rate"
