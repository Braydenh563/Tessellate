# Vendored design skill

One Claude Code skill, `ui-ux-pro-max`, copied from
[nextlevelbuilder/ui-ux-pro-max-skill](https://github.com/nextlevelbuilder/ui-ux-pro-max-skill)
at commit `91c193ac059b487d13ce535c7015b021eb71c841` (skill version 2.13.0),
MIT-licensed. The licence text is kept beside it as `LICENSE.ui-ux-pro-max`.

**Licence direction matters here.** This project is AGPL-3.0. MIT code may come
*in* (this directory); nothing from this project may go *out* to an MIT
project. Same rule as `docs/ARCHITECTURE.md` (decisions kept from the retired roadmap docs) records for odysseus.

`ui-ux-pro-max` is a searchable local CSV/JSON corpus (styles, palettes, font
pairings, UX guidelines, icons, chart types, stacks) driven by
`scripts/search.py`. `docs/roadmap/WORLD_CLASS_PLAN.md` uses it as the research
step for a surface redesign.

## Pruned 2026-10-10

The same upstream commit also supplied six sibling skills: `design`,
`design-system`, `ui-styling`, `brand`, `slides` and `banner-design`. They were
removed because none had ever been invoked, they target logo, banner, slide
and brand work or React, Tailwind and shadcn stacks that Tessellate does not
use, and their descriptions cost prompt space every turn. `git log -- .claude/skills`
recovers them; an upstream re-copy brings them back too, so copy only
`ui-ux-pro-max`.

## Local modifications

Kept to the minimum, so an upstream refresh is a re-copy plus re-applying these:

1. `ui-ux-pro-max/SKILL.md`: every documented command path was
   `${CLAUDE_PLUGIN_ROOT}/.claude/skills/…`, which resolves only when the repo
   is installed as a *plugin*. As a project skill that variable is unset, so
   the paths became `/.claude/skills/…`, which does not exist. Changed to
   `${CLAUDE_PLUGIN_ROOT:-.}/…`, correct in both installations.
2. `ui-ux-pro-max/SKILL.md`: a note under the title that `docs/DESIGN.md`
   overrides the skill for `frontend/`, and that `--persist` is not used here.
3. `pyproject.toml`: `.claude/skills` in ruff's `extend-exclude`; see the
   comment there. `.github/codeql/codeql-config.yml` excludes it the same way.
4. `.gitignore`: a negation for `.claude/skills/**/data/`. The `data/` rule
   (app user-data) has no leading slash, so it matches at any depth and would
   silently untrack the skill's corpus.

The scripts are Python 3 with no third-party dependencies, so they run without
the project venv:

```bash
python3 ".claude/skills/ui-ux-pro-max/scripts/search.py" "<query>" --domain style
python3 ".claude/skills/ui-ux-pro-max/scripts/search.py" "<query>" --domain ux
```

## What has and has not been checked

Verified: the skill loads as a project skill, `search.py` returns real results
from the bundled CSVs, the repo's tests do not walk this directory, and
`ruff check .` is unaffected.

**Not checked: any design output.** The corpus mostly targets React, Next.js,
Tailwind and shadcn. Tessellate's frontend is vanilla JS and CSS custom
properties under `docs/DESIGN.md`, enforced by `tests/test_style_scale.py`.
Treat its advice as input to a decision; `docs/DESIGN.md` wins on anything that
lands in `frontend/`.
