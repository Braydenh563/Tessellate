# Running copies (INBOX 1641 remainder), agent remaining list

Done: Settings, About, Running copies row (`renderRunningCopies`, settings-health.js); `core/running_copies.py` (per-user record `<pid>.json`, stale prune, shutdown with route-then-verified-pid fallback); `POST /instance/shutdown` (token + loopback) in api/app.py; `GET /running-copies`, `POST /running-copies/{pid}/shutdown` in api/routes_tasks.py; the quit timer moved to `jobs.thread` (`stop_process_soon`); start.bat names another Tessellate copy and points to Settings; Guide topic `running-copies`; tests/test_running_copies_1641.py.

Remaining:
- Unverified on Windows: record folder `%LOCALAPPDATA%\Tessellate\run`, `taskkill` fallback, PowerShell command-line check in `running_copies._command_line`, the start.bat message branch (`:port_pid_is_ours`).
- A copy that is shutting down within 90 s of its start still lists (boot grace); the record goes when the process exits (measured under 10 s).
- The fallback needs the port to answer as Tessellate, so a hung server is reported "did not answer" and left running (by design: never end a pid not proven to be this app).
- start.sh has no new message: a Tessellate on the port already makes it open that copy (`mm_port_is_memorymap`).
- Launcher does not offer to shut the other copy down itself (message only, as the brief allows).
- CHANGELOG, README numbers, INBOX 1641 resolve, codemap regenerate: orchestrator.
