"""Rename the product to Tessellate (formerly MemoryMap AI), idempotently.

    python scripts/rebrand.py            # rewrite, print what changed
    python scripts/rebrand.py --check    # print what would change, exit 1 if any
    python scripts/rebrand.py --repo-url Braydenh563/Tessellate

The owner, 2026-10-11 (INBOX 903): "alright lets rename and retrademark to
Tessellate update absolutely everything including all the documentation and
the pages site. make sure to still note the former name though."

Other branches keep landing text written before the rename, so this runs
again after every merge and must change nothing the second time.
`tests/test_brand_name.py` runs `pending()` and fails on anything left.

What it changes: the product name "MemoryMap AI" or "MemoryMap" as a word in
copy, titles, prompts, help, docs and the Pages site; the GitHub repo and
Pages URLs (to `--repo-url`, the renamed repo by default).

What it keeps, by rule rather than by list where it can:
- a name glued to a path, an extension or an identifier (`dist/MemoryMap AI`,
  `MemoryMap AI.exe`, `restartMemoryMap`, `X-MemoryMap-Agent`,
  `MemoryMap-AI-Setup-`): files, folders and wire names that installed copies
  still look for; the internal identifiers move separately, with fallbacks;
- "formerly MemoryMap ..." mentions;
- in the roadmap docs and CLAUDE.md, anything in double quotes
  (the owner's words are quoted there);
- a line carrying `brand: keep`, or the line after one carrying
  `brand: keep-next` (a data folder, a certificate subject, a stored value);
- whole files that are records: past CHANGELOG entries, HISTORY, archived
  ledgers, the owner's typo fixtures, running agents' ledgers;
- icons and logos (a separate logo pass follows once the owner picks a mark).
"""

from __future__ import annotations

import argparse
import re
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
NEW = "Tessellate"
OLD_REPO = "Braydenh563/MemoryMap-AI"
DEFAULT_REPO = "Braydenh563/Tessellate"

SKIP_FILES = {
    "CHANGELOG.md",
    "docs/CHANGELOG.md",
    "docs/roadmap/HISTORY.md",
    "scripts/rebrand.py",
    "tests/test_brand_name.py",
    "tests/fixtures/owner_typos.json",
    # name the old identifiers on purpose: the fallbacks and their tests
    "src/tessellate/core/envnames.py",
    "tests/test_rebrand_compat.py",
}
SKIP_PREFIXES = (
    "docs/roadmap/archive/",
    "docs/roadmap/agent-remaining/",
    "frontend/vendor/",
    "frontend/board-library/",
    "scratchpad/",
)
#: Where the owner's words are quoted inline: quoted spans stay as written.
QUOTE_KEPT = ("docs/roadmap/", "CLAUDE.md")
TEXT_SUFFIXES = {
    ".md", ".html", ".js", ".mjs", ".css", ".py", ".sh", ".bat", ".cmd", ".ps1",
    ".iss", ".wxs", ".spec", ".yml", ".yaml", ".toml", ".txt", ".desktop",
    ".plist", ".xml", ".webmanifest", ".ini", ".cfg", ".in", ".json", ".j2",
}
TEXT_NAMES = {"Makefile", "Dockerfile", "README", "LICENSE", ".env.example", ".gitignore", ".gitattributes", ".dockerignore"}

NAME = re.compile(r"MemoryMap(?:(?: |&nbsp;|\u00a0|\n *(?:[#;*/-]+ *)?)AI\b)?")
ESCAPED = re.compile(r"(?:\\[nt]|\[[0-9;]*m)$")
QUOTED = re.compile(r"\"[^\"\n]{0,1200}(?:\n[^\"\n]{0,1200}){0,12}\"|“[^”]{0,4000}”")


# ---- step 2: internal identifiers (`--identifiers`) ----------------------
#: Module paths and logger names: `memorymap.<module>` for the package's own
#: top-level modules, `from/import memorymap`, `-m memorymap`, `src/memorymap`.
#: Not: `memorymap.db` (the old database name, renamed once at start), `memorymap.spec`
#: (the PyInstaller spec files), `memorymap.local` (a host name),
#: `memorymap.desktop.app.1` (the Windows taskbar id pinned shortcuts carry),
#: `memorymap.ocr.*` (browser keys, read once and removed by library.js), file formats
#: (`memorymap-board`, `memorymap-library-set`, `memorymap-clip`).
PACKAGE_PARTS = ("ai", "api", "core", "entry", "search", "vendor", "__main__",
                 "__init__", "__version__", "mcp_server", "SUPPORT_EMAIL")
LOGGERS = ("chat", "tools", "startup", "agent", "embeddings", "searxng", "whiteboard", "import",
           "extras", "entries", "jobstore", "config", "voice", "skills", "launcher", "errors",
           "captions", "templates", "meetings", "lexical_filing", "update", "tasks")
