"""The prose metric re-run (L-world-class-64): a line the app prints in a
panel is at most 120 characters, and the longer words sit in a tooltip or a
`data-help-for` popover.

Measured 2026-11-14 at 1440x900 over the seven tabs and every Settings
section (own text nodes over 120 characters, outside popovers): 0 on the
tabs, 9 in Settings; 5 fixed here; the rest are a built-in persona's own
prompt (data, not help) and a path-length-dependent status line.
"""
from pathlib import Path

from tessellate.core.embedmodels import EMBED_MODELS, OLLAMA_EMBED_MODELS

ROOT = Path(__file__).resolve().parents[1]
STATUS = (ROOT / "frontend" / "js" / "status.js").read_text(encoding="utf-8")
SKILLS = (ROOT / "src" / "tessellate" / "ai" / "skills.py").read_text(encoding="utf-8")
EMBEDDINGS = (ROOT / "src" / "tessellate" / "ai" / "embeddings.py").read_text(encoding="utf-8")


def test_a_model_reason_is_one_line():
    for model in (*EMBED_MODELS, *OLLAMA_EMBED_MODELS):
        reason = getattr(model, "why_not", "") or ""
        assert len(reason) <= 120, (model, len(reason))


def test_the_not_installed_line_is_one_sentence_and_the_alternative_is_a_tooltip():
    line = "Search by meaning is not installed yet; search uses keywords until you allow the download in Settings, Search and index."
    assert len(line) <= 120 and line in EMBEDDINGS
    assert "embeddingError.title =" in STATUS


def test_the_composer_note_is_a_tooltip_not_a_second_sentence():
    assert 'ollamaLine.title = "Until a model is connected' in STATUS


def test_a_built_in_skill_description_is_one_line():
    start = SKILLS.index("Interviews you about a job you do often")
    assert len(SKILLS[start : SKILLS.index('"', start)]) <= 120
