"""Test helper: a `/chat/tools/execute` body as the server would have handed it out (signed, L566)."""

from __future__ import annotations

from tessellate.ai import consent_store


def call(name: str, arguments: dict | None = None, steps: list | None = None) -> dict:
    """`{"name", "arguments", "steps", "sig"}` with this process's tag, so the route runs it."""
    return {
        "name": name,
        "arguments": arguments or {},
        "steps": steps or [],
        "sig": consent_store.sign_call(name, arguments or {}, steps or []),
    }
