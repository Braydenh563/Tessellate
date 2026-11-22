"""The DPAPI store's file names are legal on Windows, and a refused store write never fails the caller.

Source text: the owner's Windows log, 2026-11-22 (Python 3.14, Ollama off): GET /capabilities
answered 500 with `OSError: [Errno 22] Invalid argument:
'...\\Tessellate\\pin\\setting|mcp_token|5c40e1e6...tmp'`. The account names secret settings are
kept under (`secrets_store._account`, "setting|mcp_token|<notebook>") hold `|`, which Windows
refuses in a file name, and the raw name was the file name (`pinstore.DpapiStore.put`).
"""

from __future__ import annotations

import re
from pathlib import Path

import pytest

from tessellate.core import pinstore, secrets_store

#: The characters Windows refuses in a file name, plus the control range.
WINDOWS_INVALID = re.compile(r'[<>:"/\\|?*\x00-\x1f]')


@pytest.fixture
def dpapi(tmp_path, monkeypatch):
    """A DPAPI store under a scratch LOCALAPPDATA, with the crypt step an identity (no Windows here)."""
    monkeypatch.setenv("LOCALAPPDATA", str(tmp_path / "local"))
    monkeypatch.setattr(pinstore.DpapiStore, "_crypt", staticmethod(lambda data, protect: data))
    return pinstore.DpapiStore(tmp_path / "notebook")


def _names(dpapi) -> list[str]:
    return [p.name for p in dpapi._dir().iterdir()]


@pytest.mark.parametrize(
    "account",
    [
        "setting|mcp_token|5c40e1e6a1b2c3d4e5f60718293a4b5c",
        "setting|llm_api_key|5c40e1e6a1b2c3d4e5f60718293a4b5c",
        'odd<>:"/\\|?*name',
    ],
)
def test_every_file_the_store_writes_has_a_windows_legal_name(dpapi, account):
    dpapi.put(account, "s3cret")
    names = _names(dpapi)
    assert names, "nothing was written"
    for name in names:
        assert not WINDOWS_INVALID.search(name), name
    assert dpapi.get(account) == "s3cret"
    dpapi.delete(account)
    assert _names(dpapi) == []


def test_a_pin_record_written_under_its_old_name_still_reads(dpapi):
    """PIN accounts were always a 32-hex digest, a legal name: those files keep their names."""
    account = pinstore.account_for(Path("/some/notebook"))
    dpapi.put(account, "record")
    assert _names(dpapi) == [f"{account}.bin"]
    assert dpapi.get(account) == "record"


def test_two_unsafe_accounts_never_share_a_file(dpapi):
    dpapi.put("setting|mcp_token|aaaa", "one")
    dpapi.put("setting|llm_api_key|aaaa", "two")
    assert dpapi.get("setting|mcp_token|aaaa") == "one"
    assert dpapi.get("setting|llm_api_key|aaaa") == "two"


def test_a_store_that_raises_oserror_falls_back_to_the_owner_only_file(tmp_path, monkeypatch, caplog):
    """The old failure: an OSError from the protected store went up through `config.set_preference`
    to the route. Now it is logged once and the owner-only file keeps the value."""

    class Refusing(pinstore.Store):
        name = "refusing"

        def available(self) -> bool:
            return True

        def put(self, account, secret):
            raise OSError(22, "Invalid argument")

        def get(self, account):
            return None

        def delete(self, account):
            pass

    monkeypatch.setattr(secrets_store, "_keyring", lambda data_dir: Refusing())
    kept = secrets_store.write(tmp_path, "mcp_token", "tok")
    assert kept is True
    assert secrets_store.read(tmp_path, "mcp_token") == "tok"
    assert any("refused mcp_token" in r.getMessage() for r in caplog.records)


def test_capabilities_answers_when_the_mcp_token_cannot_be_kept(monkeypatch, caplog):
    """One field degrades: the rest of the answer still arrives."""
    from tessellate import mcp_server
    from tessellate.api import routes_capabilities

    def refuse() -> str:
        raise OSError(22, "Invalid argument")

    monkeypatch.setattr(mcp_server, "token", refuse)
    mcp = routes_capabilities._mcp()
    assert mcp["installed"] is True
    assert mcp["config"]["env"][mcp_server.TOKEN_ENV] == ""
    assert any("MCP token" in r.getMessage() for r in caplog.records)


@pytest.mark.parametrize("account", ["setting|mcp_token|5c40e1e6", 'a<b>c:d"e/f\\g|h?i*j'])
def test_the_temporary_file_a_write_goes_through_is_legal_too(dpapi, account, monkeypatch):
    """The owner's 500 named the `.tmp` path, not the final one: both come from the same safe name."""
    seen = []
    real = pinstore.Path.write_bytes

    def spy(self, data):
        seen.append(self.name)
        return real(self, data)

    monkeypatch.setattr(pinstore.Path, "write_bytes", spy)
    dpapi.put(account, "s3cret")
    assert seen and all(n.endswith(".tmp") and not WINDOWS_INVALID.search(n) for n in seen), seen
