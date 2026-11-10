"""Bundles of optional extras, and installing, removing or reinstalling
several at once (INBOX 595).

The owner, 2026-10-05: "should we bundle multiple packages together for bulk
download if various features need multiple libraries ... with the ability to
install/uninstall/reinstall individual ones or in bulk??" Decision: yes.

What these pin:

- a bundle is a named list of entries from the allowlist, defined once in
  `core/extras.py`, and the catalogue (`GET /extras`) carries them;
- a bulk action is one job on the pool (`core/jobs.py`), never a thread, and
  walks its packages in the order asked, one at a time;
- one package failing never stops the ones after it, and each one reports
  its own outcome and sentence;
- a reinstall is pip's `--force-reinstall` through the same runner, per
  extra and in bulk;
- the request still names allowlist ids only: a package spec in a bulk body
  is refused like one in a single install's path.

Nothing here runs pip: `subprocess.Popen` is a fake that records the command.
"""

from __future__ import annotations

import re
from pathlib import Path

import pytest

from tessellate.api import routes_tasks
from tessellate.core import extras, jobs
from tests._js_scope import unwrapped


@pytest.fixture(autouse=True)
def _clean_extras():
    extras.reset_for_tests()
    yield
    extras.reset_for_tests()


class _FakePip:
    """`subprocess.Popen` for pip: records each command, and fails the ones
    naming a package in `failing`."""

    commands: list[list[str]] = []
    failing: set[str] = set()

    def __init__(self, command, **kwargs):
        type(self).commands.append(list(command))
        self._code = 1 if any(name in command for name in type(self).failing) else 0
        self.stdout = ["ERROR: No matching distribution found"] if self._code else ["Successfully installed"]

    def wait(self):
        return self._code

    def terminate(self):
        pass


@pytest.fixture
def fake_pip(monkeypatch):
    _FakePip.commands = []
    _FakePip.failing = set()
    monkeypatch.setattr(extras.subprocess, "Popen", _FakePip)
    # The pool runs the job inline here, so a test reads the outcome on the
    # next line; that the real dispatch is the pool is its own test below.
    monkeypatch.setattr(extras, "_dispatch", lambda func, *args, name="": func(*args))
    monkeypatch.setattr(extras, "frozen_extras_dir", lambda: None)
    return _FakePip


def _installed(monkeypatch, ids):
    monkeypatch.setattr(extras, "is_installed", lambda extra: extra.id in ids)


def _pip_packages(command):
    """The package names a recorded pip command was given."""
    start = command.index("install") + 1 if "install" in command else command.index("uninstall") + 1
    return [part for part in command[start:] if not part.startswith("-") and not part.endswith(".txt")]


# --- the catalogue ----------------------------------------------------------


def test_every_bundle_names_entries_of_the_allowlist():
    for bundle in extras.BUNDLES:
        assert bundle.extras, bundle.id
        for extra_id in bundle.extras:
            assert extra_id in extras.EXTRAS_BY_ID, (bundle.id, extra_id)
        assert len(set(bundle.extras)) == len(bundle.extras), bundle.id


def test_the_bundles_the_owner_named_exist():
    by_id = {bundle.id: bundle for bundle in extras.BUNDLES}
    assert {"documents", "pdfpages"} <= set(by_id["documents"].extras)
    assert {"ocr", "pdfpages"} <= set(by_id["vision"].extras)
    assert {"semantic", "localllm"} <= set(by_id["ai"].extras)
    assert by_id["voice"].extras == ("voice",)
    assert by_id["desktop"].extras == ("desktop",)


def test_every_extra_is_in_at_least_one_bundle():
    """A package no bundle names can only be installed one at a time, which
    is fine, but it is also easy to forget when a new entry is added."""
    named = {extra_id for bundle in extras.BUNDLES for extra_id in bundle.extras}
    assert named == set(extras.EXTRAS_BY_ID)