IDENT_RULES = [
    (re.compile(r"(?<![\w.-])memorymap(?=\.(?:" + "|".join(PACKAGE_PARTS) + r")\b)"), "tessellate"),
    (re.compile(r"\b(from|import)(\s+)memorymap\b(?![-.]\w*(?:db|spec)\b)"), r"\1\2tessellate"),
    (re.compile(r"(-m\s+)memorymap\b(?![.-])"), r"\1tessellate"),
    (re.compile(r"(-m\s+)memorymap(?=\.)"), r"\1tessellate"),
    (re.compile(r"\bsrc([/\\]+)memorymap\b"), r"src\1tessellate"),
    (re.compile(r"getLogger\((['\"])memorymap(?=[.'\"])"), r"getLogger(\1tessellate"),
    (re.compile(r"(?<![\w])MEMORYMAP_(?=[A-Z0-9])"), "TESSELLATE_"),
    # a path join onto the package folder: `ROOT / "src" / "memorymap"`
    (re.compile(r"(/\s*)([\"'])memorymap\2"), r"\1\2tessellate\2"),
    # `[sys.executable, "-m", "memorymap"]`, `prog="memorymap"`, `PACKAGE = "memorymap"`
    (re.compile(r"([\"']-m[\"'],\s*[\"'])memorymap(?=[\"'])"), r"\1tessellate"),
    (re.compile(r"\b(prog|PACKAGE)(\s*=\s*[\"'])memorymap(?=[\"'])"), r"\1\2tessellate"),
    # logger names the package gives itself (`getLogger("memorymap.chat")`), where a test names them
    (re.compile(r"([\"'])memorymap(?=\.(?:" + "|".join(LOGGERS) + r")\1)"), r"\1tessellate"),
]

#: Kept whole by the identifier pass: the old package name's own shim.
IDENT_SKIP = {"src/memorymap/__init__.py", "src/memorymap/__main__.py"}
CODE_SUFFIXES = {".py", ".js", ".mjs", ".sh", ".bat", ".cmd", ".ps1", ".yml", ".yaml", ".toml", ".ini", ".cfg", ".spec", ".iss", ".wxs"}


def ident_text(text: str, quotes_kept: bool) -> tuple[str, int]:
    """The internal names: the package, its loggers, the environment."""
    spans = _protected_spans(text, quotes_kept)
    count = 0
    for pattern, repl in IDENT_RULES:
        def sub(m: re.Match) -> str:
            nonlocal count
            if any(a <= m.start() < b for a, b in spans):
                return m.group(0)
            count += 1
            return m.expand(repl)
        text = pattern.sub(sub, text)
    return text, count


def _protected_spans(text: str, quotes_kept: bool) -> list[tuple[int, int]]:
    spans: list[tuple[int, int]] = []
    if quotes_kept:
        spans += [m.span() for m in QUOTED.finditer(text)]
    lines = text.splitlines(keepends=True)
    pos, keep_next = 0, False
    for line in lines:
        if keep_next or "brand: keep" in line and "brand: keep-next" not in line:
            spans.append((pos, pos + len(line)))
        keep_next = "brand: keep-next" in line
        pos += len(line)
    return spans


def _glued(text: str, start: int, end: int) -> bool:
    """A name that is part of a path, a file, a header or an identifier."""
    before = text[start - 1] if start else ""
    after = text[end : end + 3]
    if before and (before.isalnum() or before in "_/\\.-$"):
        # "\nMemoryMap has stopped", "[1;38;5;73mMemoryMap": an escape, not a word.
        return not ESCAPED.search(text[max(0, start - 16) : start])
    if after[:1].isalnum() or after[:1] in "_/\\":
        return True
    if after.startswith("-AI") or after.startswith("-Agent"):
        return True
    # MemoryMap AI.exe, MemoryMap AI.lnk: a file; "MemoryMap." ends a sentence.
    return after[:1] == "." and after[1:2].isalnum()


def _formerly(text: str, start: int) -> bool:
    return text[max(0, start - 12) : start].lower().rstrip(" (").endswith("formerly")


