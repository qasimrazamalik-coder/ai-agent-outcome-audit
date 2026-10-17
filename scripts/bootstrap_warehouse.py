"""Build the upstream cx-journey-warehouse and copy its DuckDB file into data/.

    python scripts/bootstrap_warehouse.py [--scale 1.0] [--repo PATH_OR_URL]

By default it clones https://github.com/qasimrazamalik-coder/cx-journey-warehouse into
.cache/ and runs its build. Pass --repo with a local path to use a checkout you already have.
"""

from __future__ import annotations

import argparse
import shutil
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_REPO = "https://github.com/qasimrazamalik-coder/cx-journey-warehouse.git"


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--repo", default=DEFAULT_REPO)
    parser.add_argument("--scale", default="1.0")
    args = parser.parse_args()

    if Path(args.repo).exists():
        upstream = Path(args.repo).resolve()
    else:
        upstream = ROOT / ".cache" / "cx-journey-warehouse"
        if upstream.exists():
            subprocess.run(["git", "-C", str(upstream), "pull", "--ff-only", "-q"], check=True)
        else:
            upstream.parent.mkdir(parents=True, exist_ok=True)
            subprocess.run(["git", "clone", "--depth", "1", "-q", args.repo, str(upstream)], check=True)

    out = ROOT / "data" / "warehouse.duckdb"
    out.parent.mkdir(exist_ok=True)
    built = upstream / "warehouse_for_audit.duckdb"
    subprocess.run(
        [sys.executable, "scripts/build.py", "--scale", args.scale, "--db", str(built), "--skip-report"],
        cwd=upstream, check=True,
    )
    shutil.copyfile(built, out)
    built.unlink()
    print(f"warehouse ready: {out}")


if __name__ == "__main__":
    main()
