# Codemap agent, remaining (2026-10-10)

Built: `scripts/codemap.py`, `docs/CODEMAP.md`, `tests/test_codemap_fresh.py`, one CLAUDE.md sentence.

- Not indexed: class methods, nested functions, `let`/`var` helpers, and JS functions declared in a form other than `function name(` or `const name = (`.
- Frontend ids are every `id="..."` text in index.html, including any inside HTML comments; not checked for false hits.
- Routes match only `@router.<method>` and `@app.<method>` decorators; another router name is missed.
- Generation measured 2.0 to 2.7 s wall at load average 12 to 15 on four cores (2026-10-10); no unloaded figure was taken, and the 3 s lint budget is tight on a busy machine. The route scan now walks statements only, but under this load the wall time did not drop measurably.
- Staged gate: `ruff check .` fails on vendored `src/memorymap/vendor/whoosh` (1,140 findings, same on the base checkout); `test_plan_hygiene` (vendor networkx conftest markers), `test_scratchpad_size` (1,018 files against a 1,003 cap) and `test_readme_freshness` (tool count) also fail on the base, not on this change.
- Not wired into `scripts/gate.sh` or CI; it runs only as part of the test suite.
