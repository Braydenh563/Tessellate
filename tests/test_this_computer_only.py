"""A phone on the network never makes this computer act (the owner,
2026-10-11: "I pressed open file location for the support bundle on my phone
and it opened up file explorer on my computer which is cool but worried me a
bit. I need maximum trust, proper safe connection, proper security for the
lan and open connection")."""

from __future__ import annotations

import importlib

import pytest
from fastapi import HTTPException
from starlette.requests import Request

from tessellate.api.this_computer import is_another_device, this_computer_only

HOST_ONLY = {
    "routes_auth": {"/lan-certificate", "/recovery-key/save"},
    "routes_backups": {"/backups/restore", "/backups/bundle/restore"},
    "routes_files": {"/files/open-exports-folder", "/files/save"},
    "routes_maintenance": {"/system/maintenance", "/system/doctor", "/system/reinstall-on-start",
                           "/system/open-logs-folder", "/system/desktop-shortcut"},
    "routes_models": {"/provider", "/pull", "/delete", "/embedding-backend"},
    "routes_settings": {"/system/console-mode", "/system/restart", "/extras/bulk", "/extras/{extra_id}/install",
                        "/extras/{extra_id}/uninstall", "/embedding-models/use",
                        "/embedding-models/pull", "/embedding-models/{model_id}/download",
                        "/embedding-models/{model_id}"},
    "routes_settings_transfer": {"/import/directory"},
    "routes_tasks": {"/desktop/fullscreen", "/shutdown"},
    "routes_update": {"/apply"},
    "routes_websearch": {"/websearch/detect-searxng", "/websearch/searxng/start", "/websearch/searxng/reinstall",
                         "/websearch/searxng/stop"},
}


def _request(client: str, headers: dict[str, str] | None = None) -> Request:
    raw = [(k.lower().encode(), v.encode()) for k, v in (headers or {}).items()]
    return Request({"type": "http", "method": "POST", "path": "/", "headers": raw, "client": (client, 50000)})


@pytest.mark.parametrize("client", ["192.168.0.50", "10.1.2.3", "2001:db8::5", "fe80::1%en0", "100.64.0.9"])
def test_another_device_is_refused(client):
    with pytest.raises(HTTPException) as caught:
        this_computer_only(_request(client))
    assert caught.value.status_code == 403 and "Not available on this device" in caught.value.detail


@pytest.mark.parametrize("client", ["127.0.0.1", "::1", "::ffff:127.0.0.1"])
def test_this_computer_is_let_through(client):
    assert this_computer_only(_request(client)) is None


def test_a_tunnel_on_this_computer_is_another_device():
    assert is_another_device(_request("127.0.0.1", {"X-Forwarded-For": "203.0.113.9"}))


@pytest.mark.parametrize("module", sorted(HOST_ONLY))
def test_every_act_on_the_computer_carries_the_guard(module):
    router = importlib.import_module(f"tessellate.api.{module}").router
    guarded = set()
    for route in router.routes:
        calls = {getattr(d.dependency, "__name__", "") for d in getattr(route, "dependencies", [])}
        if "this_computer_only" in calls:
            guarded.add(route.path.removeprefix(router.prefix))
    assert HOST_ONLY[module] <= guarded, HOST_ONLY[module] - guarded
