"""Forgot your password? (INBOX 663; the owner: "it needs to be robust and secure").

Two paths from the lock screen, one key that can be made in Settings:

- a recovery key (160 random bits, shown once) wraps the same data key a
  second time, so a new password can be set with it and private notes kept;
- without it, the same reset the terminal command does (`--reset-password`),
  through one shared function, losing only what is sealed.

What is held here: the crypto round trip, wrong keys refused and throttled
like wrong passwords, every session and vault grant ended, a private note
readable after the reset, a key dead once used or replaced or re-keyed past,
other devices refused, the two reset doors leaving the same notebook, the
migration both ways, and the key in no file or log line the app writes.
"""

from __future__ import annotations

import logging
import sqlite3

import pytest
from fastapi.testclient import TestClient

from tessellate.api import routes_auth
from tessellate.core import crypto, deps, netbind, vault

PASSWORD = "the owner's password"
NEW_PASSWORD = "a brand new passphrase"
SECRET = "the spare key is under the mat"


@pytest.fixture(autouse=True)
def _clean():
    routes_auth._active_tokens.clear()
    routes_auth._media_tickets.clear()
    routes_auth._clear_unlock_failures()
    vault.close()
    yield
    routes_auth._active_tokens.clear()
    routes_auth._media_tickets.clear()
    routes_auth._clear_unlock_failures()
    vault.close()


@pytest.fixture(autouse=True)
def _devices_already_allowed(client):
    """These tests are about sessions and the vault, so the phone here is one
    this computer already allowed; holding a new device is test_lan.py's."""
    from tessellate.core import lantrust

    lantrust.set_flag(deps.get_config().data_dir, "ask_new_devices", False)
    yield
    lantrust.reset_for_tests()


def _local(client) -> TestClient:
    return TestClient(client.app, base_url="http://127.0.0.1:8795", client=("127.0.0.1", 50000))


def _lan(client) -> TestClient:
    return TestClient(client.app, base_url="http://192.168.1.10:8795", client=("192.168.1.20", 50000))


CODE = "123456"


@pytest.fixture(autouse=True)
def _known_code(monkeypatch):
    """The code is printed to the terminal, so tests pin the draw."""
    import secrets
    from types import SimpleNamespace

    from tessellate.core import reset_code

    monkeypatch.setattr(
        reset_code, "secrets", SimpleNamespace(randbelow=lambda n: int(CODE), token_bytes=secrets.token_bytes)
    )
    reset_code._forget()


def _reset(local, code: str = CODE):
    """Ask for the code, then reset with it (INBOX 1424)."""
    asked = local.post("/auth/reset-code")
    assert asked.status_code == 200, asked.text
    return local.post("/auth/reset", json={"confirm": "RESET", "code": code})


def _auth(token: str) -> dict:
    return {"X-Auth-Token": token}


def _restart() -> None:
    routes_auth._active_tokens.clear()
    routes_auth._media_tickets.clear()
    vault.close()


def _notebook(client, *, with_key: bool = True) -> tuple[int, str | None]:
    """A notebook with one private note and, unless asked not to, a recovery
    key; then a restart, so nothing is unlocked. (note id, recovery key)"""
    local = _local(client)
    token = local.post("/auth/setup", json={"password": PASSWORD}).json()["token"]
    entry = local.post("/entries", json={"content": SECRET}, headers=_auth(token)).json()
    made = local.post(f"/entries/{entry['id']}/privacy", json={"private": True}, headers=_auth(token))
    assert made.status_code == 200, made.text
    key = None
    if with_key:
        answer = local.post("/auth/recovery-key", json={"current_password": PASSWORD}, headers=_auth(token))
        assert answer.status_code == 200, answer.text
        key = answer.json()["recovery_key"]
    _restart()
    return entry["id"], key


def _recover(local, key: str, password: str = NEW_PASSWORD):
    return local.post("/auth/recover", json={"recovery_key": key, "new_password": password})


def _reads_secret(local, note: int, token: str) -> bool:
    response = local.get(f"/entries/{note}", headers=_auth(token))
    assert response.status_code == 200, response.text
    return response.json()["content"] == SECRET


# --- the key itself ----------------------------------------------------------


def test_a_recovery_key_is_160_random_bits_in_eight_groups():
    key = crypto.new_recovery_key()
    groups = key.split("-")
    assert len(groups) == 8 and all(len(g) == 4 for g in groups)
    canonical = crypto.normalise_recovery_key(key)
    assert canonical is not None and len(canonical) == 32
    import base64

    assert len(base64.b32decode(canonical)) == 20
    assert crypto.new_recovery_key() != key


