# Contributing to Tessellate

Thanks for your interest. This is a small, focused project with one guiding
principle, so a little context goes a long way.

## The one rule that shapes everything

**Tessellate is 100% offline and local-first.** Every feature must work on the
user's own machine with no cloud dependency. Two features may reach the
internet, web search and the update check, and both are opt-in: web search is
off by default, the update check waits for your answer to a question the first
start asks once, and both are clearly marked. If an idea needs to phone home, it is out of scope by
design, but it is still welcome in a discussion.

A few more principles (the full list is in
[`docs/ARCHITECTURE.md`](docs/ARCHITECTURE.md)):

- The app must stay usable with the AI turned off: degrade, never crash. Saving a
  note must never fail because a model is unavailable.
- Database migrations are **additive** (new columns), so users never lose data.
- Shared state lives in exactly one place (`core/deps.py`). Do not build your own
  `DatabaseManager` or `ConfigManager`.
- Destructive agent actions always ask first.

If you are using an AI assistant on this codebase, read
[`CLAUDE.md`](CLAUDE.md) first. It is the project's own operating manual: where to
check before rebuilding something, the standing lint set, and the failure shapes
seen most often when an assistant works here without reading it.

## Getting set up

```bash
python3 -m venv .venv && source .venv/bin/activate   # Windows: .venv\Scripts\activate
pip install -r requirements.txt
pip install -e .            # editable install, do not forget the dot
```

Run the app with `python -m tessellate` and open <http://localhost:8000>, or use
`./start.sh` (`start.bat` on Windows), which does all of the above.

`requirements.txt` includes `sentence-transformers`, which brings PyTorch (about
2 GB). The test suite fakes every embedding and does not need it. If you only want
to run the tests, install the packages by hand, as `CLAUDE.md` section 7 lists them.

## Before you open a PR

Everything runs offline, with no Ollama and no models:

```bash
bash scripts/gate.sh --changed   # lint set, node --check, ruff, and the tests that name your files
ruff check .                     # lint (what CI runs)
pytest -n auto                   # the whole suite: 12,400+ tests, under nine minutes on four cores
```

The full suite takes about 25 minutes serially, so run the gate while you work
and leave the rest to CI, which runs everything on every push. `make check` runs
lint and tests together, and `make help` lists the other tasks. Optionally,
`ruff format .` tidies formatting.

To run the lint and hygiene checks on every commit, install the hooks once:

```bash
pip install pre-commit && pre-commit install
```

CI runs `ruff check`, the test suite on Python 3.11, 3.12 and 3.13, a Playwright
smoke suite, and CodeQL. Keep all of them green.

A set of lints exists because the test suite cannot see the DOM or the prose:
`test_style_scale.py`, `test_ui_signatures.py`, `test_ui_recipes.py`,
`test_css_braces.py`, `test_frontend_ids.py`, `test_frontend_handlers.py`,
`test_dock_grammar.py`, `test_docs_layout.py`, `test_docs_links.py`,
`test_readme_freshness.py`, `test_asset_cache_busting.py`, `test_no_em_dashes.py`,
`test_no_innerhtml_interpolation.py` and `test_markdown_link_schemes.py`. If one
fails, it has found something real: fix the cause, never widen the rule.

Every AI call in the suite is faked. That keeps a run fast and offline, and it
means the suite cannot tell you how a real small model behaves. The tests that can
are marked `evals` and are skipped unless you have a model running:

```bash
bash scratchpad/llama-dev.sh check   # what is present, downloads nothing
bash scratchpad/llama-dev.sh serve   # starts one, prints two exports
pytest -m evals                      # with those exports set
```

Nothing else needs it. The script downloads only when you ask, no mode of
`scripts/gate.sh` calls it, and CI never sees a model.

## Writing code that fits in

- Match the style of the file you are editing: naming, comment density, idioms.
  The codebase favours short comments that say *why*, not *what*.
- New behaviour needs a test. Copy an existing `tests/test_*.py` and reuse the AI
  fakes in `tests/fakes.py` and `tests/conftest.py`. Never call a real model.
- The frontend has no build step. Scripts live in `frontend/js/` and share one
  global scope, loaded in the order `frontend/index.html` lists them; `app.js` is
  the head of that list, not the whole app. Run `node --check` on each file you
  edit, and use `grep -n "^function name" frontend/js/*.js` to find a function.
- New interface comes from the recipe index in
  [`docs/DESIGN.md`](docs/DESIGN.md): a menu, a bar, help text and a surface each
  have a recipe, and spacing and corners are tokens. A need the index does not
  cover gets its recipe and its lint in the same commit as the feature.
- Help moves with the UI. A change that adds, moves, renames or removes a control
  updates every help surface that names it: the `data-help-for` popovers, Settings
  and the guide's topics (`ai/help_chat.py`, `ai/help_topics_more.py`).
- Copy is sentence case, with no em-dashes, no exclamation marks and no "Oops".
  Errors say what happened and what to do.
- If you touch the architecture (a new module, table or data flow), update
  `docs/ARCHITECTURE.md` in the same PR.
- Add a bullet to `CHANGELOG.md` under "Unreleased", and copy the file to
  `docs/CHANGELOG.md`: the two must be identical, and
  `tests/test_docs_site.py` checks it. The same goes for `CONTRIBUTING.md` and
  `SECURITY.md`, which are mirrored into `docs/` for the documentation site.
- A tool, a skill or a version bump changes numbers the README states (the tool
  and skill counts, the version, the optional packages), and
  `tests/test_readme_freshness.py` fails until the README says the same.

## Working with an AI assistant

AI coding tools are welcome here, but this codebase is mature (most obvious
features already exist), and the common failure mode is an assistant "adding"
something that is already there and gutting the working version in the process.
Three rules keep that from happening:

- **Reconcile before building.** Search for the feature first. If it exists,
  extend it, do not reimplement it. (Snooze, chat export, theming, the command
  palette, the skills bar and much more are already built.)
- **Additive only.** Extend functions rather than replacing them, and never
  delete a feature, widget or CSS rule to make room for a new one without asking.
- **One feature per commit.** After each commit, `git diff --stat` should list only
  the files that feature touches. An unexpectedly wide diff is the early warning
  sign of a regression.

## Commit and PR conventions

- Write clear commit messages that explain the *why*.
- Keep PRs focused: one logical change per PR is easier to review.
- The PR template prompts you for the essentials (what and why, how to test, the
  checklist). Fill it in.

## Reporting bugs and suggesting features

Use the issue templates. They ask the few questions that make a local-first app
easy to reproduce. For open-ended ideas, start a Discussion instead of an issue.

## Security

Please do not file security problems as public issues. See
[`SECURITY.md`](SECURITY.md) for how to report them privately.
