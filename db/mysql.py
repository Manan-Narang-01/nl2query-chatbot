# db/mysql.py
import pymysql
import pymysql.cursors
from typing import Any
from config import settings


def get_mysql_connection():
    """Create and return a MySQL connection."""
    try:
        conn = pymysql.connect(
            host=settings.MYSQL_HOST,
            port=settings.MYSQL_PORT,
            user=settings.MYSQL_USER,
            password=settings.MYSQL_PASSWORD,
            database=settings.MYSQL_DATABASE,
            cursorclass=pymysql.cursors.DictCursor
        )
        return conn
    except pymysql.OperationalError as e:
        raise ConnectionError(f"MySQL connection failed: {str(e)}")


def run_mysql_query(query: str) -> dict[str, Any]:
    """Execute a query and return rows as list of dicts."""
    conn = None
    cursor = None
    try:
        conn = get_mysql_connection()
        cursor = conn.cursor()
        cursor.execute(query)

        if query.strip().upper().startswith("SELECT"):
            rows = cursor.fetchall()
            result = list(rows)
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