def test_a_key_is_read_however_it_was_copied():
    key = crypto.new_recovery_key()
    canonical = key.replace("-", "")
    assert crypto.normalise_recovery_key(key.lower()) == canonical
    assert crypto.normalise_recovery_key(" ".join(key.split("-"))) == canonical
    assert crypto.normalise_recovery_key(key[:-1]) is None
    assert crypto.normalise_recovery_key("not a key at all") is None


def test_the_recovery_key_wraps_the_same_data_key(session):
    vault.create(session, PASSWORD)
    dek = vault.key()
    key = vault.issue_recovery(session)
    session.commit()
    assert vault.open_with_recovery(session, key) == dek
    assert vault.open_with_recovery(session, crypto.new_recovery_key()) is None
    # The password's own wrap is untouched by it.
    vault.close()
    assert vault.open_with(session, PASSWORD) and vault.key() == dek


# --- the recovery path ---------------------------------------------------------


def test_recovery_keeps_private_notes_and_sets_the_new_password(client):
    note, key = _notebook(client)
    local = _local(client)
    answer = _recover(local, key)
    assert answer.status_code == 200, answer.text
    body = answer.json()
    assert body["vault_open"] is True
    assert _reads_secret(local, note, body["token"])
    # The new password unlocks, with private notes, after a restart; the old does not.
    _restart()
    assert local.post("/auth/unlock", json={"password": PASSWORD}).status_code == 401
    routes_auth._clear_unlock_failures()
    again = local.post("/auth/unlock", json={"password": NEW_PASSWORD}).json()
    assert again["vault_open"] is True
    assert _reads_secret(local, note, again["token"])


def test_a_used_key_is_spent_and_its_successor_works(client):
    note, key = _notebook(client)
    local = _local(client)
    first = _recover(local, key).json()
    successor = first["recovery_key"]
    assert successor and successor != key
    assert _recover(local, key, "yet another passphrase").status_code == 401
    routes_auth._clear_unlock_failures()
    second = _recover(local, successor, "yet another passphrase")
    assert second.status_code == 200, second.text
    assert _reads_secret(local, note, second.json()["token"])


def test_replacing_the_key_kills_the_old_one(client):
    _note, key = _notebook(client)
    local = _local(client)
    token = local.post("/auth/unlock", json={"password": PASSWORD}).json()["token"]
    replaced = local.post("/auth/recovery-key", json={"current_password": PASSWORD}, headers=_auth(token))
    assert replaced.status_code == 200
    assert replaced.json()["recovery_key"] != key
    assert _recover(local, key).status_code == 401
    routes_auth._clear_unlock_failures()
    assert _recover(local, replaced.json()["recovery_key"]).status_code == 200


def test_making_a_key_needs_the_current_password_and_is_throttled(client):
    _notebook(client, with_key=False)
    local = _local(client)
    token = local.post("/auth/unlock", json={"password": PASSWORD}).json()["token"]
    for _ in range(routes_auth._FAILURE_ALLOWANCE + 1):
        wrong = local.post("/auth/recovery-key", json={"current_password": "nope"}, headers=_auth(token))
        assert wrong.status_code in (401, 429)
    assert local.post("/auth/recovery-key", json={"current_password": PASSWORD}, headers=_auth(token)).status_code == 429
    assert local.post("/auth/recovery-key", json={"current_password": PASSWORD}).status_code == 401  # locked


def test_a_re_key_hands_out_a_new_recovery_key(client):
    note, key = _notebook(client)
    local = _local(client)
    token = local.post("/auth/unlock", json={"password": PASSWORD}).json()["token"]
    rotated = local.post("/auth/rotate-vault-key", json={"current_password": PASSWORD}, headers=_auth(token))
    assert rotated.status_code == 200, rotated.text
    successor = rotated.json()["recovery_key"]
    assert successor and successor != key
    _restart()
    assert _recover(local, key).status_code == 401
    routes_auth._clear_unlock_failures()
    answer = _recover(local, successor)
    assert answer.status_code == 200
    assert _reads_secret(local, note, answer.json()["token"])


