#!/usr/bin/env python3
"""Write docs/CODEMAP.md: where every function, id, route, CSS section and
plan heading lives, as `name | file:line` rows.

The map exists because the cheapest way to find code in this repository is a
grep of a table, not a read of a 5,000-line file. The orient skill sends every
session and agent here first, so a stale map sends them to the wrong line.
That is why tests/test_codemap_fresh.py regenerates the map and compares it
with the committed copy: a change that moves a function fails until the map is
regenerated with `python scripts/codemap.py`.

Deterministic on purpose: the only non-repository input is the generation
date, which the lint reads back from the committed file, so a map generated on
one day still matches on the next. Stdlib only; every file is read through a
`with` block or `read_text`, and nothing is run in a shell.
"""

from __future__ import annotations

import ast
import datetime
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "docs" / "CODEMAP.md"

HTTP_METHODS = frozenset(
    {"get", "post", "put", "patch", "delete", "options", "head", "api_route", "websocket"}
)
ROUTER_NAMES = frozenset({"router", "app"})
SCRIPT_SRC = re.compile(r'<script src="/js/([^"?]+)', re.IGNORECASE)
ID_ATTRIBUTE = re.compile(r'(?<![\w-])id="([^"]*)"')
FUNCTION_DECLARATION = re.compile(r"^(?:async\s+)?function\s+([A-Za-z_$][\w$]*)\s*\(")
ARROW_CONSTANT = re.compile(r"^const\s+([A-Za-z_$][\w$]*)\s*=\s*(?:async\s+)?\(")
#: A script that is one closure from its first code line to its last
#: (sketch-pad.js): its functions sit one step in, and are listed too.
CLOSURE_OPEN = re.compile(r"^\(\s*(?:async\s*)?(?:\(\)\s*=>|function\s*\(\))\s*\{\s*$")
CLOSURE_CLOSE = re.compile(r"^\}\s*\)?\s*\(\)\s*\)?;?\s*$")
INDENTED_FUNCTION = re.compile(r"^  (?:async\s+)?function\s+([A-Za-z_$][\w$]*)\s*\(")
INDENTED_ARROW = re.compile(r"^  const\s+([A-Za-z_$][\w$]*)\s*=\s*(?:async\s+)?\(")
MODULE_LEVEL = re.compile(r"^(?:async\s+def|def|class)\s+([A-Za-z_]\w*)")
TEST_DEFINITION = re.compile(r"^\s*def test_", re.M)
PLAN_HEADING = re.compile(r"^(#{2,3}) +(\S.*)$")
GENERATED = re.compile(r"^Generated (\d{4}-\d{2}-\d{2})\b", re.M)


def _read(path: Path) -> str:
    return path.read_text(encoding="utf-8", errors="replace")


def _lines(text: str) -> list[str]:
    # Split on newline alone: str.splitlines also breaks on form feeds and
    # other separators, which would shift every line number after them.
    lines = text.split("\n")
    if lines and lines[-1] == "":
        lines.pop()
    return lines


def _tree(trees: dict[Path, ast.Module], path: Path) -> ast.Module:
    """Each file is parsed once per build: the routes and the backend modules
    both read src/tessellate/api, and parsing 15 MB of Python twice was most of
    the generation time."""
    if path not in trees:
        trees[path] = ast.parse(_read(path), filename=str(path))
    return trees[path]


def _rel(root: Path, path: Path) -> str:
    return path.relative_to(root).as_posix()


def _cell(text: str) -> str:
    return text.replace("|", "\\|")


def _table(headers: tuple[str, ...], rows: list[tuple[str, ...]]) -> list[str]:
    out = ["| " + " | ".join(headers) + " |", "|" + "|".join("---" for _ in headers) + "|"]
    out.extend("| " + " | ".join(_cell(cell) for cell in row) + " |" for row in rows)
    return out


def _code(name: str) -> str:
    return f"`{name}`"


def _js_order(root: Path) -> list[str]:
    """Script files in index.html's order, then the lazily loaded ones (by
    name), then the service worker, which index.html never loads."""
    js_dir = root / "frontend" / "js"
    on_page: list[str] = []
    for name in SCRIPT_SRC.findall(_read(root / "frontend" / "index.html")):
        if name not in on_page and (js_dir / name).is_file():
            on_page.append(name)
    lazy = sorted(path.name for path in js_dir.glob("*.js") if path.name not in on_page)
    files = [f"frontend/js/{name}" for name in on_page + lazy]
    if (root / "frontend" / "sw.js").is_file():
        files.append("frontend/sw.js")
    return files


def _frontend_functions(root: Path) -> list[tuple[str, list[tuple[str, int]]]]:
    groups = []
    for rel in _js_order(root):
        groups.append((rel, sorted(js_functions(_lines(_read(root / rel))))))
    return groups


def _closure_wrapped(lines: list[str]) -> bool:
    code = [line for line in lines if line.strip() and not line.lstrip().startswith("//")]
    return bool(code) and bool(CLOSURE_OPEN.match(code[0])) and bool(CLOSURE_CLOSE.match(code[-1]))


