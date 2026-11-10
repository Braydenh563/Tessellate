"""Forgetting the password: the one reset both doors share (INBOX 663).

There are two ways to reset without the password or a recovery key: the
terminal command (`python -m tessellate --reset-password`, `__main__`) and the
lock screen's "I don't have it" path (`POST /auth/reset`, routes_auth.py).
They must leave the notebook in the same state, so the work is here and both
call it; each door only does its own asking (a typed RESET at a prompt or in
a field) and its own telling.

What a reset keeps and what it loses, which both doors say before it runs:

- Ordinary notes, documents, boards, files and settings are not encrypted
  with the password. They are plain rows, and nothing here touches them.
- Private notes are. Their data key is wrapped by the password (and by a
  recovery key, if one was made), and this removes the wrap, so they stay
  sealed for good. A sealed backup still opens with its own password: that
  file has its own key, not this one.
- "Allow other devices on this network" goes off (SEC-01): a notebook
  without a password is never reachable from the network.
"""

from __future__ import annotations

from dataclasses import dataclass

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from tessellate.core import netbind
from tessellate.core.config import ConfigManager
from tessellate.core.database import Entry, User, Vault


@dataclass(frozen=True)
class ResetOutcome:
    """What a reset did, for the door that ran it to say."""

    had_password: bool
    private_notes: int
    lan_was_on: bool


def private_note_count(session: Session) -> int:
    """How many notes a reset leaves sealed. Every space, deleted or not:
    a note in the bin is sealed the same way."""
    session.info["workspace_id"] = "all"
    return session.scalar(
        select(func.count(Entry.id)).where(Entry.is_private == True)  # noqa: E712
    ) or 0


def reset_password(session: Session, config: ConfigManager) -> ResetOutcome:
    """Clear the password so setup runs again, and commit.

    The user row goes (the next start asks for a new password), every vault
    row goes (a wrap whose password is gone would make the next setup reuse
    a vault it cannot open), and LAN mode is turned off. Sessions held in
    memory are the caller's to end: the terminal runs in another process,
    and the running server ends its own (`routes_auth.reset`).
    """
    user = session.scalar(select(User))
    if user is None:
        return ResetOutcome(had_password=False, private_notes=0, lan_was_on=False)
    private_notes = private_note_count(session)
    session.delete(user)
    lan_was_on = netbind.lan_enabled(config)
    if lan_was_on:
        config.set_preference(netbind.LAN_PREF, False)
    for row in session.scalars(select(Vault)):
        session.delete(row)
    session.commit()
    # The PIN wraps the key of the vault just deleted: the terminal reset
    # runs where the OS store is the same user's, so it goes here too.
    from tessellate.core import hellostore, pinstore

    pinstore.forget(config.data_dir)
    hellostore.forget(config.data_dir)  # the Hello record wraps the same key
    return ResetOutcome(had_password=True, private_notes=private_notes, lan_was_on=lan_was_on)
