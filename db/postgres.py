# db/postgres.py
import psycopg2
import psycopg2.extras
from typing import Any
from config import settings


def get_postgres_connection():
    """Create and return a PostgreSQL connection."""
    try:
        conn = psycopg2.connect(
            host=settings.PG_HOST,
            port=settings.PG_PORT,
            user=settings.PG_USER,
            password=settings.PG_PASSWORD,
            database=settings.PG_DATABASE
        )
        return conn
    except psycopg2.OperationalError as e:
        raise ConnectionError(f"PostgreSQL connection failed: {str(e)}")


def run_postgres_query(query: str) -> dict[str, Any]:
    """Execute a query and return rows as list of dicts."""
    conn = None
    cursor = None
    try:
        conn = get_postgres_connection()
        cursor = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
        cursor.execute(query)

        # Handle SELECT vs INSERT/UPDATE/DELETE
        if query.strip().upper().startswith("SELECT"):
            rows = cursor.fetchall()
            result = [dict(row) for row in rows]
        else:
            conn.commit()
            result = [{"affected_rows": cursor.rowcount}]

        return {
            "status": "success",
            "data": result,
            "row_count": len(result)
        }

    except Exception as e:
        if conn:
            conn.rollback()
        return {
            "status": "error",
            "data": [],
            "row_count": 0,
            "error": str(e)
        }
    finally:
        if cursor:
            cursor.close()
        if conn:
            conn.close()