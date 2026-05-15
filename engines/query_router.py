# engines/query_router.py
import json
import re
import sys
import os
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from db.postgres import run_postgres_query
from db.mysql    import run_mysql_query
from db.mongodb  import run_mongo_query
from db.oracle   import run_oracle_query


# ─── Dangerous SQL keyword blocklist ─────────────────────────────────────────

_BLOCKED_SQL_KEYWORDS = {
    "DROP", "TRUNCATE", "ALTER", "CREATE", "GRANT", "REVOKE",
    "EXEC", "EXECUTE", "SHUTDOWN", "LOAD_FILE",
    "INTO OUTFILE", "INTO DUMPFILE", "XP_CMDSHELL",
}

_BLOCKED_MONGO_OPS = {"drop", "createcollection", "dropcollection", "eval"}


def _validate_sql_query(query: str) -> tuple[bool, str]:
    """Block dangerous SQL keywords before execution."""
    clean = re.sub(r'--[^\n]*', ' ', query)
    clean = re.sub(r'/\*.*?\*/', ' ', clean, flags=re.DOTALL)
    upper = clean.upper()

    # Check multi-word phrases first
    for phrase in ("INTO OUTFILE", "INTO DUMPFILE", "XP_CMDSHELL"):
        if phrase in upper:
            return False, f"Query blocked: contains disallowed operation '{phrase}'"

    # Check single keywords
    tokens = set(re.findall(r'\b\w+\b', upper))
    for kw in _BLOCKED_SQL_KEYWORDS - {"INTO OUTFILE", "INTO DUMPFILE", "XP_CMDSHELL"}:
        if kw in tokens:
            return False, f"Query blocked: contains disallowed keyword '{kw}'"

    return True, ""


def _validate_mongo_query(query: dict) -> tuple[bool, str]:
    """Block dangerous MongoDB operations before execution."""
    op = str(query.get("operation", "")).lower().strip()
    if op in _BLOCKED_MONGO_OPS:
        return False, f"Query blocked: operation '{op}' is not allowed"
    return True, ""


def route_and_execute(query: str, db_type: str) -> dict:
    """
    Route the generated query to the correct database connector
    and return a unified response.

    Args:
        query:   Generated query string (SQL or JSON string for MongoDB)
        db_type: One of postgresql | mysql | mongodb | oracle

    Returns:
        dict with status, data, row_count, error (if any)
    """
    db_type = db_type.lower().strip()

    try:
        if db_type == "postgresql":
            safe, reason = _validate_sql_query(query)
            if not safe:
                return {"status": "error", "data": [], "row_count": 0, "error": reason}
            return run_postgres_query(query)

        elif db_type == "mysql":
            safe, reason = _validate_sql_query(query)
            if not safe:
                return {"status": "error", "data": [], "row_count": 0, "error": reason}
            return run_mysql_query(query)

        elif db_type == "mongodb":
            try:
                query_dict = json.loads(query)
            except json.JSONDecodeError as e:
                return {
                    "status": "error",
                    "data": [],
                    "row_count": 0,
                    "error": f"Invalid MongoDB query JSON: {str(e)}"
                }
            safe, reason = _validate_mongo_query(query_dict)
            if not safe:
                return {"status": "error", "data": [], "row_count": 0, "error": reason}
            return run_mongo_query(query_dict)

        elif db_type == "oracle":
            safe, reason = _validate_sql_query(query)
            if not safe:
                return {"status": "error", "data": [], "row_count": 0, "error": reason}
            return run_oracle_query(query)

        else:
            return {
                "status": "error",
                "data": [],
                "row_count": 0,
                "error": f"Unsupported database type: {db_type}"
            }

    except Exception as e:
        return {
            "status": "error",
            "data": [],
            "row_count": 0,
            "error": str(e)
        }