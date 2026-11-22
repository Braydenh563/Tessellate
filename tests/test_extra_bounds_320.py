"""Every pip extra installs within version bounds (L-world-class-320, T23).

An install used to take PyPI's newest release of each extra that day, so a
breaking or hijacked major landed on the next press of Install. The bounds go
to pip as constraints beside requirements.txt's, so `packages` stay names (the
uninstall and the import check read them as names)."""

from __future__ import annotations

import re

from tessellate.core import extras

_BOUND = re.compile(r"^([A-Za-z0-9_.-]+)(?:>=[0-9.]+,<[0-9.]+|==[0-9.]+)$")


def _bounded_names() -> set[str]:
    lines = [*extras.EXTRA_BOUNDS]
    requirements = extras._requirements_path().read_text(encoding="utf-8")
    lines.extend(line.split("#")[0].strip() for line in requirements.splitlines())
    names = set()
    for line in filter(None, lines):
        match = _BOUND.match(extras._REQUIREMENT_EXTRAS_RE.sub("", line))
        if match:
            names.add(extras._canonical(match.group(1)))
    return names


def test_every_bound_has_a_floor_and_a_cap():
    for line in extras.EXTRA_BOUNDS:
        assert _BOUND.match(line), line


def test_every_pip_extra_is_bounded():
    bounded = _bounded_names()
    for extra in extras.EXTRAS:
        if extra.kind != "pip":
            continue
        for package in extra.packages:
            if "==" in package:
                continue
            assert extras._canonical(extras._requirement_name(package)) in bounded, f"{extra.id}: {package}"


def test_the_bounds_reach_pip_even_without_requirements_txt(client, monkeypatch, tmp_path):
    """The packaged app's bundle may lack requirements.txt; its installs used
    to go in unconstrained."""
    seen = {}

    class _Capture:
        def __init__(self, command, **kwargs):
            seen["text"] = extras.Path(command[command.index("-c") + 1]).read_text(encoding="utf-8")
            self.stdout = []

        def wait(self):
            return 0

    monkeypatch.setattr(extras, "_requirements_path", lambda: tmp_path / "absent.txt")
    monkeypatch.setattr(extras, "_pip_base_command", lambda: ["pip"])
    monkeypatch.setattr(extras.subprocess, "Popen", _Capture)
    extras._run_install(extras.EXTRAS_BY_ID["voice"])
    assert "faster-whisper>=1.2,<2" in seen["text"].splitlines()
