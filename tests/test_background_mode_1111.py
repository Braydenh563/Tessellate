"""B72 / CHAT_PLAN 1691: a background call to the utility model does not think.

Measured on Qwen3-0.6B (B72, 2026-11-11, seed 7): four short utility jobs
(tags, entities, title, one sentence) spent 925 tokens in the default mode and
56 with thinking off, 16 times fewer. Ollama honours `think: false`
(`OllamaClient.request_extras`); this pins that every short background job asks
for it, and that the preset is not on the picker.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from tessellate.ai import presets

AI = Path(__file__).resolve().parents[1] / "src" / "tessellate" / "ai"

#: How many short-output utility-model calls each file makes in the preset.
#: `drafter.py`'s second call writes the whole draft, `meeting_summary.py`
#: writes a summary: both keep the mode they had.
SITES = {
    "captioning.py": 1,
    "drafter.py": 1,
    "entities.py": 1,
    "passive_capture.py": 1,
    "reminder_parser.py": 1,
    "skill_runner.py": 1,
    "speakers.py": 1,
    "tensions.py": 1,
}


def test_the_background_preset_turns_thinking_off_and_keeps_the_normal_cap():
    mode = presets.resolve(presets.BACKGROUND_MODE)
    assert mode.id == presets.BACKGROUND_MODE
    assert mode.think is False
    assert mode.max_output_tokens == presets.MODES["normal"].max_output_tokens
    assert mode.temperature is None
    assert mode.length_hint == ""


def test_the_background_preset_is_not_on_the_picker():
    assert presets.BACKGROUND_MODE not in presets.MODES


@pytest.mark.parametrize("name, count", sorted(SITES.items()))
def test_every_short_background_call_asks_for_the_background_preset(name, count):
    source = (AI / name).read_text()
    assert source.count("mode=presets.BACKGROUND_MODE") == count, name
    assert "from tessellate.ai import presets" in source or "import presets" in source, name
