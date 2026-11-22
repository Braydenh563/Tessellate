"""INBOX 527: argument-error specificity, coercion and malformed-JSON recovery,
measured against the real registry (no model). Run:
    PYTHONPATH=src .venv/bin/python scratchpad/harness_argmeasure.py
"""
import logging
import tempfile
from pathlib import Path

from tessellate.ai import tools
from tessellate.ai.provider import normalise_tool_calls
from tessellate.ai import wiring  # noqa: F401
from tessellate.core import deps
from tessellate.entry import manager

logging.disable(logging.WARNING)
deps.init_app_state(data_dir=Path(tempfile.mkdtemp()))
s = deps.get_db().session()
e = manager.create_entry(s, "plumber invoice", "Work", [])
s.commit()

named = total = 0
vague = []
for name, spec in tools.TOOLS.items():
    req = spec.parameters.get("required") or []
    if not req or spec.destructive or spec.ends_turn:
        continue
    total += 1
    err = str(tools.execute_tool(s, name, {}).get("error", ""))
    if any(p in err for p in req):
        named += 1
    else:
        vague.append((name, err[:90]))
print(f"missing-required errors naming the parameter: {named}/{total}")
for v in vague[:6]:
    print("  ", v)

ok = tot = 0
for name, args in (
    ("get_note", {"note_id": str(e.id)}),
    ("pin_note", {"note_id": str(e.id), "pinned": "true"}),
    ("tag_note", {"note_id": e.id, "tags": "urgent"}),
    ("get_note", {"id": e.id}),
):
    r = tools.execute_tool(s, name, args)
    tot += 1
    ok += "error" not in r
    print("  ", name, args, "->", r.get("error"))
print(f"string-typed / scalar-for-array / misnamed arguments accepted: {ok}/{tot}")

mal = [
    '{"title": "x", "content": "y",}',
    "{'content': 'milk'}",
    '{"content": "milk"',
    '```json\n{"content": "milk"}\n```',
    '{"content": "milk", "pinned": True}',
]
got = sum(
    bool(normalise_tool_calls([{"function": {"name": "create_note", "arguments": m}}])[0]["arguments"])
    for m in mal
)
print(f"malformed argument strings recovered: {got}/{len(mal)}")
