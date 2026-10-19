"""The launcher's pre-Python splash, and its handoff to the app window.

Reported directly: the work start.bat does before Python exists, the git
pull, building .venv, a pip install that can run to minutes, leaves nothing
on screen, so *"the user doesn't think the application didn't start properly
because they didn't have access to the terminal logs"*.

The splash itself is a PowerShell/WinForms window and cannot be exercised
here. What is testable, and what actually breaks, is the contract between the
three pieces: the launcher creates a status file, the splash watches it, and
this process deletes it at exactly the right moment. A splash that is never
closed is worse than no splash, it is a borderless always-on-top window with
no owner, sitting over the app.
"""

from __future__ import annotations

import os
import re
from pathlib import Path

from tessellate import __main__ as launcher

REPO = Path(__file__).resolve().parents[1]


def test_closing_the_splash_deletes_the_file_the_launcher_named(tmp_path, monkeypatch):
    marker = tmp_path / "splash.txt"
    marker.write_text("Installing dependencies...")
    monkeypatch.setenv("MM_SPLASH_FILE", str(marker))

    launcher._close_launch_splash()

    assert not marker.exists()


def test_closing_the_splash_twice_is_not_an_error(tmp_path, monkeypatch):
    """The launcher deletes it on its own way out too, so a double delete is
    an ordinary race rather than a fault."""
    marker = tmp_path / "splash.txt"
    marker.write_text("x")
    monkeypatch.setenv("MM_SPLASH_FILE", str(marker))

    launcher._close_launch_splash()
    launcher._close_launch_splash()  # must not raise


def test_no_splash_running_is_not_an_error(monkeypatch):
    """Browser mode, a machine with no PowerShell, or a locked-down execution
    policy all reach this with the variable unset."""
    monkeypatch.delenv("MM_SPLASH_FILE", raising=False)
    launcher._close_launch_splash()


def test_an_unwritable_path_does_not_stop_the_launch(monkeypatch):
    monkeypatch.setenv("MM_SPLASH_FILE", os.path.join(os.sep, "nope", "nope.txt"))
    launcher._close_launch_splash()


# --- the launcher's half of the contract ---------------------------------------


def _start_bat() -> str:
    return (REPO / "start.bat").read_text(encoding="utf-8", errors="replace")


def test_the_launcher_opens_the_splash_before_any_slow_work():
    """It has to go up before the git pull, not after, the whole point is the
    seconds-to-minutes before anything else appears."""
    text = _start_bat()
    # The invocation, not the comment above it that also names the file.
    splash_at = text.index("start \"\" /b powershell")
    assert splash_at < text.index("git -c http.lowSpeedLimit")
    assert splash_at < text.index("pip install -r requirements.txt")


def test_every_exit_path_takes_the_splash_down():
    """A window with no owner left on the desktop is the failure that matters."""
    text = _start_bat()
    # Browser mode closes it itself; the end-of-script backstop covers the
    # error paths that fall through.
    assert text.count('del /q "!MM_SPLASH_FILE!"') >= 2
    tail = text[text.index("Tessellate has stopped") - 700 :]
    assert 'del /q "!MM_SPLASH_FILE!"' in tail


def test_the_child_process_does_not_open_a_second_splash():
    """start.bat re-launches itself after a self-update. The child inherits
    MM_SPLASH_FILE and must write to the window the parent already opened."""
    text = _start_bat()
    launch = text.index("start \"\" /b powershell")
    # The guard grew a second condition when the flag parser landed (Brief
    # 17): --doctor and friends print a table and exit, so they get no
    # splash either. Both conditions sit on the one IF that opens the block.
    guard = text.rindex("if not defined MM_CHILD ", 0, launch)
    assert guard < launch
    assert text[guard : text.index("\n", guard)].rstrip().endswith("(")


def test_the_phases_the_splash_reports_are_the_slow_ones():
    # The splash file stopped being one line of plain text when the
    # step|total|title|detail|state protocol landed (Brief 17): every phase
    # now goes through `call :status`, which is the only writer.
    written = set(re.findall(r'call :status \S+ "([^"]+)" "([^"]+)"', _start_bat()))
    blob = " ".join(part for pair in written for part in pair).lower()
    assert "update" in blob        # git pull
    assert "dependencies" in blob  # pip install, the long one
    assert "starting the app" in blob


def test_the_splash_script_can_always_give_up_on_its_own():
    """The one case the launcher cannot clean up after: killed outright, so
    nothing deletes the file. Three independent exits, all present."""
    ps1 = (REPO / "scripts" / "splash.ps1").read_text(encoding="utf-8")
    assert "MaxMinutes" in ps1                     # a hard deadline
    assert "Test-Path -LiteralPath $StatusFile" in ps1  # the file vanished
    assert "__done__" in ps1                       # an explicit stop
    # And it must never take the launch down with it.
    assert "catch {" in ps1 and "exit 0" in ps1


# --- the Unix launcher ---------------------------------------------------------


def _start_sh() -> str:
    return (REPO / "start.sh").read_text(encoding="utf-8")


