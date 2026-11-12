"""Inventory of tracked scratchpad files: KEEP or DELETE candidate.

Run from anywhere in the repo: python scratchpad/cleanup_inventory.py [--list] [--delete-list]
A file is KEEP when something that matters names it (by basename or path):
tests/, scripts/, .github/, the top-level docs and plans, the open agent
ledgers, or another KEEP scratchpad file (followed transitively through
require()/import and any file name it mentions). A short always-keep list and
anything changed in git in the last three days (any branch) stay too.
Everything else is a DELETE candidate; git history keeps it.
"""
import collections
import fnmatch
import os
import re
import subprocess
import sys

ROOT = subprocess.check_output(["git", "rev-parse", "--show-toplevel"], text=True).strip()
os.chdir(ROOT)

ALWAYS = {
    "scratchpad/ui-sweeps/" + n
    for n in ("lib.js", "errors.js", "contrast.js", "docks.js", "touch.js", "chrome.js", "serve.sh")
} | {
    "scratchpad/" + n
    for n in (
        "killport.sh", "inbox_resolve.py", "changelog_union.py", "llama-dev.sh",
        "fake_openai_server.py", "pngpixel.py", "cleanup_inventory.py", "README.md",
    )
}
TEXT_EXT = {".py", ".js", ".sh", ".md", ".yml", ".yaml", ".json", ".txt", ".toml", ".cfg", ".html", ".css", ".bat", ".ps1"}
RECENT_DAYS = 3
TOKEN = re.compile(r"[\w.\-]+")
REQUIRE = re.compile(r"""(?:require\(|from\s+|import\s+)['"]?(\.{1,2}/[\w./\-]+)""")


def git(*args):
    return subprocess.check_output(["git", *args], text=True, errors="replace")


def read(path):
    try:
        with open(path, encoding="utf-8", errors="replace") as fh:
            return fh.read()
    except OSError:
        return ""


def is_source(p):
    """Files whose mentions count as naming a scratchpad file."""
    if p.startswith("scratchpad/"):
        return False
    base = os.path.basename(p)
    return (
        p.startswith(("tests/", "scripts/", ".github/"))
        or p in ("CLAUDE.md", "README.md", "docs/ARCHITECTURE.md", "docs/DESIGN.md")
        or p in ("docs/roadmap/HANDOVER.md", "docs/roadmap/INBOX.md", "docs/roadmap/SESSION_BRIEFS.md")
        or base in ("AGENT_SKILLS_REFORM.md", "BACKLOG.md")
        or (base.endswith("_PLAN.md") and p.startswith("docs/"))
        or fnmatch.fnmatch(p, "docs/roadmap/agent-remaining/*.md")
    )


def recent_files():
    """Scratchpad files changed in the last three days on any branch or
    worktree head (other agents' commits live on their own branches)."""
    log = git("log", "--all", f"--since={RECENT_DAYS} days ago", "--name-only", "--format=", "--", "scratchpad")
    return {line for line in log.splitlines() if line}


def tokens(text):
    """Every file-name-shaped word in the text (a path splits on its slashes),
    so a basename check is a set lookup, not a regex over megabytes."""
    return {t.strip(".-") for t in TOKEN.findall(text)}


def required(path, body):
    """Files a scratchpad file pulls in with require('./x') or import './x'."""
    out = set()
    for rel in REQUIRE.findall(body):
        target = os.path.normpath(os.path.join(os.path.dirname(path), rel)).replace(os.sep, "/")
        out.add(target)
        out.update(target + ext for ext in (".js", ".py", ".mjs"))
    return out


def classify():
    files = [p for p in git("ls-files").splitlines() if p]
    scratch = [p for p in files if p.startswith("scratchpad/")]
    scratch_set = set(scratch)
    named = tokens("\n".join(read(p) for p in files if is_source(p)))
    recent = recent_files()
    keep, why = set(), {}
    for p in scratch:
        base = os.path.basename(p)
        if p in ALWAYS:
            keep.add(p)
            why[p] = "always"
        elif p in recent:
            keep.add(p)
            why[p] = "recent"
        # By stem too: scripts/gate.sh --sweeps names its sweeps bare
        # ("phonedocs", run as scratchpad/ui-sweeps/$s.js), and a basename-only
        # match marked eight of them DELETE (CI red, 2026-11-10).
        elif base in named or os.path.splitext(base)[0] in named:
            keep.add(p)
            why[p] = "named"
    by_base = collections.defaultdict(list)
    for p in scratch:
        by_base[os.path.basename(p)].append(p)
    frontier = list(keep)
    while frontier:  # a KEEP file naming another scratchpad file keeps it
        cur = frontier.pop()
        if os.path.splitext(cur)[1] not in TEXT_EXT:
            continue
        body = read(cur)
        hits = required(cur, body)
        for t in tokens(body):
            hits.update(by_base.get(t, ()))
        for p in hits:
            if p in scratch_set and p not in keep:
                keep.add(p)
                why[p] = "via " + os.path.basename(cur)
                frontier.append(p)
    return scratch, keep, why


def main():
    scratch, keep, why = classify()
    delete = [p for p in scratch if p not in keep]
    if "--list" in sys.argv:
        for p in scratch:
            print(("KEEP   " + p + "  (" + why[p] + ")") if p in keep else "DELETE " + p)
    print(f"scratchpad files: {len(scratch)}  KEEP: {len(keep)}  DELETE: {len(delete)}")
    for title, sel in (("KEEP", keep), ("DELETE", set(delete))):
        by_type = collections.Counter(os.path.splitext(p)[1] or "(none)" for p in sel)
        by_dir = collections.Counter(os.path.dirname(p) for p in sel)
        print(f"{title} by type: " + ", ".join(f"{k} {v}" for k, v in by_type.most_common()))
        print(f"{title} by directory: " + ", ".join(f"{k} {v}" for k, v in by_dir.most_common()))
    if "--delete-list" in sys.argv:
        for p in delete:
            print(p)


if __name__ == "__main__":
    main()