def rebrand_text(text: str, quotes_kept: bool, repo: str = DEFAULT_REPO) -> tuple[str, int]:
    spans = _protected_spans(text, quotes_kept)

    def inside(i: int) -> bool:
        return any(a <= i < b for a, b in spans)

    out, last, count = [], 0, 0
    for m in NAME.finditer(text):
        s, e = m.span()
        if inside(s) or _glued(text, s, e) or _formerly(text, s):
            continue
        out.append(text[last:s])
        out.append(NEW)
        last = e
        count += 1
    out.append(text[last:])
    text = "".join(out)
    if repo != OLD_REPO:
        owner, name = repo.split("/", 1)
        old_pages = f"{OLD_REPO.split('/')[0].lower()}.github.io/{OLD_REPO.split('/')[1]}"
        new_pages = f"{owner.lower()}.github.io/{name}"
        # The owner/name slug only ever names the repo: github.com, the API,
        # raw files, badges.
        for old, new in ((OLD_REPO, repo), (old_pages, new_pages)):
            pieces = text.split(old)
            if len(pieces) > 1:
                rebuilt = [pieces[0]]
                pos = len(pieces[0])
                for piece in pieces[1:]:
                    if inside(pos):
                        rebuilt.append(old)
                    else:
                        rebuilt.append(new)
                        count += 1
                    rebuilt.append(piece)
                    pos += len(old) + len(piece)
                text = "".join(rebuilt)
    return text, count


def _quotes_kept(path: Path) -> bool:
    rel = path.relative_to(ROOT).as_posix()
    return path.suffix.lower() == ".md" and rel.startswith(QUOTE_KEPT)


def _read(path: Path) -> str:
    # newline="": a .bat keeps its CRLF; cmd.exe misreads labels without it.
    with open(path, encoding="utf-8", newline="") as handle:
        return handle.read()


def candidate_files() -> list[Path]:
    listed = subprocess.run(["git", "ls-files", "-z"], cwd=ROOT, capture_output=True, check=True).stdout
    files = []
    for raw in listed.split(b"\0"):
        rel = raw.decode("utf-8", "replace")
        if not rel or rel in SKIP_FILES or rel.startswith(SKIP_PREFIXES):
            continue
        path = ROOT / rel
        if path.suffix.lower() == ".svg":  # logos and icons wait for the logo pass
            continue
        if path.suffix.lower() in TEXT_SUFFIXES or path.name in TEXT_NAMES:
            files.append(path)
    return files


def _ident_files() -> list[Path]:
    """The brand's files, plus code under scratchpad/ (sweeps and helpers run
    the app by its module name); never the old package's shim."""
    listed = subprocess.run(["git", "ls-files", "-z", "scratchpad"], cwd=ROOT, capture_output=True, check=True).stdout
    extra = [ROOT / raw.decode("utf-8", "replace") for raw in listed.split(b"\0") if raw]
    extra = [p for p in extra if p.suffix.lower() in CODE_SUFFIXES]
    return [p for p in candidate_files() + extra if p.relative_to(ROOT).as_posix() not in IDENT_SKIP]


def _ident_ok(path: Path) -> bool:
    return path.relative_to(ROOT).as_posix() not in IDENT_SKIP


def _rewrite(path: Path, text: str, repo: str, brand: bool, ident: bool) -> tuple[str, int]:
    count = 0
    if brand and "MemoryMap" in text:
        text, n = rebrand_text(text, _quotes_kept(path), repo)
        count += n
    if ident and ("memorymap" in text or "MEMORYMAP_" in text):
        text, n = ident_text(text, _quotes_kept(path))
        count += n
    return text, count


def pending(repo: str = DEFAULT_REPO, brand: bool = True, ident: bool = True) -> dict[str, int]:
    """File -> replacements still to make; empty when the rename is complete."""
    found: dict[str, int] = {}
    brand_files = {p for p in candidate_files()} if brand else set()
    files = sorted(set(_ident_files()) | brand_files) if ident else sorted(brand_files)
    for path in files:
        try:
            text = _read(path)
        except (UnicodeDecodeError, FileNotFoundError, IsADirectoryError):
            continue
        _, count = _rewrite(path, text, repo, brand and path in brand_files, ident and _ident_ok(path))
        if count:
            found[path.relative_to(ROOT).as_posix()] = count
    return found


def main(argv: list[str]) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--check", action="store_true", help="change nothing; exit 1 if anything is left")
    parser.add_argument("--repo-url", default=DEFAULT_REPO, help="owner/name of the GitHub repo")
    parser.add_argument("--brand-only", action="store_true", help="the product name and URLs, not the package and env names")
    args = parser.parse_args(argv)
    total = 0
    brand_files = set(candidate_files())
    for rel, count in sorted(pending(args.repo_url, ident=not args.brand_only).items()):
        total += count
        print(f"{count:5d}  {rel}")
        if not args.check:
            path = ROOT / rel
            new, _ = _rewrite(path, _read(path), args.repo_url, path in brand_files, not args.brand_only and _ident_ok(path))
            with open(path, "w", encoding="utf-8", newline="") as handle:
                handle.write(new)
    verb = "left" if args.check else "changed"
    print(f"{total} {verb}")
    return 1 if args.check and total else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
