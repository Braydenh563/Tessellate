"""The six-digit reset code (INBOX 1424, audit 1028 K1).

`POST /auth/reset` took only a typed word, so any program on this computer
could seal every private note. It now needs a code the server prints to its
own terminal. Held here: no code or a wrong code changes nothing, the code is
never in a response or the log buffer, one use, ten minutes (fixed clock),
two live codes at most, 30 seconds between asks, five wrong tries, asking again buys no extra guesses, this
computer only, and only a hash is kept.
"""

from __future__ import annotations

import logging

from test_forgot_password import (  # noqa: F401  # the fixtures are autouse there
    CODE,
    _clean,
    _devices_already_allowed,
    _known_code,
    _lan,
    _local,
    _notebook,
    _reset,
    _state,
)

#: Named so the autouse fixtures above read as used: pytest finds them by import.
AUTOUSE = (_clean, _devices_already_allowed, _known_code)

BODY = {"confirm": "RESET"}


def _try(local, code: str) -> int:
    return local.post("/auth/reset", json={**BODY, "code": code}).status_code


def test_reset_without_a_code_is_refused_and_changes_nothing(client, app_state):
    _notebook(client)
    local = _local(client)
    before = _state(app_state)
    assert local.post("/auth/reset", json=BODY).status_code == 401
    local.post("/auth/reset-code")
    assert _try(local, "000000") == 401
    assert _try(local, "12345") == 401
    assert _state(app_state) == before


def test_the_code_is_printed_to_the_terminal_and_never_returned(client, capsys, caplog):
    _notebook(client)
    caplog.set_level(logging.DEBUG)
    asked = _local(client).post("/auth/reset-code")
    assert asked.json()["expires_in"] == 600 and asked.json()["where"] in ("terminal", "log")
    assert CODE not in asked.text and CODE not in str(asked.headers)
    assert CODE in capsys.readouterr().err
    assert CODE not in caplog.text


def test_the_code_works_once(client):
    _notebook(client)
    local = _local(client)
    assert _reset(local).status_code == 200
    assert _try(local, CODE) in (400, 401)


def test_the_code_expires_after_ten_minutes(client, monkeypatch):
    from tessellate.core import reset_code

    _notebook(client)
    local = _local(client)
    clock = [1_000_000.0]
    monkeypatch.setattr(reset_code, "_now", lambda: clock[0])
    local.post("/auth/reset-code")
    clock[0] += 599
    assert _try(local, "999999") == 401
    local.post("/auth/reset-code")
    clock[0] += 600
    assert _try(local, CODE) == 401
    assert local.get("/auth/status").json()["setup_required"] is False


def test_just_inside_the_ten_minutes_still_works(client, monkeypatch):
    from tessellate.core import reset_code

    _notebook(client)
    local = _local(client)
    clock = [1_000_000.0]
    monkeypatch.setattr(reset_code, "_now", lambda: clock[0])
    local.post("/auth/reset-code")
    clock[0] += 599
    assert _try(local, CODE) == 200


def _fixed_clock(monkeypatch):
    from tessellate.core import reset_code

    clock = [1_000_000.0]
    monkeypatch.setattr(reset_code, "_now", lambda: clock[0])
    return clock


def test_a_second_code_leaves_the_first_working_and_a_correct_one_consumes_all(client, monkeypatch):
    from tessellate.core import reset_code

    _notebook(client)
    local = _local(client)
    clock = _fixed_clock(monkeypatch)
    draws = iter([111111, 222222])
    monkeypatch.setattr(reset_code.secrets, "randbelow", lambda n: next(draws))
    assert local.post("/auth/reset-code").status_code == 200
    clock[0] += 31
    assert local.post("/auth/reset-code").status_code == 200
    assert _try(local, "111111") == 200
    assert _try(local, "222222") in (400, 401)


