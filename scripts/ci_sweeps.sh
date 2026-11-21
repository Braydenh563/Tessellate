#!/usr/bin/env bash
# The stable ui sweeps, run in CI on every push (L-general-20). deepflows.js
# joins once its 29 of 68 failing flow runs are fixed (same row).
#
#   bash scripts/ci_sweeps.sh            # VENV is the python prefix (CI: $pythonLocation)
#
# "Stable" is scratchpad/ui-sweeps/stable.txt: the gate's sweeps that passed twice
# running on a fresh data dir with nothing else on the box. The rest need a seeded
# notebook, a slow model or an idle machine, and stay on `gate.sh --sweeps`. A sweep
# that turns flaky is taken off the list with its reason, never retried until green.
set -uo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"
PORT="${PORT:-8781}"
DATA="$(mktemp -d)"
LOGS="${SWEEP_LOGS:-$ROOT/.sweeps}"
mkdir -p "$LOGS"
failed=()

bash scratchpad/ui-sweeps/serve.sh "$PORT" "$DATA/sweeps" || exit 1
export BASE="http://127.0.0.1:$PORT"
while read -r name _; do
  case "$name" in ""|\#*) continue ;; esac
  start=$(date +%s)
  if timeout 300 node "scratchpad/ui-sweeps/$name.js" > "$LOGS/$name.log" 2>&1; then
    echo "pass  $name  $(( $(date +%s) - start ))s"
  else
    echo "FAIL  $name  $(( $(date +%s) - start ))s (log: $LOGS/$name.log)"
    tail -20 "$LOGS/$name.log"
    failed+=("$name")
  fi
done < scratchpad/ui-sweeps/stable.txt

pgrep -f "[u]vicorn.*--port $PORT" | xargs -r kill
echo "failed: ${failed[*]:-none}"
[ "${#failed[@]}" = 0 ]
