"""The owner's benches (tools/avatar-lab.html, tools/companion-sim.html) load the
app's renderers without app.js; the owner found both broken on 2026-11-03 after
the blink rig moved to atlas-motion.js and the look pickers to
companion-settings.js. These hold what a file can say: every script they load
exists, and every lazy module the renderers ask for has a stand-in with the
same files as the app's own map.
"""

from __future__ import annotations

import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
TOOLS = ROOT / "tools"
JS = ROOT / "frontend" / "js"
SHIMS = (TOOLS / "lab-shims.js").read_text(encoding="utf-8")
#: The renderers the benches load (tools/*.js `script("js/...")` and modules).
RENDERERS = ("avatars.js", "atlas.js", "atlas-motion.js", "companion-settings.js", "prefs.js")


def _lab_modules() -> dict[str, list[str]]:
    body = SHIMS.split("const LAB_MODULES = {", 1)[1].split("};", 1)[0]
    return {m.group(1): re.findall(r'"([^"]+)"', m.group(2)) for m in re.finditer(r"(\w+):\s*\[([^\]]*)\]", body)}


def _app_modules() -> dict[str, list[str]]:
    app = (JS / "app.js").read_text(encoding="utf-8").split("const LAZY_MODULES = {", 1)[1].split("\n};", 1)[0]
    return {m.group(1): re.findall(r'"([^"]+)"', m.group(2)) for m in re.finditer(r"^\s+(\w+):\s*\[([^\]]*)\],", app, re.M)}


def test_each_bench_loads_the_shims_first_and_every_script_it_names_exists() -> None:
    for page, script in (("avatar-lab.html", "avatar-lab.js"), ("companion-sim.html", "companion-sim.js")):
        html = (TOOLS / page).read_text(encoding="utf-8")
        assert html.index('src="lab-shims.js"') < html.index(f'src="{script}"'), f"{page}: the shims must load before {script}"
        for src in re.findall(r'script\("(js/[^"]+)"\)', (TOOLS / script).read_text(encoding="utf-8")):
            assert (ROOT / "frontend" / src).is_file(), f"{script} loads {src}, which is gone"


def test_every_lazy_module_the_renderers_ask_for_has_a_stand_in() -> None:
    lab, app = _lab_modules(), _app_modules()
    for name in RENDERERS:
        for asked in re.findall(r'ensureModule\("(\w+)"', (JS / name).read_text(encoding="utf-8")):
            assert asked in lab, f"{name} asks for {asked}; tools/lab-shims.js has no stand-in"
    for name, files in lab.items():
        assert app.get(name) == files, f"lab-shims.js {name} is {files}, the app's is {app.get(name)}"
