"""L-chat-226 (CHAT_PLAN section 9 row 5): one unused feature a week, from the
usage counts. The offer names a feature unused for ninety days, at most once
in seven days, never one already offered, and none while the ledger is
younger than the window. Counts only: nothing typed rides in a name."""

from __future__ import annotations

from datetime import date, timedelta

from tessellate.core import clock, usage

TODAY = date(2026, 11, 14)
KNOWN = ["tab:graph", "tab:timeline", "tab:notes", "cmd:new-note", "cmd:open-settings"]


def _old_ledger(data) -> None:
    usage.record(data, ["tab:notes"], today=TODAY - timedelta(days=200))
    usage.record(data, ["tab:notes", "cmd:new-note"], today=TODAY - timedelta(days=3))


def test_no_offer_while_the_ledger_is_younger_than_the_window(tmp_path) -> None:
    usage.record(tmp_path, ["tab:notes"], today=TODAY - timedelta(days=10))
    assert usage.weekly_offer(tmp_path, KNOWN, today=TODAY) is None


def test_an_unused_feature_is_offered_once_a_week(tmp_path) -> None:
    _old_ledger(tmp_path)
    first = usage.weekly_offer(tmp_path, KNOWN, today=TODAY)
    assert first in {"tab:graph", "tab:timeline", "cmd:open-settings"}
    assert usage.weekly_offer(tmp_path, KNOWN, today=TODAY + timedelta(days=3)) is None
    second = usage.weekly_offer(tmp_path, KNOWN, today=TODAY + timedelta(days=7))
    assert second and second != first


def test_every_unused_feature_is_offered_before_one_repeats(tmp_path) -> None:
    _old_ledger(tmp_path)
    seen = [usage.weekly_offer(tmp_path, KNOWN, today=TODAY + timedelta(days=7 * n)) for n in range(4)]
    assert set(seen[:3]) == {"tab:graph", "tab:timeline", "cmd:open-settings"}
    assert seen[3] in seen[:3]  # all offered once, the round starts again


def test_a_feature_used_since_is_not_offered(tmp_path) -> None:
    _old_ledger(tmp_path)
    usage.record(tmp_path, ["tab:graph", "tab:timeline"], today=TODAY)
    assert usage.weekly_offer(tmp_path, KNOWN, today=TODAY) == "cmd:open-settings"


def test_the_route_offers_and_clear_forgets_it(client) -> None:
    from tessellate.core import deps

    data = deps.get_config().data_dir
    usage.record(data, ["tab:notes"], today=clock.today() - timedelta(days=200))
    usage.record(data, ["tab:notes"])
    first = client.get("/usage/offer", params={"known": KNOWN}).json()
    assert first["name"] in {"tab:graph", "tab:timeline", "cmd:new-note", "cmd:open-settings"}
    again = client.get("/usage/offer", params={"known": KNOWN}).json()
    assert again["name"] is None
    client.delete("/usage")
    usage.record(data, ["tab:notes"], today=clock.today() - timedelta(days=200))
    after = client.get("/usage/offer", params={"known": KNOWN}).json()
    assert after["name"] is not None
