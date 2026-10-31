"""The bounded background pool (WORLD_CLASS_PLAN A3, section 4 B2).

The bug these tests pin: every upload used to spawn up to three
`threading.Thread`s of its own, so a folder of 200 pictures was 600 threads
hitting one Ollama and one Tesseract at once. Three properties make that
impossible, and each is measured rather than read off the code:

1. a lane never runs more than its width at once, under load (50 jobs),
2. shutdown returns inside its deadline even with work still queued,
3. a single-width lane runs its jobs in the order they were enqueued.
"""

from __future__ import annotations

import threading
import time

from tessellate.core import jobs


def test_a_lane_never_exceeds_its_width() -> None:
    """50 jobs, a lane 3 wide: the high-water mark is 3, not 50.

    The counter is under its own lock and read at its peak inside the job, so
    this is the number of jobs that were genuinely inside `func` together,
    not an inference from the worker count.
    """
    pool = jobs.Pool({"model": 3}, kind_lanes={"caption": "model"})
    lock = threading.Lock()
    live = 0
    high = 0
    done = threading.Event()
    finished = 0

    def work() -> None:
        nonlocal live, high, finished
        with lock:
            live += 1
            high = max(high, live)
        time.sleep(0.005)
        with lock:
            live -= 1
            finished += 1
            if finished == 50:
                done.set()

    try:
        for _ in range(50):
            pool.enqueue("caption", work)
        assert done.wait(20), f"only {finished} of 50 jobs ran"
    finally:
        pool.shutdown(deadline=2.0)

    assert high <= 3, f"{high} jobs ran at once in a lane 3 wide"
    assert high > 1, "the lane ran everything serially, so the width does nothing"
    assert finished == 50


def test_shutdown_returns_inside_its_deadline_with_jobs_pending() -> None:
    """A queue full of work does not make quitting slow.

    The pool drops what is still queued rather than draining it: the process
    is going away, the work is re-derivable from the upload row, and a
    shutdown that waits for 200 Tesseract passes is the hang the handler
    exists to prevent.
    """
    pool = jobs.Pool({"cpu": 1}, kind_lanes={"ocr": "cpu"})
    started = threading.Event()
    release = threading.Event()
    ran = []

    def slow() -> None:
        started.set()
        release.wait(5)
        ran.append("slow")

    def never() -> None:  # pragma: no cover - the point is that it does not run
        ran.append("never")

    pool.enqueue("ocr", slow)
    assert started.wait(5)
    for _ in range(200):
        pool.enqueue("ocr", never)

    assert pool.queued_count() > 100
    began = time.monotonic()
    clean = pool.shutdown(deadline=0.4)
    elapsed = time.monotonic() - began
    release.set()

    # The in-flight job is still blocked, so this is the honest "not clean"
    # answer: the workers are daemons and die with the process.
    assert clean is False
    assert elapsed < 2.0, f"shutdown took {elapsed:.2f}s against a 0.4s deadline"
    assert "never" not in ran
    assert pool.queued_count() == 0


def test_order_is_preserved_within_a_kind() -> None:
    """The model lane is one worker wide, so its queue is its order."""
    pool = jobs.Pool({"model": 1}, kind_lanes={"caption": "model"})
    seen: list[int] = []
    done = threading.Event()

    def work(index: int) -> None:
        seen.append(index)
        if index == 19:
            done.set()

    try:
        for index in range(20):
            pool.enqueue("caption", work, index)
        assert done.wait(20)
    finally:
        pool.shutdown(deadline=2.0)

    assert seen == list(range(20))


def test_a_failing_job_does_not_kill_its_worker() -> None:
    """One bad job used to be one dead thread; now it is one log line."""
    pool = jobs.Pool({"cpu": 1}, kind_lanes={"ocr": "cpu"})
    done = threading.Event()

    def boom() -> None:
        raise RuntimeError("tesseract is not installed")

    try:
        pool.enqueue("ocr", boom)
        pool.enqueue("ocr", done.set)
        assert done.wait(10), "the worker died with the failing job"
    finally:
        pool.shutdown(deadline=2.0)


def test_pending_rows_are_shaped_like_tasks_rows() -> None:
    """The activity panel draws these, so they carry its keys."""
    pool = jobs.Pool({"model": 1}, kind_lanes={"caption": "model"})
    release = threading.Event()
    try:
        pool.enqueue("caption", release.wait, 5, name="cat.png")
        pool.enqueue("caption", lambda: None, name="dog.png")
        deadline = time.monotonic() + 5
        rows: list[dict] = []
        while time.monotonic() < deadline:
            rows = pool.pending()
            if len(rows) == 2:
                break
            time.sleep(0.01)
        assert len(rows) == 2, rows
        for row in rows:
            assert set(row) >= {"kind", "name", "label", "detail", "progress", "log"}
            assert row["kind"].startswith("job-")
        assert [row["name"] for row in rows] == ["cat.png", "dog.png"]
    finally:
        release.set()
        pool.shutdown(deadline=2.0)


