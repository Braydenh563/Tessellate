"""Regenerate src/tessellate/api/route_table.py, the lazy router rows' path templates.

Run after adding, moving or renaming a route in a module outside
`lazy_routes.BOOT_MODULES`; `tests/test_lazy_routes.py` fails until you do.

    PYTHONPATH=src python scripts/route_table.py
"""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
TABLE = ROOT / "src" / "tessellate" / "api" / "route_table.py"


def main() -> None:
    sys.path.insert(0, str(ROOT / "src"))
    from tessellate.api import lazy_routes
    from tessellate.api.app import ROUTER_ROWS

    TABLE.write_text(lazy_routes.render_table(lazy_routes.build_table(ROUTER_ROWS)), encoding="utf-8")
    print(f"wrote {TABLE.relative_to(ROOT)}")


if __name__ == "__main__":
    main()
