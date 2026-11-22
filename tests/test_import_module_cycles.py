"""Cycles through `importlib.import_module` count as cycles (audit 2026-10-05,
ARCH-10).

`test_no_import_cycles.py` counts `import` statements, and reports none. Its
own docstring names the way round it: replace the edge that closes a cycle
with `importlib.import_module("memorymap....")` at the call site. That breaks
the import-time ordering problem and leaves the dependency exactly where it
was, so the package has no real layering: measured with those edges counted,
three cycle groups, the largest fifteen modules (`core.deps`, `core.events`,
`entry.manager`, `search.engine`, `ai.embeddings`, `ai.provider` and nine
more).

This is a ratchet, not a fix: the numbers below are what the package holds
today, and a change may only lower them. Inverting an edge with a registry
(`jobstore.set_forget` is the pattern) is how a group shrinks; when it does,
lower the number here in the same commit.
"""

from __future__ import annotations

import ast
from collections import defaultdict
from pathlib import Path

from tests._repo_files import repo_files

SRC = Path(__file__).resolve().parents[1] / "src"
PACKAGE = "tessellate"

#: The ratchet. Lower these when a group shrinks; never raise them.
#: 15 and 3 at the audit; 14 and 2 measured 2026-11-21 (L688); 14 and 1 after the launcher
#: registry and `paths.bundle_root` took the overlay and Settings edges (L-world-class-791).
MAX_LARGEST_GROUP = 0
MAX_GROUPS = 0


def _module_name(path: Path) -> str:
    rel = path.relative_to(SRC).with_suffix("")
    name = ".".join(rel.parts)
    return name[: -len(".__init__")] if name.endswith(".__init__") else name


def _graph() -> dict[str, set[str]]:
    modules = {_module_name(p): p for p in repo_files(SRC, suffixes=(".py",))}
    graph: dict[str, set[str]] = defaultdict(set)

    def resolve(target: str) -> str | None:
        while target and target not in modules:
            target = target.rpartition(".")[0]
        return target or None

    for name, path in modules.items():
        tree = ast.parse(path.read_text(encoding="utf-8"))
        for node in ast.walk(tree):
            targets: list[str] = []
            if isinstance(node, ast.Import):
                targets = [alias.name for alias in node.names]
            elif isinstance(node, ast.ImportFrom) and node.module and node.level == 0:
                targets = [node.module] + [f"{node.module}.{alias.name}" for alias in node.names]
            elif (
                isinstance(node, ast.Call)
                and isinstance(node.func, ast.Attribute)
                and node.func.attr == "import_module"
                and node.args
                and isinstance(node.args[0], ast.Constant)
                and isinstance(node.args[0].value, str)
            ):
                targets = [node.args[0].value]
            for target in targets:
                if not target.startswith(PACKAGE):
                    continue
                resolved = resolve(target)
                if resolved and resolved != name:
                    graph[name].add(resolved)
    return graph


def _groups(graph: dict[str, set[str]]) -> list[set[str]]:
    """Strongly connected components of more than one module (Tarjan)."""
    index: dict[str, int] = {}
    low: dict[str, int] = {}
    stack: list[str] = []
    on_stack: set[str] = set()
    found: list[set[str]] = []
    counter = [0]

    def visit(node: str) -> None:
        work = [(node, iter(sorted(graph.get(node, ()))))]
        index[node] = low[node] = counter[0]
        counter[0] += 1
        stack.append(node)
        on_stack.add(node)
        while work:
            current, children = work[-1]
            advanced = False
            for child in children:
                if child not in index:
                    index[child] = low[child] = counter[0]
                    counter[0] += 1
                    stack.append(child)
                    on_stack.add(child)
                    work.append((child, iter(sorted(graph.get(child, ())))))
                    advanced = True
                    break
                if child in on_stack:
                    low[current] = min(low[current], index[child])
            if advanced:
                continue
            work.pop()
            if work:
                parent = work[-1][0]
                low[parent] = min(low[parent], low[current])
            if low[current] == index[current]:
                group = set()
                while True:
                    member = stack.pop()
                    on_stack.discard(member)
                    group.add(member)
                    if member == current:
                        break
                if len(group) > 1:
                    found.append(group)

    for node in sorted(graph):
        if node not in index:
            visit(node)
    return found


def test_cycles_through_import_module_do_not_grow():
    groups = _groups(_graph())
    largest = max((len(group) for group in groups), default=0)
    detail = "\n".join(", ".join(sorted(group)) for group in sorted(groups, key=len, reverse=True))
    assert largest <= MAX_LARGEST_GROUP, f"the largest cycle grew to {largest} modules:\n{detail}"
    assert len(groups) <= MAX_GROUPS, f"{len(groups)} cycle groups:\n{detail}"


def test_the_walk_sees_an_import_module_edge():
    """The lint's own guard: a cycle closed only by `import_module` is found."""
    graph = {"memorymap.a": {"memorymap.b"}, "memorymap.b": {"memorymap.a"}}
    assert _groups(graph) == [{"memorymap.a", "memorymap.b"}]
