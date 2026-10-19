"""Back-date seed-stats1319.js's notes: 12 months with a known count each
(Nov 2025 .. Oct 2026 = 3 4 5 2 6 7 9 8 12 10 14 6), the last two notes left on now.
    python seed-stats1319.py <data dir>/tessellate.db"""
import sqlite3
import sys
from datetime import datetime, timedelta
counts = [("2025-11", 3), ("2025-12", 4), ("2026-01", 5), ("2026-02", 2), ("2026-03", 6), ("2026-04", 7),
          ("2026-05", 9), ("2026-06", 8), ("2026-07", 12), ("2026-08", 10), ("2026-09", 14), ("2026-10", 6)]
con = sqlite3.connect(sys.argv[1])
ids = [r[0] for r in con.execute("SELECT id FROM entries ORDER BY id")]
k = 0
for month, n in counts:
    for j in range(n):
        if month == "2026-10":
            day = [2, 5, 8, 13, 14, 16][j]
        else:
            day = 1 + (j * 3) % 27
        when = datetime.fromisoformat(f"{month}-{day:02d} 12:00:00")
        con.execute("UPDATE entries SET created_at=? WHERE id=?", (when.isoformat(sep=" "), ids[k]))
        k += 1
con.commit()
con.execute("UPDATE reminders SET due_at=? WHERE text LIKE 'Late%'", ((datetime.now() - timedelta(days=2)).isoformat(sep=" "),))
con.commit()
print("dated", k, "left on now", len(ids) - k)
