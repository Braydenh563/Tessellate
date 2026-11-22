"""A settings switch is pressed as itself, not as the n-th checkbox (L-general-74).

The settings sweep listed the switches, then pressed an id-less one by its
index among every checkbox in the modal. A checkbox drawn above it between
the two (a list answering late) moved the index by one, so the press landed
on the next switch: CI put back "Noise suppression" onto "Echo cancellation",
the next put-back saw Echo already on, and one switch "would not go back"
(CI #246, 4 of 4 runs of slice 4). The microphone switches were the only
id-less switches in General, which is why they were always the ones.
"""

from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
MEETINGS = (ROOT / "frontend/js/meetings.js").read_text(encoding="utf-8")
FLOWS = (ROOT / "scratchpad/ui-sweeps/deepflows-flows.js").read_text(encoding="utf-8")


def _block(text: str, start: str) -> str:
    return text.split(start, 1)[1].split("\n}\n", 1)[0]


def test_every_microphone_switch_has_an_id_per_host():
    body = MEETINGS.split("function micControlsInto(host) {", 1)[1].split("\n  }\n", 1)[0]
    loop = body.split("for (const [key, name, hint, fallback = true] of MIC_SWITCHES) {", 1)[1]
    assert "box.id = `mic-${tag}-${key}`;" in loop
    # One tag for the device select and the switches, so the two hosts (the
    # recorder's fold and Settings) never share an id.
    assert "const tag = host.id ||" in body and "`mic-device-${tag}`" in body


def test_the_sweep_presses_the_switch_it_found_in_the_same_page_call():
    click = _block(FLOWS, "async function clickSwitch(env, sw) {")
    # No index read in one call and used in a later one.
    assert "querySelectorAll('#settings-modal input[type=\"checkbox\"]')[i]" not in click
    assert "evaluateHandle(switchesInPage" in click
    assert "const switchesHere = (env) => env.js(switchesInPage" in FLOWS
