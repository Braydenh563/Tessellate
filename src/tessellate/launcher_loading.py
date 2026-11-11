"""The desktop window's loading page, split out of `__main__.py` (audit-1028
K24, dec-1111-k2.md): the inline page shown before the server answers, its
look and motion recolouring, and the phase-to-percent table. Moved whole and
unchanged; `__main__` imports these names back, so `launcher._LOADING_HTML`
and `launcher._loading_html()` stay where the desktop path and the tests
read them. Imports nothing from `__main__`.
"""

import os

from tessellate.core import launch_status


# Shown in the desktop window the instant it opens, before the server is
# reachable: replaces what used to be a black/blank window for however long
# _wait_for_server() took, which on a cold start (embeddings warmup, a slow
# machine) is not always instant. Someone running in "hidden console" mode
# (show_console_on_startup=False, or the packaged installer's console-less
# build) has *no* terminal to watch either, so this is the only feedback
# they get that anything is happening at all, reported directly: "the
# window doesn't [show] until all the checks and dependency updates are
# done", which is exactly the gap between this window opening and
# `_boot_and_swap` below finishing.
#
# Deliberately plain, inline HTML/CSS/JS rather than a page served from
# `frontend/`, the whole point is that it must render with no server
# listening on HOST:PORT yet, so it cannot be a request to that server. The
# palette (#4664f0) matches index.html's own `theme-color` meta tag rather
# than pulling in the real app's CSS, so the swap to the real window doesn't
# jar even though nothing is actually shared between them.
#
# The logo is the same reason, and is why it is **copied** here as inline SVG
# rather than referenced. Asked for directly ("add the logo to the loading
# screen"); this window used to show a 10px blue dot beside the wordmark,
# which is the first thing anyone sees of the app on a cold start. It cannot
# be `<img src="/favicon.svg">`, there is no server to serve it, and a
# `file://` path breaks in the packaged build, so the artwork is duplicated.
# It is 30 lines of static geometry that has changed once; keeping the two in
# sync by hand is cheaper than the alternatives, and a drift shows up
# immediately on the next launch.
_LOADING_HTML = """<!doctype html>
<html><head><meta charset="utf-8">
<style>
  html, body { height: 100%; margin: 0; }
  body {
    display: flex; flex-direction: column; align-items: center; justify-content: center;
    gap: 18px; height: 100%; background: #12141c; color: #e7e9ee;
    font: 14px/1.4 -apple-system, "Segoe UI", system-ui, sans-serif;
  }
  .mark { display: flex; flex-direction: column; align-items: center; gap: 10px; font-size: 18px; font-weight: 600; }
  .mark svg { width: 46px; height: 46px; display: block; }
  .tagline { color: #9aa1ad; font-size: 12px; margin-top: -12px; }
  /* The step list, the same one scripts/splash.ps1 draws before this
     window exists, so the handoff from that window to this one looks
     like the same list carrying on rather than a restart. */
  .steps { list-style: none; margin: 0; padding: 0; width: 300px; }
  .steps li { display: flex; align-items: baseline; gap: 8px; padding: 3px 0;
              color: #5d6472; }
  .steps li .tick { width: 14px; flex: none; text-align: center; }
  .steps li .name { flex: none; }
  .steps li .detail { color: #5d6472; font-size: 12px; overflow: hidden;
                      text-overflow: ellipsis; white-space: nowrap; }
  .steps li.done { color: #9aa1ad; }
  .steps li.done .tick { color: #4a9d7a; }
  .steps li.active { color: #e7e9ee; }
  .steps li.active .tick { color: #4f6df5; animation: mm-pulse 1.4s ease-in-out infinite; }
  .steps li.active .detail { color: #9aa1ad; }
  .steps li.failed { color: #e58f8f; }
  .steps li.failed .tick { color: #e58f8f; }
  @keyframes mm-pulse { 0%, 100% { opacity: 1; } 50% { opacity: 0.35; } }
  .bar-track { width: 300px; height: 6px; border-radius: 3px; background: #262b3a; overflow: hidden; }
  .bar-fill { height: 100%; width: 4%; background: #4f6df5; border-radius: 3px;
              transition: width 300ms ease-out; }
  .bar-fill.error { background: #e5a13a; }
  #status { color: #9aa1ad; min-height: 1.2em; }
  /* Two lines reserved, not one: the longest tip names the data folder,
     which wraps, and a fixed 1.4em clipped its second line. min-height
     rather than height so nothing can shift the bar and the step list
     every six seconds either. */
  #tip { color: #5d6472; font-size: 12px; min-height: 2.8em; max-width: 340px;
         text-align: center; transition: opacity 200ms ease-out; }
  /* Reduced motion: the pulse and both fades go, the information stays.
     Nothing here is conveyed by movement alone. */
  @media (prefers-reduced-motion: reduce) {
    .steps li.active .tick { animation: none; }
    .bar-fill, #tip { transition: none; }
  }
</style></head>
<body>
  <div class="mark"><svg viewBox="0 0 100 100" role="img" aria-label="Tessellate">
    <defs>
      <linearGradient id="tile" gradientUnits="userSpaceOnUse" x1="0" y1="0" x2="100" y2="100">
        <stop offset="0%" stop-color="#5b7cff"/><stop offset="55%" stop-color="#4f6df5"/>
        <stop offset="100%" stop-color="#a927d8"/>
      </linearGradient>
      <linearGradient id="pearl" x1="0" y1="0" x2="1" y2="1">
        <stop offset="0%" stop-color="#ffffff"/><stop offset="100%" stop-color="#c9b8ff"/>
      </linearGradient>
      <filter id="lift" x="-30%" y="-30%" width="160%" height="160%">
        <feDropShadow dx="0" dy="3" stdDeviation="2.5" flood-color="#1a1060" flood-opacity="0.45"/>
      </filter>
    </defs>
    <rect width="100" height="100" rx="23" fill="url(#tile)"/>
    <g opacity="0.95"><polygon points="35.3,48.7 46.8,55.4 46.8,68.6 35.3,75.3 23.8,68.6 23.8,55.4" fill="#fff" stroke="#fff" stroke-width="7" stroke-linejoin="round"/></g>
    <g opacity="0.7"><polygon points="64.7,48.7 76.2,55.4 76.2,68.6 64.7,75.3 53.2,68.6 53.2,55.4" fill="#fff" stroke="#fff" stroke-width="7" stroke-linejoin="round"/></g>
    <g filter="url(#lift)"><polygon points="57.3,18.4 67.5,27.0 65.2,40.0 52.7,44.6 42.5,36.0 44.8,23.0" fill="url(#pearl)" stroke="url(#pearl)" stroke-width="7" stroke-linejoin="round"/></g>
  </svg><span>Tessellate</span></div>
  <div class="tagline">Your notes, pieced together</div>
  <ul class="steps" id="steps"></ul>
  <div class="bar-track"><div class="bar-fill" id="bar"></div></div>
  <div id="status">Starting…</div>
  <div id="tip"></div>
  <script>
    // Seeded by _loading_html() from the launcher's own status file before
    // this window is created: see core/launch_status.py. The launcher's
    // work (the git pull, building .venv, the pip install) is already over
    // by the time this page exists, so without the seed the list would
    // open empty and only ever learn about the steps still to come. An
    // empty seed is the ordinary case for `python -m tessellate --desktop`
    // run by hand, and falls back to the one step this process owns.
    window.__mmSeed = [];
    window.__mmTips = [
      "Your notes never leave this machine.",
      "Ctrl+K opens the command palette.",
      "The capture box files a thought for you, in the right place.",
      "The first run installs about 300 MB once. Later starts take seconds.",
      "Your notes live in your own data folder, as plain files you can copy."
    ];

    var mmSteps = window.__mmSeed.slice();
    // The share of the bar the launcher's steps already account for. This
    // process's own phases divide up what is left, so the bar carries on
    // from where the pre-Python splash stopped rather than resetting.
    var mmBase = 0;
    var mmOwn = null;   // the row this process is narrating into

    // Built from DOM nodes rather than an innerHTML string: every title
    // and detail here came out of a shell script by way of a text file,
    // and the project's own lint exists because the next author to touch
    // a line like this interpolates one.
    function mmRender() {
      var list = document.getElementById("steps");
      list.textContent = "";
      for (var i = 0; i < mmSteps.length; i++) {
        var s = mmSteps[i];
        var mark = s.state === "done" ? "\\u2713"
                 : s.state === "failed" ? "\\u00d7"
                 : s.state === "active" ? "\\u25cf" : "\\u25cb";
        var row = document.createElement("li");
        row.className = s.state;
        var tick = document.createElement("span");
        tick.className = "tick";
        tick.textContent = mark;
        var name = document.createElement("span");
        name.className = "name";
        name.textContent = s.title;
        var detail = document.createElement("span");
        detail.className = "detail";
        detail.textContent = s.detail || "";
        row.appendChild(tick);
        row.appendChild(name);
        row.appendChild(detail);
        list.appendChild(row);
      }
    }

    function mmSetup() {
      var done = 0, total = 0;
      for (var i = 0; i < mmSteps.length; i++) {
        if (mmSteps[i].state === "done") done++;
        total = mmSteps[i].total || total;
      }
      if (!total) total = mmSteps.length || 1;
      // The last step is this process: whatever the launcher called it, it
      // is the one still running, so this window narrates into it.
      if (mmSteps.length && mmSteps[mmSteps.length - 1].state !== "done") {
        mmOwn = mmSteps[mmSteps.length - 1];
      } else {
        mmOwn = { step: total, total: total, title: "Start",
                  detail: "Starting the app", state: "active" };
        mmSteps.push(mmOwn);
      }
      mmBase = Math.round(done * 100 / total);
      mmRender();
      document.getElementById("bar").style.width = Math.max(mmBase, 4) + "%";
    }

    // Called from the Python side (window.evaluate_js) as the launcher
    // learns more, not polled from here, see startup_status.py's own
    // docstring for why the loading window can't ask the server itself.
    window.__mmSetStatus = function (text, pct) {
      document.getElementById("status").textContent = text;
      // The row keeps the launcher's own detail for this step and the line
      // below carries the phase inside it. Writing the phase into both put
      // the same sentence on screen twice, one above the other, which reads
      // as a rendering bug rather than as two pieces of information.
      if (mmOwn && mmOwn.state !== "active") {
        mmOwn.state = "active";
        mmRender();
      }
      // pct is this process's own progress through its own phases; the bar
      // shows it inside the slice the launcher's finished steps left.
      var scaled = mmBase + (pct * (100 - mmBase) / 100);
      document.getElementById("bar").style.width = Math.max(scaled, 4) + "%";
    };
    // The last step really does finish, and this is the moment: the server
    // answered and the window is about to be pointed at the app. Without
    // it nothing ever marked the step this process owns as done, so the
    // list closed on four ticks out of five and the bar on 98.4% of its
    // track, every launch, which is the "only ever goes to 3/5 and then it
    // loads" report: not a step that was skipped, a step nobody ticked.
    window.__mmSetDone = function (text) {
      document.getElementById("status").textContent = text;
      if (mmOwn) {
        mmOwn.state = "done";
        mmOwn.detail = text;
        mmRender();
      }
      document.getElementById("bar").style.width = "100%";
    };
    window.__mmSetError = function (text) {
      document.getElementById("status").textContent = text;
      document.getElementById("bar").className = "bar-fill error";
      document.getElementById("bar").style.width = "100%";
      if (mmOwn) {
        mmOwn.state = "failed";
        mmOwn.detail = text;
        mmRender();
      }
    };

    mmSetup();

    // One tip at a time, changed every six seconds, starting at a random
    // one so the same tip is not the only one anybody ever reads. Under
    // reduced motion the fade goes and the text simply swaps.
    var mmTip = document.getElementById("tip");
    var mmTipAt = Math.floor(Math.random() * window.__mmTips.length);
    var mmReduced = window.matchMedia && window.matchMedia("(prefers-reduced-motion: reduce)").matches;
    function mmShowTip() {
      mmTip.textContent = window.__mmTips[mmTipAt % window.__mmTips.length];
      mmTipAt++;
    }
    mmShowTip();
    setInterval(function () {
      if (mmReduced) { mmShowTip(); return; }
      mmTip.style.opacity = "0";
      setTimeout(function () { mmShowTip(); mmTip.style.opacity = "1"; }, 200);
    }, 6000);
  </script>
</body></html>"""


