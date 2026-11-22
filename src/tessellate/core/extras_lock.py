"""Each pip extra's hashed lock (L-world-class-691, SECURITY.md T23).

An extra used to install by name within version bounds, so whatever PyPI
served that day, of the extra and of everything it pulled in, went in
unchecked. Each pip extra now ships a lock in `data/extras_locks/<id>.txt`:
every distribution the extra adds, pinned, with the sha256 of every file
PyPI has for it (any platform, Python 3.11 and up), and `pip install
--require-hashes --no-deps` takes nothing else.

**The lock never names a base package.** requirements.txt only ranges the
base (numpy, tokenizers, ...); a pin for one in an extra's lock would move
it under the running app. The base packages the extra relies on are
`# base:` comment lines instead, checked as present before pip starts
(`--no-deps` would otherwise leave the extra without them). The base is
requirements.txt's resolve minus `PACKAGED_EXCLUDES`, the packages the
packaged build leaves out, so a frozen build gets them from the lock.

This module only reads and writes the format; `scripts/extras_lock.py`
regenerates the locks and `core/extras.py` installs from them. It imports
nothing of the app's, so the script can use it without the app's
dependencies."""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from pathlib import Path

LOCKS_DIR = Path(__file__).resolve().parents[1] / "data" / "extras_locks"

#: In requirements.txt but not in the packaged build: fastembed is in both
#: tessellate.spec files' `excludes` (search by meaning is the `semantic`
#: extra there), and the test tools are never imported by the app, so
#: PyInstaller never collects them or what they pull in (`packaging`). Not
#: base, so the locks carry them and their dependencies; a source install,
#: which has them, leaves them alone (`core/extras.py` `_lock_selection`).
PACKAGED_EXCLUDES = ("fastembed", "pytest", "pytest-xdist", "httpx")

_PIN = re.compile(r"^([A-Za-z0-9][A-Za-z0-9._-]*)==([^\s;\\]+)\s*(?:;\s*([^\\]*?))?\s*\\?$")
_BASE = re.compile(r"^# base: (.+)$")
HASH_LINE = re.compile(r"^--hash=sha256:[0-9a-f]{64}$")


def canonical(name: str) -> str:
    """PEP 503's normal form (`Pillow` and `pillow` are one project)."""
    return re.sub(r"[-_.]+", "-", name).lower()


@dataclass
class Entry:
    """One pinned distribution: `name==version ; marker` and its hashes."""

    name: str
    version: str
    marker: str
    hashes: list[str] = field(default_factory=list)

    def text(self) -> str:
        head = f"{self.name}=={self.version}" + (f" ; {self.marker}" if self.marker else "")
        return " \\\n    ".join([head, *self.hashes]) + "\n"


@dataclass
class Lock:
    entries: list[Entry]
    base: list[Entry]
    packages: str = ""


def parse_entries(text: str) -> list[Entry]:
    """The pinned blocks of a `uv pip compile --generate-hashes` output or a
    lock body: a `name==version` line, then its `--hash=` continuations.
    Comment lines (annotations, `# base:`) are skipped."""
    entries: list[Entry] = []
    current: Entry | None = None
    for raw in text.splitlines():
        line = raw.strip()
        if not line or line.startswith("#"):
            continue
        if line.startswith("--hash="):
            if current is None:
                raise ValueError(f"a hash with no requirement: {line}")
            current.hashes.append(line.rstrip("\\").strip())
            continue
        match = _PIN.match(line)
        if not match:
            raise ValueError(f"not a pinned requirement: {line}")
        current = Entry(match.group(1), match.group(2), (match.group(3) or "").strip())
        entries.append(current)
    return entries


def split(compiled: str, base_names: set[str]) -> tuple[list[Entry], list[Entry]]:
    """A compiled closure into (what the extra adds, the base it uses)."""
    entries = parse_entries(compiled)
    new = [e for e in entries if canonical(e.name) not in base_names]
    base = [e for e in entries if canonical(e.name) in base_names]
    return new, base


def render(extra_id: str, packages: tuple[str, ...], new: list[Entry], base: list[Entry]) -> str:
    """The lock file's text: a fixed header, the base lines, then the body."""
    lines = [
        f"# The {extra_id} extra's hashed lock (L-world-class-691, SECURITY.md T23).",
        "# Regenerate with scripts/extras_lock.py (docs/RELEASING.md); never edit by hand.",
        f"# packages: {' '.join(packages)}",
    ]
    lines.extend(
        f"# base: {e.name}=={e.version}" + (f" ; {e.marker}" if e.marker else "")
        for e in sorted(base, key=lambda e: (canonical(e.name), e.marker))
    )
    body = "".join(e.text() for e in sorted(new, key=lambda e: (canonical(e.name), e.marker)))
    return "\n".join(lines) + "\n" + body


def parse(text: str) -> Lock:
    base: list[Entry] = []
    packages = ""
    for line in text.splitlines():
        match = _BASE.match(line)
        if match:
            base.extend(parse_entries(match.group(1)))
        elif line.startswith("# packages: "):
            packages = line[len("# packages: "):]
    return Lock(parse_entries(text), base, packages)


def read(extra_id: str, locks_dir: Path | None = None) -> Lock | None:
    """The shipped lock for `extra_id`, or None when there is none."""
    path = (locks_dir or LOCKS_DIR) / f"{extra_id}.txt"
    try:
        return parse(path.read_text(encoding="utf-8"))
    except OSError:
        return None


def marker_applies(marker: str) -> bool:
    """Whether an environment marker holds for this interpreter. Without
    `packaging` (a source install always has it, through pytest) a marked
    line is taken as not applying: the check then asks for less, never
    for a package this platform does not use."""
    if not marker:
        return True
    try:
        from packaging.markers import Marker
    except ImportError:
        return False
    return Marker(marker).evaluate()
