# Releasing Tessellate

How to cut a version and publish the Windows installer and the Linux package.
Everything after you push a tag is automatic. This page is mostly about the few
things to get right before that.

- [Quick reference](#quick-reference)
- [Before you tag: the checklist](#before-you-tag-the-checklist)
- [Tagging and pushing](#tagging-and-pushing)
- [What happens automatically](#what-happens-automatically)
- [Verifying the release](#verifying-the-release)
- [If something goes wrong](#if-something-goes-wrong)
- [Re-releasing or patching a bad release](#re-releasing-or-patching-a-bad-release)
- [Version numbering](#version-numbering)

## Quick reference

For when you have done this before and need the commands:

```
# 1. Bump the version everywhere it lives (see the checklist below)
#    src/tessellate/__init__.py, pyproject.toml, the ?v= stamps in
#    frontend/index.html, capture.html and clip.html, and the README's
#    "Version 0.x.y." line

# 2. Rename the changelog header (both copies)
#    CHANGELOG.md and docs/CHANGELOG.md:
#    "## [Unreleased]"  ->  "## [0.4.0] - 2026-10-20"
cp CHANGELOG.md docs/CHANGELOG.md

# 3. Commit
git add src/tessellate/__init__.py pyproject.toml README.md \
  frontend/index.html frontend/capture.html frontend/clip.html \
  CHANGELOG.md docs/CHANGELOG.md
git commit -m "Release 0.4.0" && git push

# 4. Tag and push the tag: this is what triggers the release
git tag v0.4.0
git push origin v0.4.0

# 5. Watch https://github.com/Braydenh563/Tessellate/actions
#    Jobs run as: resolve-version, github-release, then
#    build-windows-installer and build-linux-package in parallel
#    (about 10 to 15 minutes each). When all are green, the .exe, the
#    Linux .tar.gz and the Linux .zip are attached to the release.
```

Cannot push a tag from where you are working (a credential without tag-ref
permission, a tag protection rule)? Skip steps 4 and 5: open the Actions tab,
pick **Release**, choose **Run workflow** and enter the version (`0.4.0`, with no
leading `v`). The workflow creates the tag itself as part of creating the
release. Pushing the tag was only ever a convenience.

Nothing else is built or uploaded by hand.

## Before you tag: the checklist

Three things must be true before the tag, because the pipeline reads them and
does not set them for you.

### 1. Bump the version everywhere it lives

`__version__` in `src/tessellate/__init__.py` is the source of truth. It shows in
**Settings, About**, in the Windows installer's file properties, and is what the
in-app update check (`GET /update/check`) compares against GitHub's latest
release tag. **A tag that disagrees with it stops the release**: the first job
of `release.yml` compares the two and fails before anything is built, and
the workflow reads the installer's own version from this file too and passes it
to `installer.iss` as `/DMyAppVersion` (which refuses a `TESSELLATE_VERSION` that
says otherwise).

The same number is written in four more places. Two have a lint that fails the
build if they are missed, and two you must remember:

| Place | Checked by |
| --- | --- |
| every `?v=` stamp in `frontend/index.html` | `tests/test_asset_cache_busting.py` |
| the README's "Version 0.x.y." line | `tests/test_readme_freshness.py` |
| `pyproject.toml`, the `version` line | nothing: do it by hand |
| the same `?v=` stamps in `frontend/capture.html` and `frontend/clip.html` | nothing: do it by hand |

The README line is also where the test count, the tool count and the skill count
are checked, so a release is a good moment to read the README against the app.

### 2. Rename the changelog header, in both copies

`CHANGELOG.md` keeps everything not yet released under `## [Unreleased]`. Before
tagging, rename that header to the version and today's date:

```diff
-## [Unreleased]
+## [0.4.0] - 2026-10-20
```

Then add a fresh, empty `## [Unreleased]` above it for the next round of work:

```markdown
## [Unreleased]

## [0.4.0] - 2026-10-20
### Added
...
```

**Do this in `docs/CHANGELOG.md` too.** It is a byte-for-byte mirror of the root
file, because GitHub Pages only serves `/docs`, and
`tests/test_docs_site.py` fails the build if the two ever differ:

```
cp CHANGELOG.md docs/CHANGELOG.md
```

This matters beyond bookkeeping. The `github-release` job searches
`CHANGELOG.md` for a header that matches the tag's version and uses that section
as the release description. Skip the rename and the match comes back empty. The
release is still created, with GitHub's generic list of commits in place of your
changelog entry.

### 3. CI is already green

Push only from a state where CI passes on the branch you are releasing from. The
release workflow does not run the test suite: it trusts that the tagged code
already passed CI. For a change to the packaging itself (`tessellate.spec`,
`installer.iss`, the workflow), check that **Package check**
(`.github/workflows/package-check.yml`) is green too. It builds the frozen Windows
app and the installer, installs them silently and starts the app, so a packaging
break shows up before release day. It publishes nothing.

## Tagging and pushing

```
git tag v0.4.0
git push origin v0.4.0
```

The tag format matters. The workflow triggers on **`v*`**
(`.github/workflows/release.yml`), and it strips the leading `v` to get the
version it bakes into the installer. Always tag `v0.4.0`, never `0.4.0` alone.

Tag a commit that is already on `main`, or whichever branch you release from.
Tagging a branch tip that has not been merged ships code nobody else has
reviewed.

## What happens automatically

Pushing the tag starts `.github/workflows/release.yml`. It has four jobs:

**1. `resolve-version`** (seconds). Works out the version and the tag from the tag
push or from the manual run's input.

**2. `github-release`** (about 30 seconds). Creates the GitHub Release for the
tag, with its description taken from `CHANGELOG.md`'s matching section.

**3. `build-windows-installer`** (about 10 to 15 minutes, on `windows-latest`),
after the release exists:

- Installs a trimmed dependency set, deliberately **without**
  `sentence-transformers` and torch. Settings, Packages treats those as an
  optional post-install, like voice dictation, and a multi-hundred-MB download in
  the base installer would contradict that.
- Runs PyInstaller against `packaging/windows/tessellate.spec`. It is a onedir
  build: a onefile build would re-extract itself on every launch, a poor fit for
  an app meant to open like a normal desktop app.
- **Smoke-tests the frozen app.** It starts the built executable on a scratch data
  folder and fails the release unless the app serves its page within a minute.
- Runs Inno Setup against `packaging/windows/installer.iss` with
  `/DMyAppVersion=` the version in `src/tessellate/__init__.py`; it refuses a
  `TESSELLATE_VERSION` (the tag) that differs.
- Uploads `Tessellate-Setup-<version>-windows-x86_64.exe` to the release. The
  WiX `.msi` steps are present but switched off: its toolkit's licence terms
  stopped the release build.

**4. `build-linux-package`** (about 10 to 15 minutes, on `ubuntu-latest`), in
parallel with the Windows job:

- Installs GTK and WebKit for pywebview's Linux backend, then the same trimmed
  dependency set without the system-tray pieces.
- Runs PyInstaller against `packaging/linux/tessellate.spec` and smoke-tests the
  result the same way.
- Uploads `Tessellate-<version>-linux-x86_64.tar.gz` and a `.zip` of the same
  build. The tarball is the one to recommend: a zip does not reliably carry the
  executable bit, and a launcher without it cannot be started.

Nothing is published to PyPI, on purpose. The app ships through GitHub Releases,
not as something you `pip install`; the reason is in the comment at the top of
`release.yml`.

## Verifying the release

1. Open the [Actions tab](https://github.com/Braydenh563/Tessellate/actions)
   and confirm every job finished green. The two build jobs are the ones that can
   genuinely fail (a dependency drifting, an Inno Setup syntax error, PyInstaller
   missing a hidden import), so watch them rather than assume.
2. Open the [release itself](https://github.com/Braydenh563/Tessellate/releases)
   and confirm:
   - the description matches what you wrote in `CHANGELOG.md`, not GitHub's
     generic notes (a sign the header rename was missed);
   - `Tessellate-Setup-<version>-windows-x86_64.exe`, the Linux `.tar.gz` and
     the Linux `.zip` are all attached.
3. **If you can reach a Windows machine, run the installer once.** The pipeline
   proves the build starts and serves its page, and the Package check proves a
   silent install works. Neither is a person double-clicking the installer on a
   real profile, which is the step that is still "should work" rather than
   "verified". It is worth closing on the first release after any packaging
   change.

## If something goes wrong

**A build job fails.** Read its log on the Actions tab. PyInstaller failures
usually name a missing hidden import: add it to the matching spec file's
`hiddenimports` list (the app's own modules are all listed already, by file).
Inno Setup failures usually name a bad path, or a tag that does not match
`__version__`. Fix the file, commit, and re-tag (next section). There is no
way to re-run just the failed job against the same tag with a fix, because the fix
has to be in the tagged commit.

**The smoke test fails.** The frozen app did not answer on its port within a
minute. The job prints the app's own `desktop-stdio.log`, which is where a startup
crash lands.

**The changelog section is empty, or generic notes appeared.** The header rename
in `CHANGELOG.md` did not match the tag's version exactly (a typo, or a version
that differs from what you tagged). Edit the release description by hand on
GitHub. There is no need to re-tag, because the changelog text does not affect the
build.

**You tagged the wrong commit, or want to change something before anyone
downloads it.** See the next section, and do not force-push the tag.

## Re-releasing or patching a bad release

**Never force-push an existing tag.** If `v0.4.0` is wrong, do not move it. Delete
it and the release, then ship the fix as `v0.4.1`:

```
# Delete the tag locally and on GitHub
git tag -d v0.4.0
git push origin :refs/tags/v0.4.0

# Also delete the GitHub Release itself (Releases page, the release, Delete)
# so a stale asset does not linger under a tag that no longer exists.
```

Then fix the problem, bump to `0.4.1`, and go through the checklist again from the
top. A version number burned on a bad build is cheap to skip, and not worth
fighting the tag to reuse.

## Version numbering

This project is `0.x` while it stabilises (see the README's status line and
`CHANGELOG.md`'s own header). Loosely:

- **Patch** (`0.3.0` to `0.3.1`): bug fixes, no new features, nothing that changes
  how existing features behave.
- **Minor** (`0.3.0` to `0.4.0`): new features and meaningful behaviour changes,
  the normal case for most releases at this stage.
- There is no written criterion for `1.0`. That is a decision to make
  deliberately when it comes up, not a rule to follow automatically.
