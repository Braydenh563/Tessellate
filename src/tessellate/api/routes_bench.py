"""`/models/bench`: run the model bench and read its report (I8, H3).

The bench itself is `ai/bench.py`. This is the door: one run at a time, on a
thread of its own (a forty-note run over two models is minutes, not a
request), stoppable, and its last report kept in the data folder so the
table is still there after a restart. "Use this one" is not a route of its
own: it is `POST /models/chat-model`, the same switch the model picker uses,
so the bench cannot apply a model differently from the way a person would.
"""

from __future__ import annotations

import json
import logging
import threading
import time
from datetime import datetime, timezone
from typing import Callable, NamedTuple

import requests
from fastapi import APIRouter, Header, HTTPException, Request
from pydantic import BaseModel, Field

from tessellate.api.this_computer import this_computer_only
from tessellate.ai import bench, facts
from tessellate.core import deps, jobruns, jobs
from tessellate.core.atomic_io import atomic_write_text

logger = logging.getLogger("tessellate.api.bench")

router = APIRouter(prefix="/models/bench", tags=["models"])


class Budget(NamedTuple):
    """One interaction's time budget (WORLD_CLASS_PLAN decision 54).

    `measured_ms` is the browser's p50 on the fixture (`tests/fixtures/
    budget_notebook.py`: 500 notes, a board of 500 objects, a document of
    50,000 words) on the four-core sandbox, and `cap_ms` is 1.5 times it,
    rounded up to 10 ms. The server share is the route that interaction
    waits on, timed the same way against the same notebook. Raising a cap
    needs a new measurement and a reason in the commit; a miss is reported
    with its number, never absorbed by loosening the cap.
    """

    key: str
    label: str
    what: str
    measured_ms: int
    cap_ms: int
    server_path: str = ""
    server_measured_ms: int = 0
    server_cap_ms: int = 0


#: Measured 2026-10-11 (README "Performance"), machine load 7 to 11. A
#: measurement is the slowest p50 of four browser runs (three or four server
#: rounds), so a loaded machine sets the figure rather than a lucky minute.
BUDGETS: tuple[Budget, ...] = (
    Budget("first_paint", "Boot to first paint", "Navigation start to the first contentful paint, cold cache, stored session", 713, 1070, "/", 76, 120),
    Budget("first_interaction", "First interaction", "Navigation start to the Notes tab answering a click with its first row", 4639, 6960),
    Budget("list", "List paint", "Switching to Notes to the first page of rows settled", 139, 210, "/entries?limit=60", 40, 60),
    Budget("search", "Search", "One search request, p50 over three queries", 30, 50, "/search?q=harbour&limit=20", 40, 60),
    Budget("board", "Board open", "Opening a board of 500 objects to every object on the canvas", 108, 170, "/whiteboard/?board_id={board}", 75, 120),
    Budget("document", "Document open", "Opening a document of 50,000 words to resolved", 359, 540, "/documents/{document}", 32, 50),
)
SHARE_RUNS = 5