def js_functions(lines: list[str]) -> list[tuple[str, int]]:
    """`(name, line)` for every top-level function of a script, and for the
    closure's own functions when the script is wrapped whole in one."""
    wrapped = _closure_wrapped(lines)
    found = []
    for number, line in enumerate(lines, 1):
        match = FUNCTION_DECLARATION.match(line) or ARROW_CONSTANT.match(line)
        if wrapped and not match:
            match = INDENTED_FUNCTION.match(line) or INDENTED_ARROW.match(line)
        if match:
            found.append((match.group(1), number))
    return found


def _frontend_ids(root: Path) -> list[tuple[str, int]]:
    rel_lines = _lines(_read(root / "frontend" / "index.html"))
    found = []
    for number, line in enumerate(rel_lines, 1):
        found.extend((match, number) for match in ID_ATTRIBUTE.findall(line))
    return sorted(found)


def _banner_text(lines: list[str], index: int) -> str:
    text = lines[index].strip().strip("/*-= ").strip()
    if not text and index + 1 < len(lines):
        # A banner rule with its title on the next line.
        text = lines[index + 1].strip().strip("/*-= ").strip()
    return text or "(no title)"


def _css(root: Path) -> tuple[list[tuple[str, str, int]], list[tuple[str, int]]]:
    sections: list[tuple[str, str, int]] = []
    sizes: list[tuple[str, int]] = []
    for path in sorted((root / "frontend" / "css").glob("*.css")):
        rel = _rel(root, path)
        lines = _lines(_read(path))
        sizes.append((rel, len(lines)))
        for number, line in enumerate(lines, 1):
            if line.startswith("/* ===") or line.startswith("/* ---"):
                sections.append((_banner_text(lines, number - 1), rel, number))
    return sorted(sections), sizes


STATEMENT_FIELDS = ("body", "orelse", "finalbody", "handlers", "cases")


def _function_defs(tree: ast.Module) -> list[ast.AST]:
    """Every function definition in a module, nested ones included. A def is
    always a statement, so only statement containers are descended into:
    ast.walk visits every expression node too, and that was most of the
    generation time (about 4 of 7 s under cProfile)."""
    found = []
    stack: list[ast.AST] = [tree]
    while stack:
        node = stack.pop()
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            found.append(node)
        for field in STATEMENT_FIELDS:
            stack.extend(getattr(node, field, None) or [])
    return found


def _routes(root: Path, trees: dict[Path, ast.Module]) -> list[tuple[str, str, str, str, int]]:
    rows = []
    for path in sorted((root / "src" / "tessellate" / "api").glob("*.py")):
        rel = _rel(root, path)
        tree = _tree(trees, path)
        for node in _function_defs(tree):
            for decorator in node.decorator_list:
                if not (
                    isinstance(decorator, ast.Call)
                    and isinstance(decorator.func, ast.Attribute)
                    and decorator.func.attr in HTTP_METHODS
                    and isinstance(decorator.func.value, ast.Name)
                    and (decorator.func.value.id in ROUTER_NAMES or decorator.func.value.id.endswith("_router"))
                ):
                    continue
                route = decorator.args[0] if decorator.args else None
                if route is None:
                    route = next((kw.value for kw in decorator.keywords if kw.arg == "path"), None)
                if route is None:
                    shown = ""
                elif isinstance(route, ast.Constant) and isinstance(route.value, str):
                    shown = route.value
                else:
                    shown = ast.unparse(route)
                rows.append(
                    (shown, decorator.func.attr.upper(), node.name, rel, decorator.lineno)
                )
    return sorted(rows)


def _backend_modules(root: Path) -> list[tuple[str, list[tuple[str, int]]]]:
    """Column zero is matched on the line, not parsed: a full ast.parse of the
    backend was most of the generation time (about 1.5 s of 2.5 s), and a
    module-level def is always a line that starts with `def`, `async def` or
    `class`. Checked against ast.parse on the tree when this was written."""
    base = root / "src" / "tessellate"
    groups = []
    for path in sorted(base.rglob("*.py")):
        if "vendor" in path.relative_to(base).parts:
            continue
        found = []
        for number, line in enumerate(_lines(_read(path)), 1):
            match = MODULE_LEVEL.match(line)
            if match:
                found.append((match.group(1), number))
        groups.append((_rel(root, path), sorted(found)))
    return groups


def _tests(root: Path) -> list[tuple[str, int]]:
    return [
        (_rel(root, path), len(TEST_DEFINITION.findall(_read(path))))
        for path in sorted((root / "tests").glob("test_*.py"))
    ]


