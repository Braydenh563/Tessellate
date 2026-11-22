"""Regenerate every pip extra's hashed lock (L-world-class-691, SECURITY.md T23).

    PYTHONPATH=src .venv/bin/python scripts/extras_lock.py            # every pip extra
    PYTHONPATH=src .venv/bin/python scripts/extras_lock.py voice ocr  # just these

Needs uv on PATH (`pip install uv` into any scratch venv) and PyPI. Each
extra's packages are resolved for every platform and Python 3.11 and up
(`uv pip compile --universal --generate-hashes`) against requirements.txt
and `EXTRA_BOUNDS` as constraints; what the base install already has (the
resolve of requirements.txt minus `PACKAGED_EXCLUDES`) becomes `# base:`
lines, the rest the hashed body, written to
src/tessellate/data/extras_locks/<id>.txt. Run it when a bound in
`EXTRA_BOUNDS` or requirements.txt moves, or to take newer releases; then
`pytest tests/test_extras_lock_691.py` and review the diff like code.
"""

from __future__ import annotations

import shutil
import subprocess  # noqa: S404  # fixed uv arguments, no shell
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from tessellate.core import extras, extras_lock  # noqa: E402

PYTHON_FLOOR = "3.11"


def _compile(requirements: Path, constraints: list[Path], hashes: bool) -> str:
    uv = shutil.which("uv")
    if uv is None:
        raise SystemExit("uv is not on PATH: pip install uv, then run this again.")
    command = [uv, "pip", "compile", "--universal", "--python-version", PYTHON_FLOOR,
               "--no-header", "--no-annotate", "--quiet", str(requirements)]
    if hashes:
        command.insert(3, "--generate-hashes")
    for constraint in constraints:
        command += ["-c", str(constraint)]
    return subprocess.run(command, check=True, capture_output=True, text=True).stdout  # noqa: S603


def base_names(work: Path) -> set[str]:
    """Every distribution the packaged base install holds, by canonical name."""
    excluded = {extras_lock.canonical(n) for n in extras_lock.PACKAGED_EXCLUDES}
    kept = [
        line for line in (ROOT / "requirements.txt").read_text(encoding="utf-8").splitlines()
        if extras_lock.canonical(extras._requirement_name(line.strip())) not in excluded
    ]
    base_in = work / "base.in"
    base_in.write_text("\n".join(kept) + "\n", encoding="utf-8")
    return {extras_lock.canonical(e.name) for e in extras_lock.parse_entries(_compile(base_in, [], False))}


def joint_pins(pip_extras: list[extras.Extra], constraints: Path, work: Path) -> Path:
    """Every pip extra resolved together, as a constraint for each one's own
    lock: two locks pinning one distribution differently would let one
    extra's install move another's (fastembed caps huggingface-hub below 2,
    faster-whisper alone takes 2.x)."""
    wanted = work / "all.in"
    wanted.write_text("\n".join(p for e in pip_extras for p in e.packages) + "\n", encoding="utf-8")
    joint = work / "joint.txt"
    joint.write_text(_compile(wanted, [constraints], False), encoding="utf-8")
    return joint


def lock_one(extra: extras.Extra, base: set[str], constraints: list[Path], work: Path) -> Path:
    wanted = work / f"{extra.id}.in"
    wanted.write_text("\n".join(extra.packages) + "\n", encoding="utf-8")
    new, used = extras_lock.split(_compile(wanted, constraints, True), base)
    out = extras_lock.LOCKS_DIR / f"{extra.id}.txt"
    out.write_text(extras_lock.render(extra.id, extra.packages, new, used), encoding="utf-8")
    return out


def main(argv: list[str]) -> int:
    pip_extras = [e for e in extras.EXTRAS if e.kind == "pip"]
    chosen = [e for e in pip_extras if not argv or e.id in argv]
    extras_lock.LOCKS_DIR.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix="extras-lock-") as tmp:
        work = Path(tmp)
        base = base_names(work)
        constraints = extras._constraints_copy(ROOT / "requirements.txt")
        try:
            joint = joint_pins(pip_extras, constraints, work)
            for extra in chosen:
                out = lock_one(extra, base, [constraints, joint], work)
                print(f"{extra.id}: {len(extras_lock.read(extra.id).entries)} pinned, {out.relative_to(ROOT)}")
        finally:
            constraints.unlink(missing_ok=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
