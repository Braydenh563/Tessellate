# Agent rules, 2026-10-05 (read this instead of a long brief)

- Worktree from `claude/notes-flow-rebuild`; `git merge --no-edit claude/notes-flow-rebuild` before you start and before your report.
- Read CLAUDE.md sections 2, 5, 7 and docs/DESIGN.md's recipe index. Terse reports.
- Commit per step, at least every 20 minutes, with the two trailers:
  `Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>` and
  `Claude-Session: https://claude.ai/code/session_01UvMLdXt2CL6M5pkTvwyV17`.
- Before each commit: targeted tests serially (`--basetemp` private), `timeout 1700 bash scripts/gate.sh --staged` and read "failed:  none", plus the CI lints the gate misses for what you touched: tests/test_feature_catalog.py test_list_endpoints_page.py test_list_limits.py test_log_console.py test_raw_fetch_headers.py test_security_boundaries.py test_silent_mutations.py test_ux1005_copy.py test_core_message_wording.py test_help_controls.py test_no_bare_fetch.py test_badge_recipe.py. Never the full suite.
- Never raise a cap (gzip, boot budget, guards/lets ratchets, ALLOWED tables): fold module state into one const object, drop same-bundle `typeof` guards, move code to a lazy bundle. Breakpoints only 599.98/600, 819.98/820, 1099.98/1100.
- CodeQL: no `assert client.x(...)`; strip \r\n from user text before logging; never return `str(exc)` to a response; comment every bare except; no unused variables; `shutil.which` before subprocess in tests.
- Route-to-route calls pass every parameter by keyword (signatures change).
- Help moves with the UI (help_chat.py, help_topics_more.py, data-help-for, tests/test_manual_parity.py). No em-dashes. Sentence case.
- Own port and data dir; serve with `bash scratchpad/ui-sweeps/serve.sh <port> <dir>`; kill only by port (`scratchpad/killport.sh`). Never press Install in a sweep. No new required deps.
- UI work: a sweep in scratchpad/ui-sweeps/ at 1440 and 390, light and dark, numbers not screenshots; show the base fails and the fix passes.
- Do not edit INBOX.md. CHANGELOG line in both CHANGELOG.md and docs/CHANGELOG.md (identical). A plan step built: its Built block moves to HISTORY.md.
- Before stopping: `docs/roadmap/agent-remaining/<your-name>.md` (done, left). Report in five lines: status, commits, numbers, not verified, found-not-fixed.