def test_the_unix_splash_only_appears_when_there_is_no_terminal():
    """Run from a terminal, start.sh already narrates every phase, a dialog
    over the top would be noise. The report is about launching from a file
    manager, where there is no console at all."""
    text = _start_sh()
    # The gate moved into a variable when the flag parser landed (Brief 17):
    # MM_TTY is read once from `-t 1`, and the zenity branch checks it, so
    # `--help` can be answered before any splash exists.
    assert "MM_TTY=0" in text and "[ -t 1 ] && MM_TTY=1" in text
    assert '[ "$MM_TTY" = "0" ]' in text and "command -v zenity" in text


def test_both_exec_paths_take_the_unix_splash_down_by_hand():
    """`exec` replaces the shell without firing the EXIT trap, and fd 9 is
    inherited by the new process, which would hold the fifo open and leave
    zenity on screen for the whole life of the app."""
    text = _start_sh()
    for exec_line in ('exec "$VENV_PY" -m tessellate --desktop',
                      'exec "$VENV_PY" -m tessellate\n'):
        at = text.index(exec_line)
        before = text[max(0, at - 200):at]
        assert "mm_splash_done" in before, exec_line


def test_the_unix_splash_is_trapped_on_every_signal():
    assert "trap mm_splash_done EXIT INT TERM" in _start_sh()


def test_a_machine_without_zenity_or_osascript_just_gets_no_splash():
    """Every call must be a no-op when neither dialog mechanism started, or a
    missing zenity/osascript would take the launch down with it. `mm_splash`
    branches on $MM_SPLASH_MODE with a `case`; leaving it unset (neither
    branch matched at setup) means every call falls through with no match, 
    the shell equivalent of the early-return guard this replaced."""
    text = _start_sh()
    body = text[text.index("mm_splash() {") : text.index("mm_splash_done() {")]
    assert 'case "$MM_SPLASH_MODE" in' in body
    assert 'MM_SPLASH_MODE=""' in text  # the default before either branch can set it


def test_macos_gets_a_non_modal_notification_not_a_dialog():
    """Asked for directly: an equivalent splash for Linux (already had one,
    zenity) and macOS. `display dialog` steals focus and needs a click to
    dismiss: not worth it for a cosmetic splash, which is why this was
    skipped before. `display notification` is the native banner that does
    neither, so it's the one worth adding."""
    text = _start_sh()
    assert 'uname)" = "Darwin"' in text
    assert "command -v osascript" in text
    body = text[text.index("mm_splash() {") : text.index("mm_splash_done() {")]
    assert "display notification" in body
    assert "display dialog" not in body


def test_the_notification_text_is_applescript_escaped_not_shell_escaped():
    """A phase string reaching AppleScript unescaped could end its string
    literal early on a stray quote or backslash and corrupt the script
    osascript runs, rather than just failing to show a cosmetic banner."""
    text = _start_sh()
    body = text[text.index("mm_splash() {") : text.index("mm_splash_done() {")]
    notify = body[body.index("notify)") : body.index("esac")]
    assert 'sed' in notify and '\\\\"' in notify  # escapes both \ and "


def test_notify_mode_needs_no_cleanup():
    """Each notification fires and clears on its own, nothing is left
    running for mm_splash_done to own or kill, unlike zenity's live dialog
    process."""
    text = _start_sh()
    done_body = text[text.index("mm_splash_done() {") : text.index("trap mm_splash_done")]
    assert "notify" not in done_body


def test_the_bar_is_one_accent_panel_not_a_themed_progressbar():
    """Reported: a green bar and a white one. A stock ProgressBar takes the
    system theme and ignores ForeColor once themed, so the bar is two panels
    in the app accent (Brief 85)."""
    ps1 = (REPO / "scripts" / "splash.ps1").read_text(encoding="utf-8")
    assert "System.Windows.Forms.ProgressBar" not in ps1
    assert "$barFill.BackColor = $accent" in ps1
    assert "$accent = [System.Drawing.Color]::FromArgb(79, 109, 245)" in ps1  # #4f6df5


# --- the handoff window's own last step ----------------------------------------


def test_the_loading_window_can_tick_the_step_it_owns():
    """Reported: the bar "only ever goes to steps 3/5 and then it loads".

    Measured against the real launcher's status file (a warm desktop start
    writes five steps and only four of them ever reach `done`), the seeded
    loading window opened on four ticks and a bar at 80% of its track, ran
    to 98.4% as `startup_status`'s phases arrived, and was replaced by the
    app without the fifth step ever being ticked. Nothing was skipped: the
    step that finishes last is the one this process owns, and nothing
    finished it.
    """
    assert "window.__mmSetDone" in launcher._LOADING_HTML


def test_the_last_step_is_ticked_before_the_window_swaps_not_after():
    """After `load_url` the loading page no longer exists, so a tick there
    would land on a page nobody can see."""
    import inspect

    # Past the docstring, which names load_url in prose.
    src = inspect.getsource(launcher._boot_and_swap)
    body = src[src.index('os.environ["TESSELLATE_DESKTOP"]') :]
    assert body.index("_mark_start_step_done(window)") < body.index("window.load_url(")


