"""SEC-A3 and SEC-A4: no credentials in the audit log, no crash on a bad Origin."""

from __future__ import annotations

import pytest
from sqlalchemy import select

from tessellate.core import deps
from tessellate.core.database import AuditLog


def test_a_model_address_typed_with_a_password_is_logged_without_it(ai_client):
    reply = ai_client.post(
        "/models/provider", json={"provider": "ollama", "base_url": "http://bob:hunter2secret@127.0.0.1:11434"}
    )
    assert reply.status_code == 200, reply.text
    session = deps.get_db().session()
    try:
        details = [row for row in session.scalars(select(AuditLog.detail)) if row and "llm_provider" in row]
    finally:
        session.close()
    assert details
    assert not any("hunter2secret" in d or "bob" in d for d in details)
    assert any("127.0.0.1:11434" in d for d in details)


@pytest.mark.parametrize("origin", ["http://x:abc", "http://127.0.0.1:8791.evil.example", "http://x:99999"])
def test_a_malformed_port_in_origin_is_a_refusal_not_a_crash(client, origin):
    reply = client.post("/auth/lock", headers={"Origin": origin})
    assert reply.status_code == 403
