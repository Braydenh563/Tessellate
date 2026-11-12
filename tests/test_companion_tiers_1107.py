"""Research B9: idle escalates in tiers by how long the person has been away (Agent idle levels 1 to 3, sleep
last): look about, then stretch and props, then a nap. Pure: fixed clock, no Win32."""

from __future__ import annotations

from tessellate.core.overlay import behaviour as bh
from tessellate.core.overlay import props as pr

pr.register()


def weight(m: bh.Mind, name: str, idle: float) -> float:
    m.idle = idle
    m.needs.update(rest=0.45, curiosity=0.45, play=0.45, social=0.45, comfort=0.45, hunger=0.45, novelty=0.45)
    return m._weight(name, bh.ACTIVITIES[name], "calm", 12, 1000.0)


def test_the_tier_is_zero_while_they_are_about_then_one_two_three() -> None:
    assert [bh.idle_tier(s) for s in (0.0, 30.0, 61.0, 200.0, 400.0)] == [0, 0, 1, 2, 3]


def test_each_tier_favours_its_own_group_and_sleep_comes_last() -> None:
    m = bh.Mind(0.0)
    # tier 1: a look about outweighs a nap
    assert weight(m, "look_around", 90.0) > 1.5 * weight(m, "look_around", 10.0)
    assert weight(m, "curl_up", 90.0) < weight(m, "curl_up", 500.0) / 2
    # tier 2: props and stretches
    assert weight(m, "stretch", 220.0) > 1.5 * weight(m, "stretch", 10.0)
    # tier 3: the nap is at its heaviest and the look about has had its turn
    assert weight(m, "curl_up", 500.0) > weight(m, "curl_up", 220.0)


def test_nothing_in_a_tier_is_forbidden_so_a_quiet_desk_still_has_variety() -> None:
    m = bh.Mind(0.0)
    for idle in (0.0, 90.0, 220.0, 500.0):
        assert all(weight(m, n, idle) > 0 for n in ("look_around", "stretch", "groom", "doze"))
