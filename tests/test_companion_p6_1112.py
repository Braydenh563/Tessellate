"""P6 (Brief 34 second part, INBOX 752): a reaction budget per minute for the in-app companion, on top of each row's cool-down
and the six-second gap. Node vm with a fixed clock; the harness is the one the Brief 88 reaction tests use."""

from __future__ import annotations

import re
import shutil

import pytest
from tests.test_companion_npc_1581 import AV, REACT_HARNESS, _fn, _node

needs_node = pytest.mark.skipif(not shutil.which("node"), reason="needs node")


def _src() -> str:
    table = re.search(r"^const NMB_REACTIONS = \{.*?^\};", AV, re.S | re.M).group(0)
    consts = "\n".join(re.search(rf"^const {n} = .*$", AV, re.M).group(0) for n in ("NMB_REACT_GAP", "NMB_REACT_BUDGET", "NMB_REACT_WINDOW_MS"))
    return "\n".join([table, consts, _fn(AV, "nameMarkBuddyReact")])


@needs_node
def test_at_most_four_reactions_in_a_minute_and_the_window_slides() -> None:
    out = _node(REACT_HARNESS + r"""
fresh();
const kinds = ["nothing", "whoosh", "carried", "binned", "found", "private", "graph"];
ctx.nmb.missAt = NOW;
const played = [];
// One reaction every 7 s (past the 6 s gap), seven different kinds: only the first four play in the minute.
for (const k of kinds) { played.push(react(k)); NOW += 7000; }
const afterMinute = NOW;
// 49 s after the first, still inside its minute: refused. Past 60 s from the first, one slot is free again.
NOW = afterMinute + 12000;
const later = react("graph");
out({ played, later, log: ctx.nmb.reactLog.length });
""", _src())
    assert out["played"][:4] == [True, True, True, True]
    assert out["played"][4:] == [False, False, False]  # the fifth to seventh in the same minute wait
    assert out["later"] is True  # the first has left the window
    assert out["log"] <= 4


@needs_node
def test_a_refused_reaction_does_not_spend_its_cool_down() -> None:
    out = _node(REACT_HARNESS + r"""
fresh();
for (const k of ["nothing", "whoosh", "carried", "binned"]) { react(k); NOW += 7000; }
const refused = react("nothing");
NOW += 40000;
const again = react("nothing");
out({ refused, again });
""", _src())
    assert out["refused"] is False and out["again"] is True


def test_the_budget_is_four_in_sixty_seconds() -> None:
    assert re.search(r"^const NMB_REACT_BUDGET = 4;$", AV, re.M) and re.search(r"^const NMB_REACT_WINDOW_MS = 60000;$", AV, re.M)
    assert "nmb.reactLog.length >= NMB_REACT_BUDGET" in _fn(AV, "nameMarkBuddyReact")
