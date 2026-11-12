#!/usr/bin/env bash
# The ui sweeps that pass steadily, then deepflows.js, against fresh notebooks
# (L-general-20). CI runs this on every push; locally:
#   NODE_PATH=... bash scripts/ci_sweeps.sh /tmp/ci-sweeps
# The list is the sweeps that exited 0 in under a minute in the 2026-11-12
# stability run, in the order they ran (some read state an earlier one left).
# A sweep or flow joins once it passes; L-general-47 repairs the rest (deepflows'
# note, private, link, graph, settings, tabs and picker among them).
FLOWS=mindmap,whiteboard,document,ask,notifications,dashboard,palette,select,views,find
set -uo pipefail
DIR="${1:?scratch dir}"
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
STABLE=(docks contrast leaks keyboard diskspace vibecheck graphminimap wbgroupguides
  phonehead phoneswipe phonenotepage phoneshare phonedocs phonereminders wbphone
  draftreadonly hoveronly wbtopbar820 docdaily docfallback doctabs mindmapcurve
  wbtopbar tagoffer imagecardfoot maptwokinds animcost mapdoors libtlscroll wbshapetext
  touch phonesidebar phonecapture spinners companionbeats companionactease companionblend
  companioncollapse companionemotes companionentry companionlegs companionsay
  doccodecopy dockeyboard graphphone slashicons wbexportimage ctrlwheelzoom companionfade companiontabs)
failed=()
bash "$ROOT/scratchpad/ui-sweeps/serve.sh" ${SWEEP_PORT:-8781} "$DIR/sweeps" || exit 1
for name in "${STABLE[@]}"; do
  start=$SECONDS
  if BASE=http://127.0.0.1:${SWEEP_PORT:-8781} timeout 180 node "$ROOT/scratchpad/ui-sweeps/$name.js" > "$DIR/$name.log" 2>&1; then
    echo "ok   $name $((SECONDS - start))s"
  else
    echo "FAIL $name $((SECONDS - start))s"; tail -n 20 "$DIR/$name.log"; failed+=("$name")
  fi
done
bash "$ROOT/scratchpad/ui-sweeps/serve.sh" ${FLOW_PORT:-8802} "$DIR/deepflows" || exit 1
if BASE=http://127.0.0.1:${FLOW_PORT:-8802} node "$ROOT/scratchpad/ui-sweeps/deepflows-seed.js" > "$DIR/seed.log" 2>&1 \
  && BASE=http://127.0.0.1:${FLOW_PORT:-8802} ONLY=$FLOWS WIDTHS=1440 THEMES=light timeout 900 node "$ROOT/scratchpad/ui-sweeps/deepflows.js" > "$DIR/deepflows.log" 2>&1; then
  echo "ok   deepflows"
else
  echo "FAIL deepflows"; tail -n 40 "$DIR/seed.log" "$DIR/deepflows.log"; failed+=(deepflows)
fi
[ ${#failed[@]} -eq 0 ] || { echo "failed: ${failed[*]}"; exit 1; }
