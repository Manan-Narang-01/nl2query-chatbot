# db/oracle.py
import oracledb
from typing import Any
from config import settings


def get_oracle_connection():
    """Create and return an Oracle DB connection."""
    try:
        conn = oracledb.connect(
            user=settings.ORACLE_USER,
            password=settings.ORACLE_PASSWORD,
            dsn=settings.ORACLE_DSN
        )
        return conn
    except oracledb.DatabaseError as e:
        raise ConnectionError(f"Oracle connection failed: {str(e)}")


def run_oracle_query(query: str) -> dict[str, Any]:
    """Execute a query and return rows as list of dicts."""
    conn = None
    cursor = None
    try:
        conn = get_oracle_connection()
        cursor = conn.cursor()
        cursor.execute(query)

        if query.strip().upper().startswith("SELECT"):
            columns = [col[0].lower() for col in cursor.description]
            rows = cursor.fetchall()
            result = [dict(zip(columns, row)) for row in rows]
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