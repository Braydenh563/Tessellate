# rebrand-1011: Tessellate, formerly MemoryMap AI (INBOX 903)

The owner, 2026-10-11: "alright lets rename and retrademark to Tessellate
update absolutely everything including all the documentation and the pages
site. make sure to still note the former name though."

## Step 1, the brand

- `scripts/rebrand.py` (idempotent; `--check`; `--repo-url`, default
  `Braydenh563/Tessellate`). The orchestrator re-runs it after every merge;
  `tests/test_brand_name.py` fails on anything it would still change.
- Kept on purpose, with `brand: keep` beside each: the data folder
  (`config._default_data_dir`), the LAN certificate subject, the bcrypt-input
  salt, the stored caption sentinel, the PyInstaller bundle and exe name
  (`MemoryMap AI.exe`), the installer folders (`MyAppDirName`, WiX
  INSTALLFOLDER), the release asset names (`MemoryMap-AI-Setup-*`, which the
  in-app updater of every installed copy matches).
- Shortcuts are renamed and the old ones removed on upgrade (installer.iss
  [InstallDelete], start.bat, start.sh) and on uninstall.
- `/health` says Tessellate; every check accepts both names
  (`instance_lock.APP_NAMES`, start/uninstall .sh/.bat).

## Step 2, the internal identifiers (separate, last commit)

Not started at the time of writing; see below once it lands.

## Not verified

- The Windows installer, the upgrade from a pre-rename release and the
  package-check workflow's shortcut checks: no Windows here; CI runs them.
- The icons' own `<title>` (favicon.svg, icon-maskable.svg) still say the old
  name: the owner's logo pass owns them.
