# order-1018 (Sonnet, backend only)

Branch agent/order-1018-1018 from claude/trusting-cannon-wrf8s5 (f433578). Items: 1 cold intent state, 2 composer_725 "dayz" and composer_commands order, 3 spelling ghose/shortyer.

- done 1: intent.classify imports commands itself (typed reader was registered only by commands import); cold-process test in tests/test_owner_typos.py.
- next: item 2, tests/test_composer_725.py "dayz", tests/test_composer_commands.py model-manager test.
- done 1: bb57120. done 2a: spelling._app_counts imports help_chat topics on first use (cold "dayz").
- done 2b: composer_commands model-manager test passes PYTHONPATH to its child (hash in git log).
- done 3: spelling _prefix_kept, NOT_AFTER_A, _y_then_ending, question_noise._at_asking_place; fixtures shortyer, a ghose cursor, what are ghose notes. All three items landed; nothing left but the found-not-fixed below.
- found-not-fixed: tests/test_typo_routing.py "search the web for sandwiches" writes ./data when run serially (conftest guard errors, also at base); tests/test_boot_budget.py boot JS 588516 > cap 588400 (staged-lints fails at base).
