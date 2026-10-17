"""Run the bot outcome audit end to end.

    python scripts/run_audit.py            # assumes data/warehouse.duckdb exists
    python scripts/run_audit.py --bootstrap --scale 0.15   # build the warehouse first

Steps: dbt build (models + tests) -> statistics and cost model -> charts, report and
results.json in reports/.
"""

from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from audit.analysis import run_analysis  # noqa: E402


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--bootstrap", action="store_true", help="build the upstream warehouse first")
    parser.add_argument("--scale", default="1.0")
    args = parser.parse_args()

    py = sys.executable
    if args.bootstrap:
        subprocess.run([py, "scripts/bootstrap_warehouse.py", "--scale", args.scale], cwd=ROOT, check=True)
    warehouse = ROOT / "data" / "warehouse.duckdb"
    if not warehouse.exists():
        sys.exit("data/warehouse.duckdb not found: run with --bootstrap or scripts/bootstrap_warehouse.py")

    audit_db = ROOT / "data" / "audit.duckdb"
    if audit_db.exists():
        audit_db.unlink()
    env = dict(os.environ, CX_WAREHOUSE_PATH=str(warehouse), AUDIT_DB_PATH=str(audit_db))
    result = subprocess.run([py, "-c", "from dbt.cli.main import cli; cli()", "build", "--profiles-dir", "."],
                            cwd=ROOT / "dbt", env=env)
    if result.returncode != 0:
        sys.exit(result.returncode)

    results = run_analysis(audit_db, ROOT / "config" / "assumptions.yml", ROOT / "reports")
    print(json.dumps(results["headline"], indent=2))


if __name__ == "__main__":
    main()