#: The loading page's six colours, per look and mode: ground, text, faint
#: text, secondary text, accent, bar track. The page's own stylesheet is
#: written in the Classic set, which is the fallback for any other palette.
_LOADING_CLASSIC = ("#12141c", "#e7e9ee", "#5d6472", "#9aa1ad", "#4f6df5", "#262b3a")
_LOADING_LOOKS = {
    ("utilitarian", "dark"): ("#161615", "#ecebe8", "#75736e", "#a09e98", "#5b95ff", "#2a2a27"),
    ("utilitarian", "light"): ("#f4f3f1", "#1c1c1a", "#8a8883", "#66645f", "#2f5bd3", "#e3e1dd"),
    ("paper", "dark"): ("#141312", "#f2efe9", "#77726a", "#a49f95", "#ff7a4d", "#2a2826"),
    ("paper", "light"): ("#faf9f6", "#111111", "#8a867e", "#57544e", "#c63d17", "#e6e3dc"),
    ("mono", "dark"): ("#0f1215", "#e6eaee", "#5f6a75", "#8f9aa6", "#42d67f", "#232a31"),
    ("mono", "light"): ("#eceff2", "#15191e", "#7b8591", "#56606b", "#1a7f45", "#d5dae0"),
}
_LOOK_PALETTES = {"utilitarian": "utilitarian", "paper": "paper", "mono": "mono", "default": "default"}


