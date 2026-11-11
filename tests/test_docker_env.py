"""Docker support (Brief 40): the environment handling in the launcher."""

import asyncio

from tessellate.core import first_password, netbind


def test_bind_defaults_to_loopback_and_survives_junk():
    assert netbind.env_bind("") == "127.0.0.1"
    assert netbind.env_bind("localhost") == "127.0.0.1"
    assert netbind.env_bind("not a host") == "127.0.0.1"
    assert netbind.env_bind("0.0.0.0") == "0.0.0.0"
    assert netbind.env_bind(" [::] ") == "::"


def test_first_password_is_taken_once_and_blank_is_none(monkeypatch):
    monkeypatch.setenv(first_password.ENV, "  ")
    assert first_password.take_from_env() is None
    monkeypatch.setenv(first_password.ENV, "a long enough secret")
    assert first_password.take_from_env() == "a long enough secret"
    import os

    assert first_password.ENV not in os.environ  # not inherited by children


def test_seed_only_when_no_password_and_never_logs_it(tmp_path, monkeypatch, caplog):
    from tessellate.core.database import User
    from tessellate.core.database_manager import DatabaseManager

    db = DatabaseManager(tmp_path / "m.db")
    secret = "correct horse battery"
    assert first_password.seed(db, None) == "none"
    assert first_password.seed(db, "short") == "refused"
    assert first_password.seed(db, secret) == "seeded"
    assert first_password.seed(db, "another long secret") == "already-set"
    assert secret not in caplog.text
    with db.session() as session:
        assert session.query(User).count() == 1


def test_explicit_bind_skips_the_no_password_403_and_default_keeps_it(monkeypatch):
    from tessellate.core import security

    monkeypatch.setattr(security, "_notebook_has_password", lambda: False)
    monkeypatch.setattr(netbind, "_current", "0.0.0.0")

    async def call(explicit):
        netbind.set_explicit_bind(explicit)
        sent = []

        async def app(scope, receive, send):
            sent.append("app")

        async def send(message):
            sent.append(message.get("status"))

        mw = security.HostCheckMiddleware(app)
        scope = {"type": "http", "server": ("172.17.0.2", 8000), "headers": [(b"host", b"localhost:8000")]}
        await mw(scope, None, send)
        return sent

    try:
        assert 403 in asyncio.run(call(False))
        assert asyncio.run(call(True)) == ["app"]
    finally:
        netbind.set_explicit_bind(False)


# --- behind a reverse proxy (OPEN ledger 318) ---------------------------------


def test_an_allowed_host_variable_names_the_proxy_s_host(monkeypatch):
    """A proxy forwarding `memory.example.com` was answered 421, because only
    this computer's own names pass the rebinding guard."""
    monkeypatch.delenv(netbind.ALLOWED_HOSTS_ENV, raising=False)
    assert not netbind.host_allowed("memory.example.com")
    monkeypatch.setenv(netbind.ALLOWED_HOSTS_ENV, "memory.example.com, Notes.Home.Lan")
    assert netbind.host_allowed("memory.example.com")
    assert netbind.host_allowed("memory.example.com:8443")
    assert netbind.host_allowed("notes.home.lan")
    assert not netbind.host_allowed("evil.example")
    assert not netbind.host_allowed("memory.example.com.evil.example")


def test_the_allowed_host_variable_takes_names_only(monkeypatch):
    """A wildcard would switch the guard off, and a URL is not a name: the
    first is ignored, the second is read for its host."""
    monkeypatch.setenv(netbind.ALLOWED_HOSTS_ENV, "*, https://notes.example.com:8443/path, bad host")
    assert netbind.extra_allowed_hosts() == frozenset({"notes.example.com"})
    assert not netbind.host_allowed("evil.example")


def test_a_proxied_origin_on_the_standard_port_is_this_app_s_own_page(monkeypatch):
    """The proxy ends TLS and talks http to the container, so the app sees
    scheme http and Host `memory.example.com` while the browser's Origin is
    `https://memory.example.com` (port 443): without this every write behind
    a proxy was refused as another site."""
    from tessellate.core import security

    monkeypatch.delenv(netbind.ALLOWED_HOSTS_ENV, raising=False)
    assert not security._is_same_site("https://memory.example.com", "memory.example.com", "http")
    monkeypatch.setenv(netbind.ALLOWED_HOSTS_ENV, "memory.example.com")
    assert security._is_same_site("https://memory.example.com", "memory.example.com", "http")
    assert security._is_same_site("https://memory.example.com", "memory.example.com:80", "http")
    assert not security._is_same_site("https://evil.example", "memory.example.com", "http")
    assert not security._is_same_site("https://memory.example.com:9999", "memory.example.com", "http")