def test_a_third_issue_within_thirty_seconds_is_refused(client, monkeypatch):
    _notebook(client)
    local = _local(client)
    clock = _fixed_clock(monkeypatch)
    assert local.post("/auth/reset-code").status_code == 200
    clock[0] += 10
    refused = local.post("/auth/reset-code")
    assert refused.status_code == 429
    assert refused.headers["Retry-After"] == "21"
    assert refused.json()["detail"] == "A code was just printed. Look for it, or ask again in 21 seconds."
    clock[0] += 21
    assert local.post("/auth/reset-code").status_code == 200


def test_only_two_codes_stay_live_and_each_keeps_its_own_expiry(client, monkeypatch):
    from tessellate.core import reset_code

    _notebook(client)
    local = _local(client)
    clock = _fixed_clock(monkeypatch)
    draws = iter([111111, 222222, 333333])
    monkeypatch.setattr(reset_code.secrets, "randbelow", lambda n: next(draws))
    for _ in range(3):
        local.post("/auth/reset-code")
        clock[0] += 31
    assert len(reset_code._state["live"]) == 2
    assert _try(local, "111111") == 401
    assert _try(local, "333333") == 200


def test_the_log_answer_names_a_file_and_never_a_path(client, monkeypatch):
    from tessellate.core import reset_code

    _notebook(client)
    monkeypatch.setattr(reset_code, "stderr_is_terminal", lambda: False)
    body = _local(client).post("/auth/reset-code").json()
    assert body["where"] == "log" and "/" not in body["log_file"] and body["log_file"].endswith(".log")
    assert CODE not in str(body)


def test_open_logs_answers_ok_only_and_this_computer_only(client, monkeypatch):
    from tessellate.api import routes_files

    _notebook(client)
    opened = []
    monkeypatch.setattr(routes_files, "reveal_folder", lambda folder, label: opened.append(label))
    ok = _local(client).post("/auth/reset-code/open-logs")
    assert ok.json() == {"ok": True} and opened == ["the launcher logs"]
    assert _lan(client).post("/auth/reset-code/open-logs").status_code == 403


def test_five_wrong_codes_kill_the_code(client):
    _notebook(client)
    local = _local(client)
    local.post("/auth/reset-code")
    for _ in range(5):
        assert _try(local, "000000") == 401
    assert _try(local, CODE) in (401, 429)
    assert local.get("/auth/status").json()["setup_required"] is False


def test_asking_for_codes_again_does_not_reset_the_guess_count(client):
    _notebook(client)
    local = _local(client)
    statuses = []
    for _ in range(12):
        local.post("/auth/reset-code")
        statuses.append(_try(local, "000000"))
    assert 429 in statuses


def test_asking_for_a_code_is_this_computer_only(client, capsys):
    _notebook(client)
    capsys.readouterr()
    assert _lan(client).post("/auth/reset-code").status_code == 403
    tunnelled = _local(client).post("/auth/reset-code", headers={"X-Forwarded-For": "203.0.113.9"})
    assert tunnelled.status_code == 403
    cross = _local(client).post("/auth/reset-code", headers={"Origin": "https://evil.example"})
    assert cross.status_code == 403
    assert CODE not in capsys.readouterr().err


def test_a_code_cannot_be_asked_for_before_a_password_exists(client):
    assert _local(client).post("/auth/reset-code").status_code == 400


def test_the_code_is_kept_only_as_a_hash():
    import inspect

    from tessellate.core import reset_code

    source = inspect.getsource(reset_code)
    assert "compare_digest" in source and "pbkdf2_hmac" in source
    reset_code.issue()
    live = reset_code._state["live"]
    assert live and not hasattr(live[0], "code")
    reset_code._forget()


def test_open_logs_failure_never_names_the_path(client, monkeypatch):
    from fastapi import HTTPException

    from tessellate.api import routes_files

    _notebook(client)

    def refuse(folder, label):
        raise HTTPException(status_code=500, detail=f"Couldn't open {label}. You can find it at {folder}.")

    monkeypatch.setattr(routes_files, "reveal_folder", refuse)
    bad = _local(client).post("/auth/reset-code/open-logs")
    # 503 since audit 1030 Y13: no file manager is the environment, not a server fault.
    assert bad.status_code == 503
    assert "/" not in bad.json()["detail"] and "\\" not in bad.json()["detail"]