#: The loading page's two raw reduced-motion reads: the stylesheet's block and
#: the tip fade's script. They live here, not in `frontend/`, because the page is
#: shown from `html=` before the app and cannot read the app's `data-motion`.
_LOADING_MOTION_CSS = "@media (prefers-reduced-motion: reduce) {"
_LOADING_MOTION_JS = 'window.matchMedia && window.matchMedia("(prefers-reduced-motion: reduce)").matches'


def _loading_motion(html: str, choice: object) -> str:
    """The loading page under the person's Motion choice (INBOX 1506), which the
    app mirrors to `ui_state` as "follow", "on" or "off" (older words "auto" and
    "reduced" read as follow and off, as `MOTION.choice` in theme-boot.js does).
    "off" holds the page still, "on" keeps it moving whatever the system asks,
    and anything else leaves it following the system's request, as written."""
    if choice == "on":
        return html.replace(_LOADING_MOTION_CSS, "@media not all {").replace(_LOADING_MOTION_JS, "false")
    if choice in ("off", "reduced"):
        return html.replace(_LOADING_MOTION_CSS, "@media all {").replace(_LOADING_MOTION_JS, "true")
    return html


def _recolour_loading_page(html: str, data_dir: str | None) -> str:
    """The loading page in the look the app will open in (owner: "some popup
    ui's havent followed the theme change like the loading screen").

    The page is shown before the app, from `html=`, so it cannot read the
    browser storage the look lives in; the look is mirrored to the server's
    preferences (`ui_state`), which this reads from the data folder. Only the
    page's stylesheet is recoloured; the logo keeps its own colours. Any
    failure leaves the page as written, which is a loading screen in the
    Classic colours rather than no loading screen.
    """
    try:
        from tessellate.core.config import ConfigManager

        state = ConfigManager(data_dir or None).get_preference("ui_state", {}) or {}
    except Exception:  # noqa: BLE001  # a cosmetic read must never stop the launch
        return html
    html = _loading_motion(html, state.get("motion"))
    # The same order as `appearancePref` (settings.js): a palette chosen by
    # hand, then the chosen look's palette, then the default look's.
    preset = state.get("themePreset")
    palette = state.get("palette") or (_LOOK_PALETTES.get(preset, "") if preset else "utilitarian")
    mode = "light" if state.get("theme") == "light" else "dark"
    colours = _LOADING_LOOKS.get((palette, mode))
    if not colours:
        return html
    head, sep, rest = html.partition("</style>")
    if not sep:
        return html
    for old, new in zip(_LOADING_CLASSIC, colours):
        head = head.replace(old, new)
    return head + sep + rest


