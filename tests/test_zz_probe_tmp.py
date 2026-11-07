import datetime as dt
import pytest
from tessellate.api import routes_chat
from tessellate.core import config
from tessellate.entry import manager
from tests.test_composer_route_688 import _ask
from tests import _seed_r2_1107 as seed

NOW = dt.datetime(2026, 11, 7, 10, 0, 0)
QS = ["last item in my todo","how many notes do I have","what is my oldest note","what is my longest note","what is my shortest note","hi","what is my number","do I have notes without tags","show me notes without a title","what is not done in Todo","untick bread","undo","redo"]

def test_probe(client, session, monkeypatch):
    monkeypatch.setattr(config, "user_now", lambda _c: NOW)
    monkeypatch.setattr(routes_chat, "user_now", lambda _c: NOW)
    for n in seed.notes:
        e = manager.create_entry(session, n["content"], "Personal")
        e.created_at = e.updated_at = dt.datetime.fromisoformat(n["created_at"].rstrip("Z"))
    session.commit()
    with open("PROBEOUT.txt","w") as f:
        for chat in (False, True):
            for q in QS:
                r = _ask(client, q, **({} if chat else {"notes_only": True, "answer_from": "notes"}))["text"]
                f.write(f"[{'chat' if chat else 'ask'}] {q!r} -> {r!r}\n")
