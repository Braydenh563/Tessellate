"""L-general-25: the misspelling pairs taken from Wikipedia carry their
source and licence in their own file, credited in THIRD_PARTY.md, and ship."""

import json
from pathlib import Path

from tessellate.ai import question_noise

ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "src" / "tessellate" / "ai" / "data" / "common_misspellings.json"


def test_the_wikipedia_pairs_name_their_source_and_licence():
    table = json.loads(DATA.read_text(encoding="utf-8"))
    assert "Lists_of_common_misspellings" in table["source"]
    assert table["licence"].startswith("CC BY-SA 4.0")
    assert len(table["pairs"]) == 3892
    credit = (ROOT / "docs" / "THIRD_PARTY.md").read_text(encoding="utf-8")
    assert "ai/data/common_misspellings.json" in credit and "CC BY-SA 4.0" in credit


def test_the_pairs_still_repair_and_ship_in_the_wheel():
    assert question_noise.SLANG["abandonned"] == "abandoned"
    assert question_noise.SLANG["broski"] == "brother"
    assert "data/common_misspellings.json" in (ROOT / "pyproject.toml").read_text(encoding="utf-8")


def test_every_frozen_build_carries_the_whole_ai_data_folder():
    """The specs named only data/taxonomy, so the study glossary and skill
    rates were missing from the frozen app; the misspellings load at import."""
    for spec in ("linux", "windows"):
        text = (ROOT / "packaging" / spec / "tessellate.spec").read_text(encoding="utf-8")
        assert '"ai" / "data"), "tessellate/ai/data")' in text, spec
