from database.connection import (
    open_database,
    close_database,
    get_connection,
)


def main():
    open_database()

    try:
        with get_connection() as conn:

            # Save research question
            result = conn.execute(
                """
                INSERT INTO research_queries
                    (question, normalized_question)
                VALUES (%s, %s)
                RETURNING id
                """,
                (
                    "Does studying longer improve grades?",
                    "study time and academic performance"
                )
            ).fetchone()

            if result is None:
                raise RuntimeError("The INSERT did not return a research query ID")

            query_id = result[0]
            print("Saved research ID:", query_id)

            # Retrieve it
            saved = conn.execute(
                """
                SELECT id, question, created_at
                FROM research_queries
                WHERE id = %s
                """,
                (query_id,)
            ).fetchone()

            if saved is None:
                raise RuntimeError(f"Could not retrieve research query {query_id}")

            print("Retrieved research:", saved)

            conn.commit()

    finally:
        close_database()


if __name__ == "__main__":
    main()