def _loading_html(steps=None, data_dir: str | None = None) -> str:
    """`_LOADING_HTML` with the launcher's step history seeded into it.

    Read before `_close_launch_splash()` deletes the status file, which is
    the only window in which it exists: see `_run_desktop`. With no
    launcher (someone ran `python -m tessellate --desktop` by hand) there is
    no history, and the page renders the one step this process owns, which
    is exactly what `_LOADING_HTML` already says on its own.
    """
    import json

    if steps is None:
        steps = launch_status.read_file(os.environ.get("MM_SPLASH_FILE"))
    if data_dir is None:
        data_dir = os.environ.get("TESSELLATE_DATA_DIR") or ""

    html = _recolour_loading_page(_LOADING_HTML, data_dir)
    if steps:
        seed = [
            {
                "step": s.step,
                "total": s.total,
                "title": s.title,
                "detail": s.detail,
                "state": s.state,
            }
            for s in launch_status.summarise(steps)
        ]
        html = html.replace("window.__mmSeed = [];", f"window.__mmSeed = {json.dumps(seed)};")
    if data_dir:
        # The last tip names the folder rather than describing it: "where
        # are my notes" is the most-asked question this app has, and the
        # loading window is one of the few places with room to answer it.
        html = html.replace(
            '"Your notes live in your own data folder, as plain files you can copy."',
            json.dumps(f"Your notes live in {data_dir}, as plain files you can copy."),
        )
    return html

# Coarse phase name -> a fixed progress-bar percentage. Real percentages
# aren't knowable, create_app() has no notion of "38% done", but a handful
# of ordered, named phases read as real progress rather than an indeterminate
# spinner, which is what was asked for ("a progress bar with sub text
# showing the action currently being done"). A phase this map doesn't know
# about (core/startup_status.py's own default, or a future phase string
# added there without updating this) still shows as text, just without
# advancing the bar past whatever the last known phase left it at.
_STARTUP_PHASE_PERCENT = {
    "Starting…": 4,
    "Setting up your notebook…": 30,
    "Starting local services…": 55,
    "Warming up search…": 75,
    "Starting the server…": 92,
}


#: Read by `__main__` (imported there).
__all__ = [
    "_STARTUP_PHASE_PERCENT",
]
