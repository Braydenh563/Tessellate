"""The driver both long runners share (WORLD_CLASS_PLAN decision 61).

`run_agent` (agent.py) and `_run_one_step` (skill_runner.py) were each one
loop whose stages were reachable only by running the whole loop. Each is now a
`Step` enum and one function per state: a state function takes the runner's
context, yields its events, and returns the next state, so a stage can be
driven alone in a test with a context built by hand. `drive` is the loop.
"""

from __future__ import annotations

from collections.abc import Callable, Generator, Iterator, Mapping
from enum import Enum
from typing import Any, TypeVar

S = TypeVar("S", bound=Enum)

#: A state function: yields events, returns the next state (or a result,
#: once the state is the table's `end`).
StepFn = Callable[[Any], Generator[dict, None, Any]]


def drive(table: Mapping[S, StepFn], start: S, end: S, context: Any) -> Iterator[dict]:
    """Run `table` from `start` until a state function returns `end`.

    Returns what the context's `result` holds then (None for a runner that
    returns nothing), so a caller can `yield from` it and keep a return value.
    """
    state = start
    while state is not end:
        state = yield from table[state](context)
    return getattr(context, "result", None)
