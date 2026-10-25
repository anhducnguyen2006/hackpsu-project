"""Generate local-model semantic links between saved research questions.

Run from backend with:
    PYTHONPATH=. ../.venv/bin/python scripts/build_research_connections.py

The default 0.75 cosine threshold is a heuristic starting point and should be
calibrated against representative questions. This command never calls Gemini.
"""

from __future__ import annotations

import argparse

from app.research.semantic_connections import (
    DEFAULT_MAX_NEIGHBORS,
    DEFAULT_SIMILARITY_THRESHOLD,
    generate_semantic_connections,
)
from database.connection import close_database, open_database


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--threshold",
        type=float,
        default=DEFAULT_SIMILARITY_THRESHOLD,
        help="Minimum cosine similarity; default: %(default)s",
    )
    parser.add_argument(
        "--max-neighbors",
        type=int,
        default=DEFAULT_MAX_NEIGHBORS,
        help="Maximum nearest neighbors per question; default: %(default)s",
    )
    args = parser.parse_args()
    if not 0 <= args.threshold <= 1:
        parser.error("--threshold must be between 0 and 1")
    if args.max_neighbors <= 0:
        parser.error("--max-neighbors must be positive")

    open_database()
    try:
        result = generate_semantic_connections(
            similarity_threshold=args.threshold,
            max_neighbors=args.max_neighbors,
        )
    finally:
        close_database()
    print(
        "semantic connections complete "
        f"model={result.model_identifier} "
        f"dimensions={result.embedding_dimensions} "
        f"threshold={result.similarity_threshold} "
        f"max_neighbors={result.max_neighbors} "
        f"source_questions={result.source_questions} "
        f"missing_embeddings={result.missing_embeddings} "
        f"incompatible_model_embeddings={result.incompatible_model_embeddings} "
        f"connections_generated={result.connections_generated}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