def test_the_catalogue_carries_the_bundles_and_each_rows_facts(client, monkeypatch):
    body = client.get("/extras").json()
    assert [b["id"] for b in body["bundles"]] == [b.id for b in extras.BUNDLES]
    for bundle in body["bundles"]:
        assert bundle["label"] and bundle["about"].endswith(".")
        assert bundle["extras"]
    for extra in body["extras"]:
        assert "version" in extra and "disk_bytes" in extra
        assert isinstance(extra["bundles"], list)
    assert body["bulk"]["running"] is False
    assert body["bulk"]["items"] == []


def test_an_installed_pip_extra_reports_its_version_and_size(client, monkeypatch):
    """Read from the installed package's own metadata. numpy stands in for an
    extra here: it is in the base install, so it is always there to read."""
    fake = extras.Extra(id="numpyish", label="numpy", enables="x.", packages=("numpy",), module="numpy", size="1 MB")
    monkeypatch.setattr(extras, "frozen_extras_dir", lambda: None)
    version, size = extras.footprint(fake)
    import numpy

    assert version == numpy.__version__
    assert size and size > 1_000_000


def test_a_missing_package_has_no_version_and_no_size(monkeypatch):
    fake = extras.Extra(id="ghost", label="Ghost", enables="x.", packages=("no-such-package-here",), module="nope", size="1 MB")
    monkeypatch.setattr(extras, "frozen_extras_dir", lambda: None)
    assert extras.footprint(fake) == ("", None)


# --- bulk actions -----------------------------------------------------------


def test_a_bulk_install_runs_each_package_in_the_order_asked(client, fake_pip, monkeypatch):
    _installed(monkeypatch, set())
    started, message = extras.start_bulk("install", ["voice", "rapidocr", "desktop"])
    assert started, message
    names = [_pip_packages(command) for command in fake_pip.commands]
    assert names == [["faster-whisper"], ["rapidocr_onnxruntime"], ["pywebview", "pystray", "Pillow"]]
    items = extras.bulk_status()["items"]
    assert [item["id"] for item in items] == ["voice", "rapidocr", "desktop"]
    assert {item["outcome"] for item in items} == {"completed"}


def test_one_failure_does_not_stop_the_rest(client, fake_pip, monkeypatch):
    _installed(monkeypatch, set())
    fake_pip.failing = {"rapidocr_onnxruntime"}
    extras.start_bulk("install", ["voice", "rapidocr", "desktop"])
    items = {item["id"]: item for item in extras.bulk_status()["items"]}
    assert items["voice"]["outcome"] == "completed"
    assert items["rapidocr"]["outcome"] == "failed"
    assert "No matching distribution" in items["rapidocr"]["message"]
    assert items["desktop"]["outcome"] == "completed"
    assert len(fake_pip.commands) == 3
    state = extras.bulk_status()
    assert state["running"] is False
    assert state["outcome"] == "failed"
    assert state["message"].endswith(".")


def test_a_bundle_installs_its_own_packages(client, fake_pip, monkeypatch):
    _installed(monkeypatch, set())
    started, _ = extras.start_bulk("install", bundle="documents")
    assert started
    ids = [item["id"] for item in extras.bulk_status()["items"]]
    assert ids == list(extras.BUNDLES_BY_ID["documents"].extras)


def test_a_bulk_install_skips_what_is_already_there(client, fake_pip, monkeypatch):
    _installed(monkeypatch, {"voice"})
    extras.start_bulk("install", ["voice", "rapidocr"])
    items = {item["id"]: item for item in extras.bulk_status()["items"]}
    assert items["voice"]["outcome"] == "skipped"
    assert items["rapidocr"]["outcome"] == "completed"
    assert [_pip_packages(c) for c in fake_pip.commands] == [["rapidocr_onnxruntime"]]