def _plan_headings(root: Path) -> list[tuple[str, str, int]]:
    plans = [root / "docs" / "ROADMAP.md"]
    plans += sorted(
        path for path in (root / "docs" / "roadmap").glob("*.md") if path.name != "HISTORY.md"
    )
    rows = []
    for path in plans:
        rel = _rel(root, path)
        in_fence = False
        for number, line in enumerate(_lines(_read(path)), 1):
            if line.startswith("```"):
                in_fence = not in_fence
                continue
            match = None if in_fence else PLAN_HEADING.match(line)
            if match:
                rows.append((match.group(2).rstrip(), rel, number))
    return sorted(rows)


def build(root: Path, date: str) -> str:
    """The whole map as one string. `date` is the only input that is not the
    repository, so the lint can pass the committed date and compare exactly."""
    trees: dict[Path, ast.Module] = {}
    functions = _frontend_functions(root)
    ids = _frontend_ids(root)
    css_sections, css_sizes = _css(root)
    routes = _routes(root, trees)
    modules = _backend_modules(root)
    tests = _tests(root)
    plans = _plan_headings(root)

    function_count = sum(len(found) for _, found in functions)
    module_count = sum(len(found) for _, found in modules)
    test_total = sum(count for _, count in tests)
    counts = {
        "frontend functions": function_count,
        "frontend ids": len(ids),
        "CSS sections": len(css_sections),
        "backend routes": len(routes),
        "backend modules": module_count,
        "test files": len(tests),
        "tests": test_total,
        "plan headings": len(plans),
    }

    out = [
        "# Code map",
        "",
        (f"Generated {date} by `python scripts/codemap.py` from the repository. "
        "Every row is `name | file:line`: grep this file, then `sed -n 'A,Bp'` the "
        "lines you need. A stale map fails `tests/test_codemap_fresh.py`."),
        "",
        "Counts: " + ", ".join(f"{label} {value}" for label, value in counts.items()) + ".",
        "",
        f"## Frontend functions ({function_count})",
        "",
        ("Top-level `function name(`, `async function name(` and `const name = (` in "
        "`frontend/js/` and `frontend/sw.js`, in index.html's script order; lazily "
        "loaded files after, by name. Rows sorted by name within each file."),
        "",
    ]
    for rel, found in functions:
        if not found:
            continue
        out.append(f"### {rel} ({len(found)})")
        out.append("")
        out.extend(_table(("Name", "File:line"), [(_code(name), f"{rel}:{line}") for name, line in found]))
        out.append("")

    out += [
        f"## Frontend ids ({len(ids)})",
        "",
        "Every `id=\"...\"` in `frontend/index.html`, sorted by id.",
        "",
    ]
    out += _table(("Id", "File:line"), [(_code(name), f"frontend/index.html:{line}") for name, line in ids])
    out.append("")

    out += [
        f"## CSS sections ({len(css_sections)})",
        "",
        "Banner comments (`/* ===` or `/* ---`) in `frontend/css/*.css`, sorted by title.",
        "",
    ]
    out += _table(("Section", "File:line"), [(title, f"{rel}:{line}") for title, rel, line in css_sections])
    out += ["", "### Lines per stylesheet", ""]
    out += _table(("File", "Lines"), [(rel, str(size)) for rel, size in css_sizes])
    out.append("")

    out += [
        f"## Backend routes ({len(routes)})",
        "",
        ("`@router.<method>(`, `@<name>_router.<method>(` and `@app.<method>(` decorators in `src/tessellate/api/*.py`, "
        "sorted by path. The line is the decorator's."),
        "",
    ]
    out += _table(
        ("Path", "Method", "Function", "File:line"),
        [(_code(path) if path else "", method, _code(name), f"{rel}:{line}") for path, method, name, rel, line in routes],
    )
    out.append("")

    out += [
        f"## Backend modules ({module_count})",
        "",
        ("Module-level `def`, `async def` and `class` in `src/tessellate/**/*.py`, "
        "excluding `vendor/`, grouped by file."),
        "",
    ]
    for rel, found in modules:
        if not found:
            continue
        out.append(f"### {rel} ({len(found)})")
        out.append("")
        out.extend(_table(("Name", "File:line"), [(_code(name), f"{rel}:{line}") for name, line in found]))
        out.append("")

    out += [
        f"## Tests ({test_total})",
        "",
        "`def test_` lines in each `tests/test_*.py`.",
        "",
    ]
    out += _table(("File", "Tests"), [(rel, str(count)) for rel, count in tests])
    out.append("")

    out += [
        f"## Plan headings ({len(plans)})",
        "",
        ("Every `##` and `###` heading in `docs/ROADMAP.md` and `docs/roadmap/*.md`, "
        "except the HISTORY.md archive. Sorted by heading."),
        "",
    ]
    out += _table(("Heading", "File:line"), [(name, f"{rel}:{line}") for name, rel, line in plans])
    out.append("")

    return "\n".join(out)


def main() -> int:
    date = datetime.date.today().isoformat()
    text = build(ROOT, date)
    with OUT.open("w", encoding="utf-8", newline="\n") as handle:
        handle.write(text)
    print(f"wrote {_rel(ROOT, OUT)} ({len(text.encode('utf-8'))} bytes)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
