"""Run SearXNG as a Docker container.

Split out of `searxng_manager.py` (see that module for the two backends and
why Docker is only the tidier one). Everything here is the docker-cli side of
it: is Docker there and its daemon up, create/start/stop the
`memorymap-searxng` container, and the loopback-only publishing rule (and the
guard that re-creates a container an earlier version published to every
interface, since publishing is fixed at container creation and `docker start`
can't change it).
"""

from __future__ import annotations

import logging
import shutil
import subprocess
import time
from pathlib import Path

from tessellate.core.subproc import NO_WINDOW
from tessellate.search import searxng_manager, websearch
from tessellate.search.searxng_manager import (
    START_TIMEOUT,
    SearxngError,
    _reason,
    base_url,
    host_port,
)
from tessellate.search.searxng_settings import ensure_settings

# `_run`, `_wait_until_ready` and `docker_installed` (the last one, called
# from `docker_available` just below, is defined in this very file) are
# deliberately not used as bare names anywhere below: the test suite
# monkeypatches all three as `searxng_manager.<name>`, which only rebinds
# that attribute on the `searxng_manager` module object. Going through
# `searxng_manager.<name>` looks each one up fresh, so a patched or a real
# implementation is picked up exactly as it was when this was one file.

CONTAINER_NAME = "memorymap-searxng"
IMAGE = "searxng/searxng:latest"

# `docker info` against a stopped daemon is quick to fail, but give it room on
# a cold Docker Desktop rather than calling a slow start "not running".
DAEMON_PROBE_TIMEOUT = 8

#: How long `docker_available()` trusts its last answer. Short, because the
#: thing it describes is someone opening or quitting Docker Desktop and the
#: badge that reports it should not lie for long; long enough that a status
#: poll every two seconds does not mean a process spawn every two seconds.
DAEMON_PROBE_TTL = 15.0

#: The remembered answer. `None` means "nothing known", which is also what
#: `forget_docker_daemon_state()` puts back.
_daemon_probe: dict[str, object] = {"answer": None, "at": 0.0}


def docker_installed() -> bool:
    """Is the docker command on PATH? Says nothing about the daemon."""
    return shutil.which("docker") is not None


def docker_available() -> bool:
    """Can we actually run a container right now?

    Checking only that the binary exists was wrong, and produced exactly the
    failure it should have prevented: with Docker Desktop installed but not
    started, the app picked the Docker backend, tried to create a container,
    and reported "failed to connect to the docker API at npipe:...", while
    the from-source backend that would have worked was never considered.

    `docker info` is the cheapest question that means "is the daemon up".

    Cheap is relative, though: it is a process spawn, and against a *stopped*
    Docker Desktop it is a process spawn that takes until
    `DAEMON_PROBE_TIMEOUT`. `status()` asks this on every call and the web
    search strip re-asks `status()` every two seconds while an install
    settles, so the honest description of the old behaviour is "spawn
    `docker info` twice a second and block a threadpool worker for up to
    eight seconds each time, to re-learn something that changes when
    somebody opens an application". Hence the short memory below.
    """
    if not searxng_manager.docker_installed():
        return False
    fresh = _daemon_probe["answer"] is not None and (
        time.monotonic() - _daemon_probe["at"] < DAEMON_PROBE_TTL
    )
    if fresh:
        return _daemon_probe["answer"]
    try:
        result = subprocess.run(  # noqa: S603  # fixed args, no shell
            ["docker", "info", "--format", "{{.ServerVersion}}"],
            capture_output=True,
            text=True,
            timeout=DAEMON_PROBE_TIMEOUT,
            check=False,
            creationflags=NO_WINDOW,
        )
    except subprocess.TimeoutExpired:
        # A daemon that does not answer in `DAEMON_PROBE_TIMEOUT` is an answer,
        # and remembered: asking again at once spent another eight seconds.
        _daemon_probe["answer"] = False
        _daemon_probe["at"] = time.monotonic()
        return False
    except (OSError, subprocess.SubprocessError):
        # Not remembered. This arm is "docker could not be run at all", which
        # is the answer most likely to be wrong in a moment (a daemon that is
        # starting up), and it is the cheap one to repeat: it failed without
        # waiting for the timeout.
        return False
    answer = result.returncode == 0
    _daemon_probe["answer"] = answer
    _daemon_probe["at"] = time.monotonic()
    return answer


def forget_docker_daemon_state() -> None:
    """Drop the remembered answer, for the moments that change it.

    Called wherever the app itself acts on Docker (an install, a start, a
    stop): those are exactly the points where waiting up to
    `DAEMON_PROBE_TTL` to notice would show a stale badge right after a
    button press, which is the one place the staleness would be visible.
    """
    _daemon_probe["answer"] = None


