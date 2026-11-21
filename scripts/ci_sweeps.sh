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
# value, each under its own timeout (errors ran 324s whole, the font matrix 45 minutes).
#   bash scripts/ci_sweeps.sh --plan     # print the runs, start nothing
#   SLICE=2/4 bash scripts/ci_sweeps.sh  # the second of four shares (CI's matrix)
set -uo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"

# One line per run: its seconds, the sweep's name, then its env, a `|` token expanded.
runs() {
  while read -r name secs env; do
    case "$name" in ""|\#*) continue ;; esac
    secs="${secs%s}" split="" fixed=()
    for tok in $env; do
      case "$tok" in *"|"*) split="$tok" ;; *) fixed+=("$tok") ;; esac
    done
    if [ -z "$split" ]; then echo "$secs $name ${fixed[*]}"; continue; fi
    var="${split%%=*}"
    IFS='|' read -ra values <<< "${split#*=}"
    for v in "${values[@]}"; do echo "$secs $name ${fixed[*]} $var=$v"; done
  done < scratchpad/ui-sweeps/stable.txt
}
# SLICE=k/n keeps the k-th of n shares (CI runs one job per share): longest
# run first, each to the share with the fewest seconds so far, so the shares
# come out within one run of each other. The runs keep the list's order.
plan() {
  if [ -z "${SLICE:-}" ]; then runs | cut -d' ' -f2- | sed 's/  */ /g; s/ $//'; return; fi
  runs | awk -v k="${SLICE%/*}" -v n="${SLICE#*/}" '
    { secs[NR] = $1; $1 = ""; line[NR] = substr($0, 2) }
    END {
      for (i = 1; i <= NR; i++) order[i] = i
      for (i = 2; i <= NR; i++) for (j = i; j > 1 && secs[order[j]] > secs[order[j-1]]; j--) { t = order[j]; order[j] = order[j-1]; order[j-1] = t }
      for (s = 1; s <= n; s++) load[s] = 0
      for (i = 1; i <= NR; i++) { best = 1; for (s = 2; s <= n; s++) if (load[s] < load[best]) best = s; load[best] += secs[order[i]]; mine[order[i]] = (best == k) }
      for (i = 1; i <= NR; i++) if (mine[i]) print line[i]
    }' | sed 's/  */ /g; s/ $//'
}
if [ "${1:-}" = "--plan" ]; then plan; exit 0; fi
# --runs NAME: the env of each run of one sweep, one line per run (an empty
# line for a sweep with no env, or one not on the list), for gate.sh --sweeps.
if [ "${1:-}" = "--runs" ]; then
  out=$(SLICE="" plan | awk -v name="$2" '$1 == name { $1 = ""; print substr($0, 2) }')
  printf '%s\n' "$out"; exit 0
fi

PORT="${PORT:-8781}"
DATA="$(mktemp -d)"
LOGS="${SWEEP_LOGS:-$ROOT/.sweeps}"
mkdir -p "$LOGS"
failed=()

bash scratchpad/ui-sweeps/serve.sh "$PORT" "$DATA/sweeps" || exit 1
export BASE="http://127.0.0.1:$PORT"
# The seeded sweeps (libreader, libreadingfoot) write their readings into the
# served notebook's database, so they are told where it is.
export DATA="$DATA/sweeps"
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
