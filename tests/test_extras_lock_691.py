"""Every pip extra installs from a hashed lock (L-world-class-691, SECURITY.md T23).

`pip install --require-hashes --no-deps -r <lock>`: nothing PyPI serves goes
in unless its sha256 is in a lock shipped with the app, and no lock pins a
base package, so an extra install can never move numpy or tokenizers under
the running app. pip is faked throughout; scripts/extras_lock.py writes the
locks and one real install is recorded in the CHANGELOG."""

from __future__ import annotations

import re
from pathlib import Path

import pytest

from tessellate.core import extras, extras_lock

ROOT = Path(__file__).resolve().parents[1]
PIP_EXTRAS = [e for e in extras.EXTRAS if e.kind == "pip"]


def _requirements_names() -> set[str]:
    names = set()
    for line in (ROOT / "requirements.txt").read_text(encoding="utf-8").splitlines():
        name = extras._requirement_name(line.split("#")[0].strip())
        if name:
            names.add(extras_lock.canonical(name))
    return names


def _lock_text(extra_id: str) -> str:
    return (extras_lock.LOCKS_DIR / f"{extra_id}.txt").read_text(encoding="utf-8")


@pytest.mark.parametrize("extra", PIP_EXTRAS, ids=lambda e: e.id)
def test_every_pip_extra_has_a_lock_naming_its_packages(extra):
    lock = extras_lock.read(extra.id)
    assert lock is not None, f"no lock for {extra.id}: run scripts/extras_lock.py"
    assert lock.packages == " ".join(extra.packages), f"{extra.id}: regenerate its lock"
    pinned = {extras_lock.canonical(e.name) for e in lock.entries} | {
        extras_lock.canonical(e.name) for e in lock.base
    }
    for package in extra.packages:
        assert extras_lock.canonical(extras._requirement_name(package)) in pinned, f"{extra.id}: {package}"


@pytest.mark.parametrize("extra", PIP_EXTRAS, ids=lambda e: e.id)
def test_every_requirement_line_carries_sha256_hashes(extra):
    lock = extras_lock.read(extra.id)
    assert lock.entries, extra.id
    for entry in lock.entries:
        assert entry.hashes, f"{extra.id}: {entry.name} has no hash"
        for line in entry.hashes:
            assert extras_lock.HASH_LINE.match(line), f"{extra.id}: {line}"
    # Every line that is not a comment is a pin or a hash: no bare names, no
    # index URLs, no `-e` or `-r` that would reach past the hashes.
    for line in _lock_text(extra.id).splitlines():
        line = line.strip().rstrip("\\").strip()
        if line and not line.startswith("#"):
            assert re.match(r"^[A-Za-z0-9][A-Za-z0-9._-]*==\S+", line) or extras_lock.HASH_LINE.match(line), line


@pytest.mark.parametrize("extra", PIP_EXTRAS, ids=lambda e: e.id)
def test_no_lock_pins_a_base_package(extra):
    base = _requirements_names() - {extras_lock.canonical(n) for n in extras_lock.PACKAGED_EXCLUDES}
    for entry in extras_lock.read(extra.id).entries:
        assert extras_lock.canonical(entry.name) not in base, f"{extra.id} pins {entry.name}, a base package"


def test_the_packaged_excludes_are_what_the_specs_leave_out():
    """fastembed is the one requirement both specs exclude; the rest are
    test tools nothing under src imports, so PyInstaller never collects them."""
    for spec in ("windows", "linux"):
        text = (ROOT / "packaging" / spec / "tessellate.spec").read_text(encoding="utf-8")
        assert '"fastembed"' in text.split("excludes=[", 1)[1].split("]", 1)[0], spec
    for name in extras_lock.PACKAGED_EXCLUDES:
        assert extras_lock.canonical(name) in _requirements_names(), name
        if name == "fastembed":
            continue
        module = name.replace("-", "_")
        for path in (ROOT / "src").rglob("*.py"):
            text = path.read_text(encoding="utf-8")
            assert not re.search(rf"^\s*(?:import|from) {module}\b", text, re.M), f"{path} imports {module}"


def test_two_locks_never_pin_one_distribution_differently():
    """--target replaces a folder another extra installed: the same pin
    everywhere keeps one extra from moving another's dependency."""
    seen: dict[tuple[str, str], tuple[str, str]] = {}
    for extra in PIP_EXTRAS:
        for entry in extras_lock.read(extra.id).entries:
            key = (extras_lock.canonical(entry.name), entry.marker)
            if key in seen:
                assert seen[key][0] == entry.version, f"{entry.name}: {seen[key][1]} {seen[key][0]}, {extra.id} {entry.version}"
            else:
                seen[key] = (entry.version, extra.id)


