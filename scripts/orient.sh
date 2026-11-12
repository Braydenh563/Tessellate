#!/usr/bin/env bash
# Session orientation in under 40 lines (SessionStart hook; also runnable by hand).
# bash, grep, sed, head only, so it works in any sandbox and finishes well under a second.
cd "$(dirname "$0")/.." || exit 0
H=docs/roadmap/HANDOVER.md
echo "== Now (HANDOVER) =="
sed -n '/^\*\*Now (/,/^$/p' "$H" | head -12 | sed 's/^\(.\{200\}\).*/\1.../'
echo "== Owner notes (HANDOVER, above the first heading) =="
sed -n '/^## /q;/^> \*\*/p' "$H" | head -10 | sed 's/^\(.\{200\}\).*/\1.../'
echo "== Agent cap (CLAUDE.md standing order 4) =="
sed ':a;N;$!ba;s/\n/ /g;s/  */ /g' CLAUDE.md | grep -o 'The agent cap is[^.]*\.[^.]*\.' | head -1
echo "== Counts =="
echo "open INBOX items: $(grep -c '^[0-9][0-9]*\. \*\*' docs/roadmap/INBOX.md)"
echo "uncommitted paths: $(git status --short 2>/dev/null | wc -l)"
echo "== LEDGER (docs/roadmap/LEDGER.md: every open item outside the plans) =="
grep -E '^\| all \|' docs/roadmap/LEDGER.md | sed 's/^/plan open, ledger open, partly, owner calls, hardware, total: /'
echo "== Last retro (.claude/skills/retro/ledger.md; run the retro skill at session end) =="
tail -1 .claude/skills/retro/ledger.md 2>/dev/null | cut -c1-200
exit 0
