"""CI runs the Python tests in parallel legs by test file (OPEN W24, CI time 1109): the legs together are the whole suite,
the split does not move between runs, and the ratchets stay in one leg."""

from __future__ import annotations

import re
from pathlib import Path

import pytest

from tests import _shard

TESTS = Path(__file__).resolve().parent
ROOT = TESTS.parent


def _counts() -> dict[str, int]:
    return {p.name: max(1, len(re.findall(r"^\s*(?:async\s+)?def test_", p.read_text(encoding="utf-8"), re.M))) for p in TESTS.glob("test_*.py")}


@pytest.mark.parametrize("count", [1, 2, 3])
def test_every_file_is_in_exactly_one_leg_and_the_split_is_stable(count: int) -> None:
    counts = _counts()
    first = _shard.assign(counts, count)
    assert set(first) == set(counts)
    assert set(first.values()) <= set(range(count))
    assert first == _shard.assign(dict(reversed(list(counts.items()))), count)


def test_the_ratchets_and_budgets_stay_together_in_the_first_leg() -> None:
    legs = _shard.assign(_counts(), 3)
    held = [name for name in legs if _shard.together(name)]
    assert "test_global_scope_ratchet.py" in held and "test_budgets.py" in held
    assert {legs[name] for name in held} == {0}


def test_two_legs_are_within_a_fifth_of_each_other_by_estimated_seconds() -> None:
    counts = _counts()
    legs = _shard.assign(counts, 2)
    load = [0.0, 0.0]
    for name, n in counts.items():
        load[legs[name]] += _shard.WEIGHTS.get(name, _shard.DEFAULT_PER_TEST * n)
    assert max(load) <= 1.2 * min(load), load


class _Item:
    def __init__(self, path: str) -> None:
        self.path = Path(path)


def test_split_keeps_each_item_in_one_leg_and_a_bad_spec_is_refused() -> None:
    items = [_Item(f"tests/test_{c}.py") for c in "abcdefg" for _ in range(3)]
    kept = [_shard.split(items, f"{i}/3")[0] for i in (1, 2, 3)]
    assert sorted(id(x) for part in kept for x in part) == sorted(id(x) for x in items)
    assert all(len({x.path for x in part} & {x.path for other in kept if other is not part for x in other}) == 0 for part in kept)
    for bad in ("0/2", "3/2", "x", "1-2"):
        with pytest.raises(ValueError):
            _shard.split(items, bad)


def test_the_ci_workflow_runs_every_leg_with_a_matching_count() -> None:
    text = (ROOT / ".github" / "workflows" / "ci.yml").read_text(encoding="utf-8")
    legs = re.search(r"shard:\s*\[([\d, ]+)\]", text)
    assert legs, "the test job has no shard matrix"
    numbers = [int(n) for n in legs.group(1).split(",")]
    assert numbers == list(range(1, len(numbers) + 1))
    assert f"--shard ${{{{ matrix.shard }}}}/{len(numbers)}" in text
