# engines/query_router.py
import json
import sys
import os
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from db.postgres import run_postgres_query
from db.mysql    import run_mysql_query
from db.mongodb  import run_mongo_query
from db.oracle   import run_oracle_query


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
            return run_postgres_query(query)

        elif db_type == "mysql":
            return run_mysql_query(query)

        elif db_type == "mongodb":
            # MongoDB expects a dict, not a string
            try:
                query_dict = json.loads(query)
            except json.JSONDecodeError as e:
                return {
                    "status": "error",
                    "data": [],
                    "row_count": 0,
                    "error": f"Invalid MongoDB query JSON: {str(e)}"
                }
            return run_mongo_query(query_dict)

        elif db_type == "oracle":
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