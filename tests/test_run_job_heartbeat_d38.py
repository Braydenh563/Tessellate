"""D38 (audit 1028): the run-job heartbeat is armed after an await; a run's job
ended in between (the panel closed while still running) must not start a
beat that outlives it. The arm checks a generation, not only the run's state."""

from __future__ import annotations

import shutil
import subprocess
from pathlib import Path

import pytest

SRC = (Path(__file__).resolve().parents[1] / "frontend/js/documents-code.js").read_text(encoding="utf-8")

HARNESS = r"""
const fs = require("fs");
const src = fs.readFileSync(process.argv[2], "utf8");
const grab = (name) => { const s = src.indexOf(`function ${name}(`); return src.slice(s, src.indexOf("\n}\n", s) + 3); };
const calls = [], intervals = [];
let release;
const post = new Promise((r) => { release = r; });
globalThis.apiJson = (path, o) => { calls.push(`${o.method} ${path}`); return path.endsWith("/run-jobs") ? post : Promise.resolve({}); };
globalThis.recordBrowserLog = () => {};
globalThis.currentDoc = { title: "t" };
globalThis.DOC_RUN_JOB_AFTER_MS = 0; globalThis.DOC_RUN_JOB_BEAT_MS = 5;
const realSetInterval = setInterval;
globalThis.setInterval = (...a) => { intervals.push(1); return realSetInterval(...a); };
eval(grab("docRunJobCall") + grab("docRunJobArm") + grab("docRunJobEnd") + "globalThis.arm = docRunJobArm; globalThis.end = docRunJobEnd;");
globalThis.docRun = { id: 7, running: true, job: null, jobWait: null, jobBeat: null };
const run = docRun;
arm(7);
setTimeout(async () => {
  end(run);                 // the panel closed while the run was still going
  release({ id: "job-1" });
  await new Promise((r) => setTimeout(r, 40));
  console.log(JSON.stringify({ intervals: intervals.length, job: run.job, calls }));
  process.exit(0);
}, 20);
"""


@pytest.mark.skipif(not shutil.which("node"), reason="needs node")
def test_a_job_ended_while_its_row_was_being_made_starts_no_heartbeat(tmp_path):
    script = tmp_path / "h.js"
    script.write_text(HARNESS, encoding="utf-8")
    done = subprocess.run(["node", str(script), str(Path(__file__).resolve().parents[1] / "frontend/js/documents-code.js")], capture_output=True, text=True, check=True, timeout=60)
    import json

    out = json.loads(done.stdout.strip().splitlines()[-1])
    assert out["intervals"] == 0, out
    assert out["job"] is None, out
    assert "DELETE /documents/run-jobs/job-1" in out["calls"], out


def test_the_arm_checks_the_generation_after_each_await():
    start = SRC.index("function docRunJobArm(")
    body = SRC[start : SRC.index("\n}\n", start)]
    assert body.count("jobSeq") >= 1 and "jobSeq" in SRC[SRC.index("function docRunJobEnd("):]
