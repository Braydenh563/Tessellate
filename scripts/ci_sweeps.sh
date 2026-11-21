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
# A line is `name seconds [VAR=value ...]`; one VAR holding `|` makes one run per
# value, each under its own timeout (errors and fontmatrix ran 324s and 240s+ whole).
#   bash scripts/ci_sweeps.sh --plan     # print the runs, start nothing
set -uo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"

# One line per run: the sweep's name, then its env, with a `|` token expanded.
plan() {
  while read -r name _ env; do
    case "$name" in ""|\#*) continue ;; esac
    split="" fixed=()
    for tok in $env; do
      case "$tok" in *"|"*) split="$tok" ;; *) fixed+=("$tok") ;; esac
    done
    if [ -z "$split" ]; then echo "$name ${fixed[*]}"; continue; fi
    var="${split%%=*}"
    IFS='|' read -ra values <<< "${split#*=}"
    for v in "${values[@]}"; do echo "$name ${fixed[*]} $var=$v"; done
  done < scratchpad/ui-sweeps/stable.txt
}
if [ "${1:-}" = "--plan" ]; then plan | sed 's/  */ /g; s/ $//'; exit 0; fi

PORT="${PORT:-8781}"
DATA="$(mktemp -d)"
LOGS="${SWEEP_LOGS:-$ROOT/.sweeps}"
mkdir -p "$LOGS"
failed=()

bash scratchpad/ui-sweeps/serve.sh "$PORT" "$DATA/sweeps" || exit 1
export BASE="http://127.0.0.1:$PORT"
n=0
while read -r name env; do
  n=$((n + 1)); label="$name${env:+ $env}"; log="$LOGS/$n-$name.log"
  start=$(date +%s)
  # shellcheck disable=SC2086  # env is VAR=value words by design
  if env $env timeout 300 node "scratchpad/ui-sweeps/$name.js" < /dev/null > "$log" 2>&1; then
    echo "pass  $label  $(( $(date +%s) - start ))s"
  else
    echo "FAIL  $label  $(( $(date +%s) - start ))s (log: $log)"
    tail -20 "$log"
    failed+=("$label")
  fi
done < <(plan)

pgrep -f "[u]vicorn.*--port $PORT" | xargs -r kill
echo "failed: ${failed[*]:-none}"
[ "${#failed[@]}" = 0 ]