def test_a_re_key_without_a_recovery_key_makes_none(client):
    _notebook(client, with_key=False)
    local = _local(client)
    token = local.post("/auth/unlock", json={"password": PASSWORD}).json()["token"]
    rotated = local.post("/auth/rotate-vault-key", json={"current_password": PASSWORD}, headers=_auth(token))
    assert rotated.json()["recovery_key"] is None


def test_wrong_keys_earn_the_same_waits_as_wrong_passwords(client):
    _note, key = _notebook(client)
    local = _local(client)
    for _ in range(routes_auth._FAILURE_ALLOWANCE):
        assert _recover(local, crypto.new_recovery_key()).status_code == 401
    assert _recover(local, crypto.new_recovery_key()).status_code == 429
    # The same buckets: the right key waits, and so does the password.
    assert _recover(local, key).status_code == 429
    assert local.post("/auth/unlock", json={"password": PASSWORD}).status_code == 429


def test_no_key_and_a_wrong_key_get_the_same_answer(client):
    """An open route must not say whether this notebook has a recovery key."""
    _notebook(client, with_key=False)
    local = _local(client)
    absent = _recover(local, crypto.new_recovery_key())
    routes_auth._clear_unlock_failures()
    assert absent.status_code == 401
    assert absent.json()["detail"] == "That recovery key is wrong."


def test_the_new_password_follows_setup_rules_before_the_key_is_tried(client):
    _note, key = _notebook(client)
    local = _local(client)
    short = _recover(local, key, "short")
    assert short.status_code == 400
    assert not routes_auth._failed_unlocks  # nothing was guessed
    malformed = _recover(local, "ABCD-EFGH")
    assert malformed.status_code == 400
    assert not routes_auth._failed_unlocks
    assert _recover(local, key).status_code == 200  # the key was not spent


def test_recovery_ends_every_session_and_grant(client):
    note, key = _notebook(client)
    local = _local(client)
    lan = _lan(client)
    phone = lan.post("/auth/unlock", json={"password": PASSWORD}).json()["token"]
    desk = local.post("/auth/unlock", json={"password": PASSWORD}).json()["token"]
    assert vault.is_granted(phone) and vault.is_granted(desk)
    answer = _recover(local, key).json()
    for old in (phone, desk):
        assert old not in routes_auth._active_tokens
        assert not vault.is_granted(old)
    assert lan.get("/entries?limit=5", headers=_auth(phone)).status_code == 401
    assert vault.is_granted(answer["token"])
    assert set(routes_auth._active_tokens) == {answer["token"]}


def test_both_open_routes_refuse_another_device(client):
    _note, key = _notebook(client)
    lan = _lan(client)
    assert _recover(lan, key).status_code == 403
    assert lan.post("/auth/reset", json={"confirm": "RESET"}).status_code == 403
    assert lan.get("/auth/status").json()["reset_here"] is False
    assert _local(client).get("/auth/status").json()["reset_here"] is True
    # A tunnel on this machine connects from loopback on someone else's behalf.
    tunnelled = _local(client).post(
        "/auth/recover",
        json={"recovery_key": key, "new_password": NEW_PASSWORD},
        headers={"X-Forwarded-For": "203.0.113.9"},
    )
    assert tunnelled.status_code == 403
    # And another site's page, whatever its address.
    cross = _local(client).post(
        "/auth/reset", json={"confirm": "RESET"}, headers={"Origin": "https://evil.example"}
    )
    assert cross.status_code == 403
    assert client.app  # the notebook is still there
    assert _local(client).get("/auth/status").json()["setup_required"] is False


def test_the_open_status_says_nothing_about_the_notebook(client):
    _notebook(client)
    status = _local(client).get("/auth/status").json()
    # `pin_here` is about this caller and this computer (core/pinstore.py),
    # like `reset_here`: never note counts or whether a recovery key exists.
    assert set(status) == {"setup_required", "auto_session", "reset_here", "pin_here"}


# --- the reset without a key ---------------------------------------------------


def test_reset_needs_the_typed_word(client):
    _notebook(client)
    local = _local(client)
    assert local.post("/auth/reset", json={"confirm": "reset please"}).status_code == 400
    assert local.post("/auth/reset", json={}).status_code == 400
    assert local.get("/auth/status").json()["setup_required"] is False


def _state(app_state) -> dict:
    from tessellate.core.database import Entry, User, Vault
    from sqlalchemy import func, select

    with deps.get_db().session() as session:
        session.info["workspace_id"] = "all"
        return {
            "users": session.scalar(select(func.count(User.id))),
            "vaults": session.scalar(select(func.count(Vault.id))),
            "entries": session.scalar(select(func.count(Entry.id))),
            "private": session.scalar(select(func.count(Entry.id)).where(Entry.is_private == True)),  # noqa: E712
            "lan": netbind.lan_enabled(app_state),
        }


