"""INBOX 1637: a Tessellate that holds the port and does not answer (just
closed and still shutting down, or hung) was reported as "Port 8000 is already
in use by another program". The launchers now tell their own copy from another
program, wait for it, and offer to stop it on a keypress; the desktop app's
second double-click brings the window forward instead of a browser tab."""

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
BAT = (ROOT / "start.bat").read_text(encoding="utf-8")
SH = (ROOT / "start.sh").read_text(encoding="utf-8")


def test_bat_reads_the_listening_pid():
    bat = BAT.replace("\r\n", "\n")
    check = bat[bat.index("\n:port_check\n"):bat.index("\n:port_pid_is_ours\n")]
    assert "netstat -ano" in check and 'tokens=5' in check and "MM_PORT_PID" in check


def test_bat_only_waits_for_and_stops_its_own_copy():
    bat = BAT.replace("\r\n", "\n")
    ours = bat[bat.index("\n:port_pid_is_ours\n"):bat.index("\n:port_stop_stuck\n")]
    assert "instance.lock" in ours and '/C:"tessellate"' in ours
    check = bat[bat.index("\n:port_check\n"):bat.index("\n:port_pid_is_ours\n")]
    # Another program is never waited for: the wait sits behind the ours check.
    assert check.index("call :port_pid_is_ours") < check.index("MM_PORT_WAITS+=1")
    assert "if not defined MM_PORT_OURS exit /b 0" in check


def test_bat_asks_before_stopping_and_cancels_by_default():
    bat = BAT.replace("\r\n", "\n")
    stop = bat[bat.index("\n:port_stop_stuck\n"):bat.index("\n:port_stop_wait\n")]
    assert "choice /C SC /N /T 60 /D C" in stop
    assert stop.index("choice") < stop.index("taskkill /PID !MM_PORT_PID!")
    assert "MM_PORT_CANCELLED=1" in stop
    pre = bat[bat.index("--- Preflight"):bat.index(":preflight_disk_done")]
    assert pre.index("call :port_stop_stuck") < pre.index("goto :already_running")
    assert "if defined MM_PORT_CANCELLED goto :cancelled" in pre


def test_bat_desktop_double_click_focuses_the_window_not_a_tab():
    bat = BAT.replace("\r\n", "\n")
    running = bat[bat.index("\n:already_running\n"):bat.index("\n:cancelled\n")]
    assert running.index("-m tessellate --desktop") < running.index('start "" "!MM_URL!"')


def test_bat_keeps_crlf_and_no_em_dash():
    raw = (ROOT / "start.bat").read_bytes()
    assert b"\r\n" in raw and b"\n" not in raw.replace(b"\r\n", b"")
    assert "\u2014" not in BAT and "\u2014" not in SH


def test_sh_waits_for_its_own_copy_and_asks_before_stopping():
    start = SH.index("A Tessellate that holds the port")
    pre = SH[start:SH.index('mm_fail "Port $MM_PORT is already in use', start)]
    assert "mm_lock_pid" in pre and "read -r -t 60" in pre
    assert pre.index("read -r -t 60") < pre.index('kill "$MM_STUCK_PID"')
    assert "mm_lock_pid()" in SH and "kill -0" in SH


def test_health_answers_on_the_event_loop():
    """A sync /health waits for a worker thread; slow routes holding every
    thread made a busy copy look like another program."""
    app = (ROOT / "src/tessellate/api/app.py").read_text(encoding="utf-8")
    i = app.index('@app.get("/health"')
    assert "async def health(" in app[i:i + 120]