def test_a_bulk_install_skips_an_extra_that_is_not_ready(client, fake_pip, monkeypatch):
    _installed(monkeypatch, set())
    extras.start_bulk("install", ["localllm", "rapidocr"])
    items = {item["id"]: item for item in extras.bulk_status()["items"]}
    if extras.unavailable_reason(extras.EXTRAS_BY_ID["localllm"]):
        assert items["localllm"]["outcome"] == "skipped"
        assert items["localllm"]["message"].endswith(".")
    assert items["rapidocr"]["outcome"] == "completed"


def test_bulk_reinstall_forces_pip_through_the_same_runner(client, fake_pip, monkeypatch):
    _installed(monkeypatch, {"voice", "rapidocr"})
    started, message = extras.start_bulk("reinstall", ["voice", "rapidocr"])
    assert started, message
    assert len(fake_pip.commands) == 2
    for command in fake_pip.commands:
        assert "--force-reinstall" in command and "--no-cache-dir" in command


def test_a_reinstall_of_something_absent_is_an_install(client, fake_pip, monkeypatch):
    _installed(monkeypatch, set())
    extras.start_bulk("reinstall", ["rapidocr"])
    assert extras.bulk_status()["items"][0]["outcome"] == "completed"
    assert "--force-reinstall" not in fake_pip.commands[0]


def test_bulk_uninstall_removes_only_what_is_installed(client, fake_pip, monkeypatch):
    _installed(monkeypatch, {"rapidocr"})
    extras.start_bulk("uninstall", ["voice", "rapidocr"])
    items = {item["id"]: item for item in extras.bulk_status()["items"]}
    assert items["voice"]["outcome"] == "skipped"
    assert items["rapidocr"]["outcome"] == "completed"
    assert fake_pip.commands == [fake_pip.commands[0]]
    assert "uninstall" in fake_pip.commands[0]


def test_a_loaded_voice_model_fails_its_row_and_not_the_batch(client, fake_pip, monkeypatch):
    from tessellate.ai import voice

    _installed(monkeypatch, {"voice", "rapidocr"})
    monkeypatch.setattr(voice, "_loaded", ("base", object()))
    extras.start_bulk("reinstall", ["voice", "rapidocr"])
    items = {item["id"]: item for item in extras.bulk_status()["items"]}
    assert items["voice"]["outcome"] == "failed"
    assert "Restart Tessellate" in items["voice"]["message"]
    assert items["rapidocr"]["outcome"] == "completed"


def test_a_bulk_action_is_one_job_on_the_pool(client, monkeypatch):
    seen = []
    monkeypatch.setattr(extras.jobs, "enqueue", lambda kind, func, *args, name="", **kw: seen.append((kind, func)) or 1)
    _installed(monkeypatch, set())
    started, _ = extras.start_bulk("install", ["voice", "rapidocr"])
    assert started
    assert len(seen) == 1 and seen[0][0] == "extras"
    assert jobs.KIND_LANES["extras"] in jobs.LANE_WIDTHS
    assert jobs.LANE_WIDTHS[jobs.KIND_LANES["extras"]] == 1


def test_a_single_install_is_on_the_pool_too(client, monkeypatch):
    seen = []
    monkeypatch.setattr(extras.jobs, "enqueue", lambda kind, func, *args, name="", **kw: seen.append(kind) or 1)
    _installed(monkeypatch, set())
    started, _ = extras.start("rapidocr")
    assert started and seen == ["extras"]


def test_one_bulk_at_a_time_and_no_single_install_beside_it(client, monkeypatch):
    monkeypatch.setattr(extras.jobs, "enqueue", lambda *a, **k: 1)
    _installed(monkeypatch, set())
    assert extras.start_bulk("install", ["voice"])[0]
    started, message = extras.start_bulk("install", ["rapidocr"])
    assert not started and message.endswith(".")
    started, message = extras.start("rapidocr")
    assert not started and "already running" in message
    started, message = extras.remove("rapidocr")
    assert not started