def test_the_app_and_the_terminal_reset_share_one_function():
    import inspect

    from tessellate import __main__ as launcher

    assert "password_reset.reset_password(" in inspect.getsource(launcher._reset_password)
    assert "password_reset.reset_password(" in inspect.getsource(routes_auth.reset)


@pytest.mark.parametrize("door", ["app", "terminal"])
def test_both_doors_leave_the_same_notebook(client, app_state, monkeypatch, door):
    """Run on identical notebooks, each door leaves exactly this: no password,
    no vault, every note still there (the private one sealed, not deleted),
    other devices off, and nothing left unlocked in this process."""
    _notebook(client)
    app_state.set_preference(netbind.LAN_PREF, True)
    before = _state(app_state)
    if door == "app":
        answer = _reset(_local(client))
        assert answer.status_code == 200, answer.text
    else:
        from tessellate import __main__ as launcher

        monkeypatch.setattr("builtins.input", lambda prompt="": "RESET")
        assert launcher._reset_password() == 0
    after = _state(app_state)
    assert after == {**before, "users": 0, "vaults": 0, "lan": False}
    assert after["private"] == 1
    assert _local(client).get("/auth/status").json()["setup_required"] is True
    assert not vault.is_open()


def test_after_a_reset_setup_runs_and_a_new_private_note_works(client):
    note, _key = _notebook(client)
    local = _local(client)
    _reset(local)
    token = local.post("/auth/setup", json={"password": NEW_PASSWORD}).json()["token"]
    # The old private note stays sealed: it is there, and it does not open.
    old = local.get(f"/entries/{note}", headers=_auth(token)).json()
    assert old["content"] != SECRET
    fresh = local.post("/entries", json={"content": "after"}, headers=_auth(token)).json()
    assert local.post(f"/entries/{fresh['id']}/privacy", json={"private": True}, headers=_auth(token)).status_code == 200


def test_a_reset_notebook_can_still_re_key(client, session):
    """Found by forgotpw.js on its own data dir: after a reset without the
    key, the sealed notes (made under the vault the reset removed) made every
    re-key a 500, for good. They are left exactly as they are now, and every
    note the current key opens moves across."""
    from tessellate.core.database import Entry

    old_note, _key = _notebook(client)
    local = _local(client)
    _reset(local)
    token = local.post("/auth/setup", json={"password": NEW_PASSWORD}).json()["token"]
    fresh = local.post("/entries", json={"content": "after the reset"}, headers=_auth(token)).json()
    local.post(f"/entries/{fresh['id']}/privacy", json={"private": True}, headers=_auth(token))
    session.info["workspace_id"] = "all"
    sealed_before = session.get(Entry, old_note).content
    rotated = local.post("/auth/rotate-vault-key", json={"current_password": NEW_PASSWORD}, headers=_auth(token))
    assert rotated.status_code == 200, rotated.text
    body = rotated.json()
    assert body["notes_reencrypted"] == 1 and body["notes_sealed"] == 1
    session.expire_all()
    assert session.get(Entry, old_note).content == sealed_before
    assert local.get(f"/entries/{fresh['id']}", headers=_auth(body["token"])).json()["content"] == "after the reset"


# --- the key is in no file and no log line -------------------------------------


def test_the_key_is_never_written_down(client, app_state, caplog):
    caplog.set_level(logging.DEBUG)
    note, key = _notebook(client)
    local = _local(client)
    answer = _recover(local, key).json()
    successor = answer["recovery_key"]
    token = answer["token"]
    replaced = local.post("/auth/recovery-key", json={"current_password": NEW_PASSWORD}, headers=_auth(token)).json()
    keys = [key, successor, replaced["recovery_key"]]
    forms = [form for k in keys for form in (k, k.replace("-", ""), k.lower())]

    deps.get_db().engine.dispose()
    data_dir = app_state.data_dir
    for path in data_dir.rglob("*"):
        if path.is_file():
            blob = path.read_bytes()
            for form in forms:
                assert form.encode() not in blob, path.name
    logged = caplog.text
    for form in forms:
        assert form not in logged
    # The audit trail says what happened, never the key.
    db_path = next(data_dir.rglob("*.db"))
    conn = sqlite3.connect(str(db_path))
    try:
        rows = " ".join(str(r) for r in conn.execute("SELECT * FROM audit_log").fetchall())
        stored = conn.execute("SELECT recovery_wrapped_dek FROM vault").fetchone()[0]
    finally:
        conn.close()
    assert "recovery key made" in rows and "password reset with the recovery key" in rows
    for form in forms:
        assert form not in rows
    assert stored and len(stored) == crypto.NONCE_BYTES + 32 + 16  # nonce, key, GCM tag
    assert note


