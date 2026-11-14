"""One skill run, folded into a result, for the harness's tests (audit ARCH-21).

`run_for_test` drives `skill_runner.run_skill` end to end against a model
double and folds its events into a `RunResult`: the seam
`tests/test_harness_verifier.py` and `tests/test_harness_verifier_spec.py`
call. It lived in `ai/skill_runner.py` with its two classes and `_slug`, 130
lines the app shipped and never called.

Not named `test_*.py` on purpose, as `_app_js.py`.
"""

from __future__ import annotations

from tessellate.ai import budget as run_budget, skills, tools
from tessellate.ai.skill_runner import Verification, run_skill
from tessellate.core import deps
from tessellate.entry import manager

#: A skill name as a test or a fixture is likely to write it: `find_loose_ends`
#: for "Find loose ends". Not a general lookup (`skills.find` is that, and it
#: already forgives punctuation and case); this exists so a spec can name a
#: built-in without depending on its exact display wording, which is copy and
#: changes.
def _slug(name: str) -> str:
    return "_".join(str(name or "").lower().split())


class StepRun:
    """One step of a run, as a fact rather than as a stream of events."""

    __slots__ = ("index", "text", "state", "tool_calls", "pages", "truncated")

    def __init__(self, index: int, text: str) -> None:
        self.index = index
        self.text = text
        self.state = "running"
        self.tool_calls = 0
        self.pages = 1
        self.truncated = False


class RunResult:
    """A finished run, folded up: what each step did, what changed, what the
    verifier found, and why it stopped."""

    __slots__ = (
        "skill",
        "steps",
        "changes",
        "state",
        "stopped_at",
        "stopped_by",
        "verification",
        "undo_available",
        "truncated",
        "budget",
        "events",
    )


def run_for_test(
    ollama,
    *,
    skill: str,
    notes: int = 0,
    budget: dict | None = None,
    values: dict | None = None,
    small_model: bool | None = None,
) -> RunResult:
    """Run one skill end to end against a model double, and return the run.

    The seam `tests/test_harness_verifier_spec.py` drives, and the same shape
    `core/events.exercise_for_test` already has in this codebase: a harness
    whose whole job is to be provable needs one call that *is* a run, rather
    than a test that reassembles one out of a hundred events and is therefore
    testing its own reassembly.

    Seeds `notes` notes first, because paging is only a behaviour over a
    notebook large enough to have pages.

    """
    spend = run_budget.RunBudget(**budget) if budget else None
    wanted = _slug(skill)
    with deps.get_db().session() as session:
        for index in range(notes):
            manager.create_entry(
                session, f"note {index}: chase up the invoice", "Work", []
            )
        catalog = skills.catalog(deps.get_config(), set(tools.TOOLS))
        found = next((s for s in catalog if _slug(s["name"]) == wanted), None)
        if found is None:
            raise LookupError(
                f"no skill called {skill!r}; there are "
                + ", ".join(sorted(_slug(s["name"]) for s in catalog))
            )
        run = RunResult()
        run.skill = found["name"]
        run.steps = []
        run.changes = []
        run.state = {}
        run.stopped_at = None
        run.stopped_by = ""
        run.verification = Verification(False, "the run produced no result")
        run.undo_available = False
        run.truncated = False
        run.budget = spend
        run.events = []
        current: StepRun | None = None
        for event in run_skill(
            session,
            found,
            values or {},
            [],
            deps.get_model_manager(),
            ollama,
            budget=spend,
            small_model=small_model,
        ):
            run.events.append(event)
            kind = event.get("type")
            if kind == "step":
                index = event["index"]
                while len(run.steps) <= index:
                    run.steps.append(StepRun(len(run.steps), event.get("text") or ""))
                current = run.steps[index]
                current.text = event.get("text") or current.text
                current.state = event["state"]
                if event["state"] == "paging":
                    current.pages = event.get("page") or current.pages
                if event.get("truncated"):
                    current.truncated = True
            elif kind == "tool" and current is not None:
                current.tool_calls += 1
            elif kind == "verification":
                run.verification = Verification(
                    ok=event["ok"],
                    reason=event["reason"],
                    tool=event["tool"],
                    field=event["field"],
                    expect=event["expect"],
                    got=event["got"],
                    before=event["before"],
                )
            elif kind == "result":
                run.changes = event["changes"]
                run.state = event["state"]
                run.stopped_at = event["stopped_at"]
                run.stopped_by = event["stopped_by"]
                run.undo_available = event["undo_available"]
                run.truncated = event["truncated"]
        return run