def test_split_and_render_round_trip():
    compiled = (
        "numpy==2.5.5 ; python_full_version >= '3.12' \\\n    --hash=sha256:" + "a" * 64 + "\n"
        "pillow==13.0.0 \\\n    --hash=sha256:" + "b" * 64 + " \\\n    --hash=sha256:" + "c" * 64 + "\n"
    )
    new, base = extras_lock.split(compiled, {"numpy"})
    lock = extras_lock.parse(extras_lock.render("x", ("Pillow",), new, base))
    assert [(e.name, e.version, len(e.hashes)) for e in lock.entries] == [("pillow", "13.0.0", 2)]
    assert [(e.name, e.marker) for e in lock.base] == [("numpy", "python_full_version >= '3.12'")]
    assert lock.packages == "Pillow"


# --- the install --------------------------------------------------------------


class _Capture:
    seen: dict = {}

    def __init__(self, command, **kwargs):
        # Read the selection now: the install's cleanup deletes pip's temp folder.
        requirement = Path(command[command.index("-r") + 1])
        _Capture.seen = {"command": command, "lock": requirement.read_text(encoding="utf-8")}
        self.stdout = []

    def wait(self):
        return 0


def _installed(monkeypatch, versions: dict[str, str]) -> None:
    monkeypatch.setattr(extras, "_installed_version", lambda name: versions.get(extras_lock.canonical(name)))


def _base_present(extra_id: str) -> dict[str, str]:
    return {extras_lock.canonical(e.name): e.version for e in extras_lock.read(extra_id).base}


@pytest.fixture
def fake_pip(client, monkeypatch):
    monkeypatch.setattr(extras, "_pip_base_command", lambda: ["pip"])
    monkeypatch.setattr(extras.subprocess, "Popen", _Capture)
    _Capture.seen = {}
    return _Capture


def test_pip_gets_the_lock_with_require_hashes_and_no_deps(fake_pip, monkeypatch):
    _installed(monkeypatch, _base_present("voice"))
    extras._run_install(extras.EXTRAS_BY_ID["voice"])
    command = fake_pip.seen["command"]
    assert "--require-hashes" in command and "--no-deps" in command
    assert "faster-whisper" not in command  # never a bare name pip would resolve itself
    assert "faster-whisper==" in fake_pip.seen["lock"]
    assert "--hash=sha256:" in fake_pip.seen["lock"]
    assert extras.current().outcome == "completed"


def test_an_installed_distribution_is_left_where_it_is(fake_pip, monkeypatch):
    """fastembed's onnxruntime in a source install: the voice lock pins its
    own, and installing that would move it under search by meaning."""
    lock = extras_lock.read("voice")
    onnx = next(e for e in lock.entries if e.name == "onnxruntime")
    _installed(monkeypatch, {**_base_present("voice"), "onnxruntime": "0.0.1"})
    extras._run_install(extras.EXTRAS_BY_ID["voice"])
    assert "onnxruntime==" not in fake_pip.seen["lock"]
    assert any("onnxruntime 0.0.1" in line and onnx.version in line for line in extras.current().log)


def test_a_missing_base_package_refuses_before_pip(fake_pip, monkeypatch):
    present = _base_present("voice")
    present.pop("numpy")
    _installed(monkeypatch, present)
    extras._run_install(extras.EXTRAS_BY_ID["voice"])
    assert fake_pip.seen == {}
    assert extras.current().outcome == "failed"
    assert "numpy" in extras.current().step and "requirements.txt" in extras.current().step


def test_an_extra_with_no_lock_refuses_rather_than_install_unchecked(fake_pip, monkeypatch, tmp_path):
    monkeypatch.setattr(extras_lock, "LOCKS_DIR", tmp_path)
    extras._run_install(extras.EXTRAS_BY_ID["pdfpages"])
    assert fake_pip.seen == {}
    assert extras.current().outcome == "failed"
    assert "checked" in extras.current().step


def test_the_frozen_build_installs_the_whole_lock(fake_pip, monkeypatch, tmp_path):
    """--target is the extras folder alone: nothing there is the bundle's, and
    the bundle's own packages are never visible to the system pip."""
    monkeypatch.setattr(extras, "frozen_extras_dir", lambda: tmp_path)
    _installed(monkeypatch, {"onnxruntime": "0.0.1"})
    extras._run_install(extras.EXTRAS_BY_ID["voice"])
    command = fake_pip.seen["command"]
    assert "--target" in command and "--require-hashes" in command and "--no-deps" in command
    for entry in extras_lock.read("voice").entries:
        assert f"{entry.name}=={entry.version}" in fake_pip.seen["lock"]