def test_the_key_is_not_in_any_error_message(client):
    _notebook(client)
    local = _local(client)
    wrong = crypto.new_recovery_key()
    for body in (
        {"recovery_key": wrong, "new_password": NEW_PASSWORD},
        {"recovery_key": wrong, "new_password": "short"},
        {"recovery_key": wrong + "X" * 300, "new_password": NEW_PASSWORD},
        {"recovery_key": [wrong], "new_password": NEW_PASSWORD},
    ):
        routes_auth._clear_unlock_failures()
        answer = local.post("/auth/recover", json=body)
        assert answer.status_code >= 400
        assert wrong not in answer.text and wrong.replace("-", "") not in answer.text


# --- the migration ---------------------------------------------------------------


def _alembic(db_path, direction: str, target: str) -> None:
    from pathlib import Path

    from alembic import command
    from alembic.config import Config

    root = Path(__file__).resolve().parents[1]
    config = Config(str(root / "alembic.ini"))
    config.set_main_option("script_location", str(root / "migrations"))
    config.set_main_option("sqlalchemy.url", f"sqlite:///{db_path}")
    getattr(command, direction)(config, target)


def _vault_columns(db_path) -> set:
    conn = sqlite3.connect(str(db_path))
    try:
        return {row[1] for row in conn.execute('PRAGMA table_info("vault")')}
    finally:
        conn.close()


def test_the_migration_goes_up_and_down_on_an_existing_notebook(tmp_path):
    """An existing notebook from before: a vault row without the recovery
    columns. Up adds them (null), down takes them away, and the password's
    wrap of the key is untouched both ways."""
    from tessellate.core.database import DatabaseManager

    db_path = tmp_path / "old.db"
    manager = DatabaseManager(db_path)
    manager.engine.dispose()
    salt = crypto.new_salt()
    dek = crypto.new_dek()
    wrapped = crypto.wrap_dek(dek, PASSWORD, salt)
    conn = sqlite3.connect(str(db_path))
    try:
        # The table as the release before this one made it.
        conn.execute("DROP TABLE vault")
        conn.execute(
            "CREATE TABLE vault (id INTEGER PRIMARY KEY, kdf_salt BLOB, wrapped_dek BLOB, created_at DATETIME)"
        )
        conn.execute("INSERT INTO vault (kdf_salt, wrapped_dek) VALUES (?, ?)", (salt, wrapped))
        conn.execute("CREATE TABLE IF NOT EXISTS alembic_version (version_num VARCHAR(32) NOT NULL)")
        conn.execute("DELETE FROM alembic_version")
        conn.execute("INSERT INTO alembic_version VALUES ('b4e8d2a6f1c9')")
        conn.commit()
    finally:
        conn.close()

    recovery = {"recovery_salt", "recovery_wrapped_dek", "recovery_created_at"}
    assert not recovery & _vault_columns(db_path)
    _alembic(db_path, "upgrade", "d7a3f1c9e2b5")
    assert recovery <= _vault_columns(db_path)
    _alembic(db_path, "downgrade", "b4e8d2a6f1c9")
    assert not recovery & _vault_columns(db_path)
    _alembic(db_path, "upgrade", "head")
    conn = sqlite3.connect(str(db_path))
    try:
        row = conn.execute("SELECT kdf_salt, wrapped_dek, recovery_wrapped_dek FROM vault").fetchone()
    finally:
        conn.close()
    assert crypto.unwrap_dek(row[1], PASSWORD, row[0]) == dek
    assert row[2] is None


# --- Download .txt in the desktop window (INBOX 671) ------------------------------


def _desktop(monkeypatch, chosen):
    """The desktop window, with its Save dialog faked to answer `chosen`."""
    from tessellate.core import desktop_dialog

    asked = {}

    def fake(filename, start):
        asked.update(filename=filename, start=start)
        return chosen

    monkeypatch.setenv("TESSELLATE_DESKTOP", "1")
    monkeypatch.setattr(desktop_dialog, "save_dialog", fake)
    return asked


