"""Create a new Alembic revision with sequential naming.

Alembic's post-write hooks cannot rename files because Alembic re-loads
the file from its original path after the hook completes.  This script
wraps `alembic revision`, waits for it to finish, then renames the result:

    YYYYMMDD_<rev>_<slug>.py  →  YYYYMMDD_NNNN_<rev>_<slug>.py

Usage
-----
    python alembic/new_migration.py "my migration message"

Or via make (preferred):
    make migration MSG="my migration message"
"""

from __future__ import annotations

import glob
import os
import re
import subprocess
import sys

from src.core.logging import get_logger, setup_logging

setup_logging()
logger = get_logger(__name__).bind(process="alembic_new_migration")


def main() -> None:
    """Run alembic revision and rename the output file."""
    msg = " ".join(sys.argv[1:]) if len(sys.argv) > 1 else "migration"
    versions_dir = os.path.join(os.path.dirname(__file__), "versions")

    result = subprocess.run(
        ["alembic", "revision", "-m", msg],
        capture_output=True,
        text=True,
    )
    logger.info("alembic.revision_command_completed", returncode=result.returncode)
    # Always forward stderr (contains Alembic progress messages)
    if result.stderr:
        logger.info("alembic.revision_stderr", output=result.stderr)
    if result.returncode != 0:
        sys.exit(result.returncode)

    # Alembic prints: "Generating /full/path/to/file ...  done"
    match = re.search(r"Generating (.+?) \.\.\.", result.stdout + result.stderr)
    if not match:
        logger.warning("alembic.revision_output_unmatched", output=result.stdout)
        return

    script_path = match.group(1).strip()
    basename = os.path.basename(script_path)

    # Count all existing migration files; the new one is already on disk.
    all_py = [
        f
        for f in glob.glob(os.path.join(versions_dir, "*.py"))
        if not os.path.basename(f).startswith("__")
    ]
    seq = len(all_py)

    # Insert sequential number: YYYYMMDD_rev_slug → YYYYMMDD_NNNN_rev_slug
    date_prefix, remainder = basename.split("_", 1)
    new_basename = f"{date_prefix}_{seq:04d}_{remainder}"
    new_path = os.path.join(versions_dir, new_basename)

    os.rename(script_path, new_path)
    logger.info(
        "alembic.revision_created",
        filename=new_basename,
        path=new_path,
    )


if __name__ == "__main__":
    main()