def test_unknown_kinds_land_on_a_real_lane() -> None:
    """A kind nobody mapped must not vanish, and must not start a thread of
    its own either: it goes on the default lane."""
    pool = jobs.Pool({"cpu": 1})
    done = threading.Event()
    try:
        pool.enqueue("something-new", done.set)
        assert done.wait(10)
    finally:
        pool.shutdown(deadline=2.0)


def test_the_default_pool_maps_every_kind_it_names() -> None:
    """Every kind the call sites use has a lane, and the model lane is one
    wide: more than one concurrent call into a local model is slower than
    one, not faster."""
    for kind in ("ocr", "document", "caption", "vision", "vision-pdf", "file-entry"):
        assert kind in jobs.KIND_LANES, kind
        assert jobs.KIND_LANES[kind] in jobs.LANE_WIDTHS
    assert jobs.LANE_WIDTHS["model"] == 1
    assert jobs.LANE_WIDTHS["cpu"] >= 1
    for kind in ("caption", "vision", "vision-pdf", "file-entry"):
        assert jobs.KIND_LANES[kind] == "model"
    for kind in ("ocr", "document"):
        assert jobs.KIND_LANES[kind] == "cpu"


def test_every_in_background_helper_enqueues_rather_than_spawning() -> None:
    """The regression guard for the finding itself: these six helpers are the
    ones a bulk upload multiplies, and none of them may own a thread."""
    import inspect

    from tessellate.ai import captioning, docreader, vision_ocr
    from tessellate.core import ocr

    helpers = [
        ocr.extract_in_background,
        captioning.caption_in_background,
        vision_ocr.vision_ocr_in_background,
        vision_ocr.pdf_vision_ocr_in_background,
        docreader.read_in_background,
    ]
    for helper in helpers:
        source = inspect.getsource(helper)
        assert "Thread(" not in source, f"{helper.__name__} still spawns a thread"
        assert "enqueue(" in source, f"{helper.__name__} does not enqueue"


def test_a_dedupe_key_keeps_one_job_per_thing_in_flight() -> None:
    """Owner: "like 4 agent processes started ... the vision captioning and
    ocr should only happen each once". Two commits of one picture before the
    first job has stored anything must not queue two jobs."""
    pool = jobs.Pool({"model": 1}, kind_lanes={"caption": "model"})
    gate = threading.Event()
    ran = []

    def work(tag: str) -> None:
        gate.wait(2)
        ran.append(tag)

    first = pool.enqueue("caption", work, "a", dedupe_key=("caption", 7))
    second = pool.enqueue("caption", work, "b", dedupe_key=("caption", 7))
    other = pool.enqueue("caption", work, "c", dedupe_key=("caption", 8))
    assert second == first
    assert other != first
    gate.set()
    deadline = time.monotonic() + 3
    while len(ran) < 2 and time.monotonic() < deadline:
        time.sleep(0.01)
    time.sleep(0.05)
    assert sorted(ran) == ["a", "c"]
    # Once it has finished, the same key may run again (a forced re-read).
    third = pool.enqueue("caption", work, "d", dedupe_key=("caption", 7))
    assert third not in (first, other)
    pool.shutdown()


def test_loading_the_search_model_never_holds_the_model_lane():
    """The search warm-up is a model load, minutes on a first launch, and the
    model lane is one wide: on it, the first note's filing waited behind the
    load (E2E first-run, 2026-10-06, reproduced with a 40 s stand-in load).
    Filing, embedding and captions stay on `model`; the warm-up does not."""
    assert jobs.KIND_LANES["warm"] != "model"
    assert jobs.KIND_LANES["file-entry"] == "model"
    assert jobs.KIND_LANES["warm"] in jobs.LANE_WIDTHS


def test_a_hold_waits_for_the_running_job_and_starts_no_other() -> None:
    """Audit 1028 K19: a restore disposed the engine and swapped the database
    file with a background job still writing. `held()` lets the running job
    finish, starts nothing new until it ends, and then runs what queued."""
    pool = jobs.Pool({"default": 1}, kind_lanes={"tidy": "default"})
    started: list[str] = []
    release = threading.Event()

    def first() -> None:
        started.append("first")
        release.wait(5)

    try:
        pool.enqueue("tidy", first)
        deadline = time.monotonic() + 5
        while pool.running_count() == 0 and time.monotonic() < deadline:
            time.sleep(0.01)
        with pool.held(deadline=0.2) as idle:
            assert idle is False, "the job is still running: the hold says so"
        threading.Timer(0.1, release.set).start()
        with pool.held(deadline=5) as idle:
            assert idle is True
            pool.enqueue("tidy", lambda: started.append("second"))
            time.sleep(0.3)
            assert started == ["first"], "nothing starts while held"
            assert pool.queued_count() == 1
        deadline = time.monotonic() + 5
        while len(started) < 2 and time.monotonic() < deadline:
            time.sleep(0.01)
        assert started == ["first", "second"]
    finally:
        release.set()
        pool.shutdown(deadline=2.0)