def _docker_state() -> str:
    """'running', 'stopped', or 'absent' for our container."""
    result = searxng_manager._run(
        ["docker", "ps", "-a", "--filter", f"name=^{CONTAINER_NAME}$", "--format", "{{.State}}"]
    )
    state = (result.stdout or "").strip().splitlines()
    if not state:
        return "absent"
    return "running" if state[0].strip() == "running" else "stopped"


def _publish_spec() -> str:
    """The -p argument, pinned to the loopback interface.

    `-p 8888:8080` publishes on EVERY interface, which is not what the plain
    reading suggests and is the one place the docker path disagreed with the
    source path: that one sets SEARXNG_BIND_ADDRESS=127.0.0.1 and is reachable
    only from this machine. Docker also writes its own iptables rules, so a
    published port is reachable from the LAN even behind a host firewall that
    is set to refuse it, the firewall never sees the packet. Naming the
    interface is the whole fix.

    It matters here more than the port number suggests. SearXNG is an open
    proxy to the wider internet with no auth in front of it, and its /search
    endpoint takes the query as a GET parameter, so an exposed instance is
    both something a stranger on the café wifi can run searches through and a
    log of everything the owner has searched for.
    """
    return f"127.0.0.1:{host_port()}:8080"


def _docker_publishes_beyond_localhost() -> bool:
    """Does the existing container publish to the world rather than loopback?

    Port publishing is fixed when a container is CREATED, so changing the
    `docker run` above only protects people who have never started SearXNG.
    Anyone who ran an earlier version already has a container published on
    0.0.0.0, and `docker start` would keep it that way forever. This is what
    tells `_start_docker` to replace it instead.
    """
    result = searxng_manager._run(
        [
            "docker", "inspect", CONTAINER_NAME,
            "--format", "{{range $p, $conf := .HostConfig.PortBindings}}" +
                        "{{range $conf}}{{.HostIp}}\n{{end}}{{end}}",
        ]
    )
    if result.returncode != 0:
        return False  # can't tell: don't destroy a container on a guess
    bindings = [line.strip() for line in (result.stdout or "").splitlines()]
    bindings = [line for line in bindings if line]
    if not bindings:
        # No host IP recorded at all means "all interfaces", the same default
        # the bare `-p 8888:8080` form produces.
        return True
    return any(
        host_ip in ("", "0.0.0.0", "::") or not host_ip.startswith(("127.", "::1"))
        for host_ip in bindings
    )


def _remove_container() -> None:
    """Drop the container so the next start recreates it. Data is not lost:
    SearXNG keeps nothing we care about inside it, the settings file lives on
    the host and is mounted in."""
    searxng_manager._run(["docker", "rm", "-f", CONTAINER_NAME], timeout=40)


def _start_docker(data_dir: Path) -> dict:
    """Start (or create) the container and wait until it answers JSON."""
    # Refreshed for every path, not only creation: the container mounts this
    # host file, so a stopped container restarted with stale settings would
    # keep old engine defaults forever, the exact staleness rewrite-on-start
    # exists to end.
    settings = ensure_settings(data_dir)
    state = _docker_state()
    # A container an earlier version created is published on every interface,
    # and no amount of starting it changes that, publishing is set at create
    # time. Replace it rather than hand back a LAN-visible search proxy.
    if state != "absent" and _docker_publishes_beyond_localhost():
        logging.getLogger("tessellate.searxng").info(
            "Recreating the SearXNG container: it was published on all "
            "interfaces, and it should only be reachable from this machine."
        )
        _remove_container()
        state = "absent"
    if state == "running":
        if websearch.probe_searxng(base_url()):
            return {"url": base_url(), "started": False}
    elif state == "stopped":
        result = searxng_manager._run(["docker", "start", CONTAINER_NAME])
        if result.returncode != 0:
            raise SearxngError(_reason(result, "Couldn't start the existing container."))
    else:
        result = searxng_manager._run(
            [
                "docker", "run", "-d",
                "--name", CONTAINER_NAME,
                "--restart", "unless-stopped",
                "-p", _publish_spec(),
                "-v", f"{settings}:/etc/searxng/settings.yml:ro",
                "-e", f"SEARXNG_BASE_URL={base_url()}/",
                IMAGE,
            ],
            timeout=START_TIMEOUT,
        )
        if result.returncode != 0:
            raise SearxngError(_reason(result, "Couldn't create the container."))

    if not searxng_manager._wait_until_ready():
        raise SearxngError(
            "SearXNG started but isn't answering yet. Give it a moment and press "
            "Auto-detect."
        )
    return {"url": base_url(), "started": True}
