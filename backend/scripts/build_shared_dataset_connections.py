"""Generate research-question links from exact shared dataset matches.

Run from backend with:
    PYTHONPATH=. ../.venv/bin/python scripts/build_shared_dataset_connections.py

This command uses only query_dataset_matches and datasets relationships. It
does not call Gemini, download datasets, or compute profiles.
"""

from __future__ import annotations

from app.research.shared_dataset_connections import generate_shared_dataset_connections
from database.connection import close_database, open_database


def main() -> int:
    open_database()
    try:
        result = generate_shared_dataset_connections()
    finally:
        close_database()
    print(
        "shared dataset connections complete "
        f"query_pairs_considered={result.query_pairs_considered} "
        f"connections_generated={result.connections_generated}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