def _unlocked(client) -> tuple:
    local = _local(client)
    token = local.post("/auth/setup", json={"password": PASSWORD}).json()["token"]
    key = local.post("/auth/recovery-key", json={"current_password": PASSWORD}, headers=_auth(token)).json()
    return local, token, key["recovery_key"]


def _under(data_dir, key: str) -> list:
    return [p.name for p in data_dir.rglob("*") if p.is_file() and key.encode() in p.read_bytes()]


def test_the_desktop_saves_the_key_where_the_person_chooses(client, app_state, monkeypatch, tmp_path):
    local, token, key = _unlocked(client)
    outside = tmp_path / "elsewhere" / "tessellate-recovery-key.txt"
    outside.parent.mkdir()
    asked = _desktop(monkeypatch, outside)
    answer = local.post("/auth/recovery-key/save", json={"text": f"key {key}"}, headers=_auth(token))
    assert answer.status_code == 200, answer.text
    assert answer.json() == {"saved": True, "path": str(outside.resolve())}
    assert outside.read_text() == f"key {key}"
    assert asked["filename"] == "tessellate-recovery-key.txt"
    assert app_state.data_dir.resolve() not in asked["start"].resolve().parents
    deps.get_db().engine.dispose()
    assert _under(app_state.data_dir, key) == []  # nothing beside the notebook


def test_the_desktop_refuses_the_notebook_folder(client, app_state, monkeypatch):
    local, token, key = _unlocked(client)
    for inside in (app_state.data_dir / "exports" / "key.txt", app_state.data_dir / "key.txt"):
        inside.parent.mkdir(parents=True, exist_ok=True)
        _desktop(monkeypatch, inside)
        answer = local.post("/auth/recovery-key/save", json={"text": key}, headers=_auth(token))
        assert answer.status_code == 400
        assert key not in answer.text
        assert not inside.exists()
    deps.get_db().engine.dispose()
    assert _under(app_state.data_dir, key) == []


def test_a_cancelled_dialog_writes_nothing(client, app_state, monkeypatch):
    local, token, key = _unlocked(client)
    _desktop(monkeypatch, None)
    answer = local.post("/auth/recovery-key/save", json={"text": key}, headers=_auth(token))
    assert answer.json() == {"saved": False}
    deps.get_db().engine.dispose()
    assert _under(app_state.data_dir, key) == []


def test_the_save_route_is_desktop_only_and_behind_the_lock(client, monkeypatch):
    local, token, key = _unlocked(client)
    monkeypatch.delenv("TESSELLATE_DESKTOP", raising=False)
    assert local.post("/auth/recovery-key/save", json={"text": key}, headers=_auth(token)).status_code == 409
    _desktop(monkeypatch, None)
    assert local.post("/auth/recovery-key/save", json={"text": key}).status_code == 401


def test_the_dialog_starts_in_documents(monkeypatch, tmp_path):
    from tessellate.core import desktop_dialog

    monkeypatch.setattr("pathlib.Path.home", lambda: tmp_path)
    assert desktop_dialog.documents_folder() == tmp_path
    (tmp_path / "Documents").mkdir()
    assert desktop_dialog.documents_folder() == tmp_path / "Documents"


def test_the_dialog_speaks_both_pywebview_dialects(monkeypatch, tmp_path):
    import sys
    import types

    from tessellate.core import desktop_dialog

    calls = []

    class Window:
        def create_file_dialog(self, kind, directory, save_filename):
            calls.append((kind, directory, save_filename))
            return (str(tmp_path / save_filename),)

    new = types.SimpleNamespace(windows=[Window()], FileDialog=types.SimpleNamespace(SAVE=30))
    monkeypatch.setitem(sys.modules, "webview", new)
    assert desktop_dialog.save_dialog("k.txt", tmp_path) == tmp_path / "k.txt"
    old = types.SimpleNamespace(windows=[Window()], SAVE_DIALOG=20)
    monkeypatch.setitem(sys.modules, "webview", old)
    assert desktop_dialog.save_dialog("k.txt", tmp_path) == tmp_path / "k.txt"
    assert [c[0] for c in calls] == [30, 20] and calls[0][1] == str(tmp_path)
    monkeypatch.setitem(sys.modules, "webview", types.SimpleNamespace(windows=[]))
    assert desktop_dialog.save_dialog("k.txt", tmp_path) is None