def time_share(get: Callable[[str], object], path: str, runs: int = SHARE_RUNS) -> float:
    """p50 in milliseconds of `get(path)` after one warm call. `get` is a
    TestClient method in the test and a loopback request in the route, so the
    CI pin and the live reading time the same thing the same way."""
    get(path)  # the first call builds caches a person pays once, in the background
    times = []
    for _ in range(runs):
        began = time.perf_counter()
        answer = get(path)
        times.append((time.perf_counter() - began) * 1000)
        status = getattr(answer, "status_code", 200)
        if status != 200:
            raise RuntimeError(f"{path} answered {status}")
    return sorted(times)[len(times) // 2]


def heavy_ids(session) -> dict[str, int]:  # noqa: ANN001
    """The board with the most objects and the longest document: the two
    items the budget names, found rather than assumed so the live reading
    works on any notebook."""
    from sqlalchemy import func, select

    from tessellate.core.database import WhiteboardObject
    from tessellate.repo import documents

    board = session.execute(
        select(WhiteboardObject.board_id).where(WhiteboardObject.board_id.is_not(None))
        .group_by(WhiteboardObject.board_id).order_by(func.count().desc()).limit(1)
    ).scalar()
    document = documents.largest_id(session)
    return {"board": board or 0, "document": document or 0}


def budget_rows(live: Callable[[str], object] | None = None, ids: dict[str, int] | None = None) -> list[dict]:
    rows = []
    for budget in BUDGETS:
        row = budget._asdict()
        if live and budget.server_path:
            try:
                path = budget.server_path.format(**(ids or {}))
            except KeyError:
                path = ""
            #: A notebook with no board or no document has nothing to time.
            row["live_ms"] = round(time_share(live, path), 1) if path and "=0" not in path and not path.endswith("/0") else None
            row["live_within"] = None if row["live_ms"] is None else row["live_ms"] <= budget.server_cap_ms
        rows.append(row)
    return rows


def loopback(base: str, headers: dict) -> Callable[[str], object]:
    """GET against this server over loopback; a seam so the test can answer
    in-process, where no port is listening."""
    return lambda path: requests.get(base + path, headers=headers, timeout=30)


@router.get("/budgets")
def budgets(request: Request, live: bool = False, x_auth_token: str | None = Header(default=None)) -> dict:
    """The interaction budgets (decision 54). `live=true` also times each
    server share against this notebook, over loopback, so a person can see
    whether their own notebook is inside the numbers the fixture is held to."""
    if not live:
        return {"budgets": budget_rows()}
    #: The timed requests go to 127.0.0.1 carrying the caller's token, so to
    #: the guard they look like this computer: only this computer starts them.
    this_computer_only(request)
    #: This server over loopback, never the Host header's name: the request's
    #: own auth headers ride along, so the address must be this process.
    port = (request.scope.get("server") or ("127.0.0.1", 8000))[1]
    base = f"http://127.0.0.1:{port}"
    headers = {"X-Auth-Token": x_auth_token} if x_auth_token else {}
    session = deps.get_db().session()
    try:
        ids = heavy_ids(session)
    finally:
        session.close()
    return {"budgets": budget_rows(loopback(base, headers), ids), "ids": ids}

OFF = "The model bench is switched off. Turn it on in Settings, What it learned."
BUSY = "A bench is already running. Stop it or wait for it to finish."
NO_MODELS = "Pick at least one installed model to test."
NOT_RUNNING = "The model server isn't running. Start it and try again."


class BenchBody(BaseModel):
    models: list[str] = Field(min_length=1, max_length=8)
    size: int = Field(default=bench.DEFAULT_SIZE, ge=2, le=bench.MAX_SIZE)
    budget_minutes: int = Field(default=bench.DEFAULT_BUDGET_SECONDS // 60, ge=1, le=240)
    #: Run inside the request (tests, and a script that wants the answer).
    wait: bool = False


_lock = threading.Lock()
_state: dict = {"running": False, "progress": None, "started_at": None}
_stop = threading.Event()


def _report_path():  # noqa: ANN202
    return deps.get_config().data_dir / "bench.json"


def _last_report() -> dict | None:
    try:
        return json.loads(_report_path().read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None


def _run(models: list[str], size: int, budget_seconds: float) -> None:
    session = deps.get_db().session()
    try:
        with jobruns.job_run("model-bench", origin="you") as job:
            report = bench.run(
                session, deps.get_ollama(), models, size=size, budget_seconds=budget_seconds,
                stop=_stop, on_progress=lambda p: _state.__setitem__("progress", p),
            )
            report["finished_at"] = datetime.now(timezone.utc).isoformat(timespec="seconds")
            atomic_write_text(_report_path(), json.dumps(report, indent=1))
            best = report.get("recommended")
            job.result = (
                f"benched {len(report['models'])} model{'' if len(report['models']) == 1 else 's'}"
                + (f", best: {best}" if best else "")
                + (f" ({report['stopped']})" if report.get("stopped") else "")
            )
    except Exception:  # noqa: BLE001  # a crashed bench must clear the running flag
        logger.exception("bench: the run failed")
    finally:
        session.close()
        with _lock:
            _state.update(running=False, progress=None)


@router.post("")
def start(body: BenchBody) -> dict:
    config = deps.get_config()
    if not facts.enabled(config, "model_bench"):
        raise HTTPException(status_code=403, detail=OFF)
    provider = deps.get_ollama()
    if not provider.is_running():
        raise HTTPException(status_code=409, detail=NOT_RUNNING)
    from tessellate.api.routes_models import _installed_models, _name_matches

    installed = _installed_models(True)
    models = [m for m in dict.fromkeys(body.models) if _name_matches(m, installed)]
    if not models:
        raise HTTPException(status_code=400, detail=NO_MODELS)
    session = deps.get_db().session()
    try:
        available = len(bench._candidates(session))
    finally:
        session.close()
    if available < bench.MIN_NOTES:
        raise HTTPException(
            status_code=409,
            detail=f"The bench needs at least {bench.MIN_NOTES} filed notes to test on; this notebook has {available}.",
        )
    with _lock:
        if _state["running"]:
            raise HTTPException(status_code=409, detail=BUSY)
        _stop.clear()
        _state.update(running=True, progress=None, started_at=time.time(), models=models)
    args = (models, body.size, body.budget_minutes * 60)
    if body.wait:
        _run(*args)
    else:
        #: On the job pool's model lane, not a thread of its own: the bench
        #: loads the same models a caption or a filing job does, and the lane
        #: is what keeps two of them from loading at once.
        jobs.enqueue("bench", _run, *args, name="model bench")
    return {"started": True, "models": models}


@router.get("")
def state() -> dict:
    with _lock:
        snapshot = dict(_state)
    snapshot["report"] = _last_report()
    snapshot["enabled"] = facts.enabled(deps.get_config(), "model_bench")
    return snapshot


@router.post("/stop")
def stop() -> dict:
    _stop.set()
    return {"stopping": bool(_state["running"])}