@pytest.mark.parametrize(
    "body",
    [
        {"action": "install", "ids": ["requests==0.0.1"]},
        {"action": "install", "ids": ["voice", "../../etc"]},
        {"action": "install", "bundle": "no-such-bundle"},
        {"action": "compile", "ids": ["voice"]},
        {"action": "install", "ids": []},
    ],
)
def test_the_bulk_route_refuses_anything_but_allowlist_ids(client, monkeypatch, body):
    calls = []
    monkeypatch.setattr(extras.jobs, "enqueue", lambda *a, **k: calls.append(a) or 1)
    reply = client.post("/extras/bulk", json=body).json()
    assert reply["started"] is False
    assert reply["message"].endswith(".")
    assert not calls


def test_the_bulk_route_starts_a_bundle(client, monkeypatch):
    calls = []
    monkeypatch.setattr(extras.jobs, "enqueue", lambda *a, **k: calls.append(a) or 1)
    _installed(monkeypatch, set())
    reply = client.post("/extras/bulk", json={"action": "install", "bundle": "vision"}).json()
    assert reply["started"] is True, reply
    assert len(calls) == 1
    body = client.get("/extras").json()
    assert body["bulk"]["running"] is True
    assert [item["id"] for item in body["bulk"]["items"]] == list(extras.BUNDLES_BY_ID["vision"].extras)


def test_a_running_bulk_shows_its_progress_in_background_tasks(client, monkeypatch):
    monkeypatch.setattr(extras.jobs, "enqueue", lambda *a, **k: 1)
    _installed(monkeypatch, set())
    extras.start_bulk("install", ["voice", "rapidocr"])
    rows = [task for task in routes_tasks.collect() if task["kind"] == "extra"]
    assert len(rows) == 1
    assert rows[0]["label"] == "Installing 2 packages"
    assert rows[0]["progress"] == 0


def test_cancel_stops_the_rest_of_a_bulk(client, fake_pip, monkeypatch):
    """Quit on the task stops the package in hand and every one after it."""
    _installed(monkeypatch, set())
    real_run_install = extras._run_install

    def run_then_cancel(extra, reinstall=False):
        real_run_install(extra, reinstall)
        if extra.id == "voice":
            extras.cancel()

    monkeypatch.setattr(extras, "_run_install", run_then_cancel)
    extras.start_bulk("install", ["voice", "rapidocr", "desktop"])
    items = {item["id"]: item for item in extras.bulk_status()["items"]}
    assert items["voice"]["outcome"] == "completed"
    assert items["rapidocr"]["outcome"] == "cancelled"
    assert items["desktop"]["outcome"] == "cancelled"
    assert len(fake_pip.commands) == 1


def test_the_bulk_summary_reaches_the_history(client, fake_pip, monkeypatch):
    from tessellate.core import taskhistory

    recorded = []
    monkeypatch.setattr(taskhistory, "record", lambda *a, **k: recorded.append(a))
    _installed(monkeypatch, set())
    fake_pip.failing = {"rapidocr_onnxruntime"}
    extras.start_bulk("install", ["voice", "rapidocr"])
    kind, label, outcome, detail = recorded[-1][:4]
    assert kind == "extra" and label == "Installing 2 packages"
    assert outcome == "failed"
    assert "Read images without Tesseract" in detail


def test_offline_is_said_as_offline_on_each_row(client, fake_pip, monkeypatch):
    """Without a network pip ends on "Could not find a version", which reads
    as a package that does not exist; the retry lines name the real cause."""

    class _OfflinePip(_FakePip):
        def __init__(self, command, **kwargs):
            super().__init__(command, **kwargs)
            self._code = 1
            self.stdout = [
                (
                    "WARNING: Retrying (Retry(total=4)) after connection broken by "
                    + "'NewConnectionError(': Failed to establish a new connection: "
                    + "[Errno -3] Temporary failure in name resolution')': /simple/python-docx/"
                ),
                "ERROR: Could not find a version that satisfies the requirement python-docx",
            ]

    monkeypatch.setattr(extras.subprocess, "Popen", _OfflinePip)
    _installed(monkeypatch, set())
    extras.start_bulk("install", ["voice", "rapidocr"])
    for item in extras.bulk_status()["items"]:
        assert item["outcome"] == "failed"
        assert item["message"] == extras.PIP_OFFLINE_MESSAGE
    from tests.test_server_detail_wording import problems

    assert not problems(extras.PIP_OFFLINE_MESSAGE)


