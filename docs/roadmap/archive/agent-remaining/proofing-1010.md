# proofing-1010

Done: plan size caps (1a7c1c6da), agent_common.md merge (058b0d1b9), orient hook (af90e964d), scratchpad 1018 to 736 files, cap 766.

Left:
- `bash scripts/gate.sh --staged` fails here on lints that predate this work: ruff over `src/memorymap/vendor/` (1140 errors, whoosh), the networkx conflict-marker test, README tool count (67). Fix the vendored-path ruff exclude and the README count.
- The `--staged` gate took 6 minutes with other gates running; its slowest step is worth measuring.