def test_ticking_the_last_step_never_takes_the_launch_down():
    """Same contract as every other optional pywebview call in this file:
    a window someone closed mid-startup must not stop the swap."""
    import inspect

    body = inspect.getsource(launcher._mark_start_step_done)
    assert "try:" in body and "except Exception" in body


def test_browser_mode_ticks_the_final_step_and_desktop_mode_leaves_it_alone():
    """In desktop mode __main__.py's loading window inherits the same status
    file and owns the Start step until the server answers, so a tick in the
    launcher would put two Starts in one list. In browser mode nothing else
    narrates it, and leaving it `active` is why the splash, the terminal and
    the log all ended one step short of their own total.
    """
    sh = _start_sh()
    tail = sh[sh.index("Nothing else is coming in browser mode") - 900 :]
    assert 'mm_status "$MM_STEP_START" "Start" "Handed over to the app" "done"' in tail
    # And not on the desktop path, which hands the file to Python instead.
    desktop = sh[sh.index('mm_status "$MM_STEP_START" "Start" "Starting the app" "active"') :
                 sh.index('exec "$VENV_PY" -m tessellate --desktop')]
    assert '"done"' not in desktop

    bat = _start_bat()
    browser_tail = bat[bat.index("No second window is coming in browser mode") - 900 :]
    assert 'call :status !MM_STEP_START! "Start" "Handed over to the app" "done"' in browser_tail


def test_the_entry_module_does_not_drag_the_whole_app_in_with_it():
    """Nothing on screen until the imports finish, and they were the slow part.

    `--desktop` puts its window up before the server thread starts, precisely
    so someone with no console (the packaged build has none) sees something
    happening. But `main()` cannot run until Python has finished importing the
    module that defines it, and that module used to import
    `tessellate.api.app`, which imports FastAPI, SQLAlchemy, the model manager
    and the embeddings module. Measured with `-X importtime` on a warm cache:
    1,203ms to import `tessellate.__main__`, of which `tessellate.api.app` was
    1,113ms. 30ms once those two imports moved into `_run_server`, where the
    work is wanted and where it happens on the server thread, behind the
    window instead of in front of it.

    A packaged Windows build pays that wait worse than this measurement does,
    off disk through whatever is scanning it, and with no terminal to show
    that anything is happening: reported as the launcher's splash not
    appearing at all. So this is a startup budget, not a tidiness rule, and it
    is checked in a subprocess with a cold `sys.modules` because an
    in-process check would find whatever the rest of the suite had already
    imported.
    """
    import subprocess
    import sys

    probe = (
        "import sys; import tessellate.__main__; "
        "print(','.join(sorted(m for m in ('tessellate.api.app', 'uvicorn', "
        "'fastapi', 'sqlalchemy') if m in sys.modules)))"
    )
    root = Path(__file__).resolve().parents[1]
    env = dict(os.environ, PYTHONPATH=str(root / "src"))
    out = subprocess.run(
        [sys.executable, "-c", probe],
        capture_output=True,
        text=True,
        env=env,
        check=True,
    ).stdout.strip()
    assert not out, (
        "importing tessellate.__main__ pulled in " + out + ": import these "
        "inside _run_server instead, so the desktop window can open first"
    )


def test_the_loading_page_wears_the_saved_look(tmp_path):
    """Owner: "some popup ui's havent followed the theme change like the
    loading screen". The desktop loading page reads the look mirrored to the
    server's preferences and recolours its own stylesheet."""
    from tessellate import __main__ as main
    from tessellate.core.config import ConfigManager

    fresh = main._recolour_loading_page(main._LOADING_HTML, str(tmp_path))
    assert "#161615" in fresh.split("</style>")[0]  # no look chosen: Quiet
    assert "#12141c" not in fresh.split("</style>")[0]

    ConfigManager(str(tmp_path)).set_preference("ui_state", {"themePreset": "default"})
    classic = main._recolour_loading_page(main._LOADING_HTML, str(tmp_path))
    assert classic == main._LOADING_HTML

    ConfigManager(str(tmp_path)).set_preference("ui_state", {"themePreset": "mono", "theme": "light"})
    mono = main._recolour_loading_page(main._LOADING_HTML, str(tmp_path))
    assert "#eceff2" in mono.split("</style>")[0]
    # The logo's own colours are untouched.
    assert mono.split("</style>")[1] == main._LOADING_HTML.split("</style>")[1]


def test_the_splash_has_minimise_and_close_in_its_top_right_corner():
    """INBOX 1320: "I want a minimise and close x button in the top right
    corner to cancel or minimise the launch". Close asks the launcher to stop
    (the Cancel link's own `.cancel` file) and closes the window."""
    text = (REPO / "scripts" / "splash.ps1").read_text(encoding="utf-8")
    assert 'New-CornerButton ([string][char]0x2013) ($WIDTH - 76) "Minimise"' in text
    assert '$btnMin.Add_Click({ $form.WindowState = "Minimized" })' in text
    close = text[text.index("$btnClose.Add_Click({"):][:400]
    assert '($StatusFile + ".cancel")' in close and "$form.Close()" in close
    assert "$btnMin, $btnClose))" in text