# --- the screen (source checks: the suite cannot see the DOM) ---------------

ROOT = Path(__file__).resolve().parents[1]
PACKAGES_JS = ROOT / "frontend" / "js" / "settings-packages.js"


def _function(source: str, name: str) -> str:
    body = source[source.index(f"function {name}(") :]
    return body[: body.index("\n}\n")]


def test_the_packages_screen_is_a_lazy_bundle_reached_through_its_entry_point():
    app = (ROOT / "frontend" / "js" / "app.js").read_text(encoding="utf-8")
    assert 'packages: ["/js/settings-packages.js"]' in app
    assert 'packages: ["renderExtras"]' in app
    status = (ROOT / "frontend" / "js" / "status.js").read_text(encoding="utf-8")
    assert "function renderExtras(" not in status
    html = (ROOT / "frontend" / "index.html").read_text(encoding="utf-8")
    assert "settings-packages.js" not in html.split("<body", 1)[1].split("</body>")[0].split('<script src="/js/app.js')[0]


def test_an_installed_rows_reinstall_is_in_its_kebab_menu():
    """DESIGN.md's menu recipe: Reinstall and Remove behind the row's ⋯,
    not two more buttons on a row that already holds a name and chips."""
    source = unwrapped(PACKAGES_JS.read_text(encoding="utf-8"))
    menu = _function(source, "packagesRowMenu")
    assert "kebabMenu(" in menu
    assert "ph:arrow-clockwise Reinstall" in menu and "ph:trash Remove" in menu
    row = _function(source, "packagesRow")
    assert "packagesRowMenu(extra, body)" in row
    assert 'smallButton("ph:arrow-clockwise' not in row


def test_the_selection_bar_is_the_select_bar_recipe():
    html = (ROOT / "frontend" / "index.html").read_text(encoding="utf-8")
    bar = re.search(r'<div id="extras-selectbar" class="([^"]*)"[^>]*>(.*?)</div>', html, re.S)
    assert bar, "the Packages selection bar is missing"
    assert {"library-contextbar", "selectbar"} <= set(bar.group(1).split())
    inner = bar.group(2)
    assert inner.index('id="extras-selected-count"') < inner.index("library-contextbar-end")
    for name in ("install", "reinstall", "remove", "done"):
        assert f'id="extras-bulk-{name}"' in inner


def test_a_bulk_request_sends_allowlist_ids_and_never_a_package_name():
    source = unwrapped(PACKAGES_JS.read_text(encoding="utf-8"))
    bulk = _function(source, "packagesBulk")
    assert '"/extras/bulk", { action, ids: extras.map((extra) => extra.id) }' in bulk
    post = bulk.split("packagesPost(", 1)[1].split("\n", 1)[0]
    assert ".packages" not in post


def test_the_help_says_how_bundles_and_bulk_actions_work():
    """Help moves with the UI (standing order 13)."""
    from tessellate.ai import help_topics_more

    html = (ROOT / "frontend" / "index.html").read_text(encoding="utf-8")
    popover = html[html.index('id="packages-help"') :]
    popover = popover[: popover.index("</div>")]
    assert "bundle" in popover and "Reinstall" in popover
    topic = next(t for t in help_topics_more.MORE_TOPICS if t["id"] == "packages")
    assert "bundle" in topic["body"].lower() and "reinstall" in topic["body"].lower()
