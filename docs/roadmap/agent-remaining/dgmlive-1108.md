# dgmlive-1108: remaining

Branch `agent/dgmlive-1108` (not pushed). Port 8894 was used (8794 was held by another agent's server). Sweeps are in the agent scratch dir, untracked.

Done: items 1 to 5 driven in Chromium; two failures fixed (rename blur stole focus from the dialog title: 9c379da9; Keep leaked through the reused pane's `sidewaysAsked` flag: next commit). Items 1, 4 and 5 passed unchanged. Numbers are in dgmrev-1108.md.

Left:
- Kebab keyboard check covered the block menu and "More for this diagram" in the flowchart and sequence builders; not the embed dialog's own "More" and not the Library rows.
- Live editor click: a double click and a drag across the embed were not driven.
- `tests/test_complexity.py` fails on `src/tessellate/ai/composer_digest.py::answer` (not touched here; came with the merged base), so `gate.sh --staged` reports staged-lints red.
