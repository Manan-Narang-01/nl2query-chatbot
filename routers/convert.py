# routers/convert.py
import json
from fastapi import APIRouter, HTTPException, Depends
from models.schemas import (
    ConvertQueryRequest,
    ConvertQueryResponse,
    ErrorResponse
)
from engines.llm_engine import convert_query
from db.history         import save_query
from auth.api_key       import verify_api_key

router = APIRouter(prefix="/convert", tags=["Convert"])


# ─── Source DB Query Validator ────────────────────────────────────────────────

def _validate_query_matches_source(query: str, source_db: str) -> tuple[bool, str]:
    """
    Check that the submitted query looks like it belongs to the claimed source DB.
    - MongoDB queries must be valid JSON with 'collection' and 'operation' keys.
    - SQL queries (postgresql/mysql/oracle) must not be MongoDB JSON.
    """
    stripped = query.strip()
    is_json_like = stripped.startswith("{") or stripped.startswith("[")

    if source_db == "mongodb":
        try:
            parsed = json.loads(stripped)
        except json.JSONDecodeError:
            return False, (
                "Source database is MongoDB but the query is not valid JSON. "
                "MongoDB queries must be a JSON object with 'collection' and 'operation' fields."
            )
        if not isinstance(parsed, dict):
            return False, "MongoDB query must be a JSON object, not an array."
        if "collection" not in parsed:
            return False, "MongoDB query is missing the required 'collection' field."
        if "operation" not in parsed:
            return False, "MongoDB query is missing the required 'operation' field."
        return True, ""

    else:
        # postgresql / mysql / oracle — must NOT be a MongoDB JSON object
        if is_json_like:
            try:
                parsed = json.loads(stripped)
                if isinstance(parsed, dict) and "collection" in parsed:
                    return False, (
                        f"Source database is {source_db.upper()} but the query looks like "
                        f"a MongoDB JSON object. Please select MongoDB as the source database."
                    )
            except json.JSONDecodeError:
                pass  # not valid JSON — fine, treat as SQL

        # Basic check: SQL query should contain at least one SQL keyword
        upper = stripped.upper()
        sql_keywords = {"SELECT", "INSERT", "UPDATE", "DELETE", "WITH", "SHOW", "DESCRIBE", "EXPLAIN"}
        if not any(kw in upper for kw in sql_keywords):
            return False, (
                f"The query does not appear to be a valid {source_db.upper()} SQL statement. "
                f"Expected a query starting with SELECT, INSERT, UPDATE, DELETE, etc."
            )

        return True, ""


# ─── POST /convert/ ───────────────────────────────────────────────────────────

@router.post(
    "/",
    response_model=ConvertQueryResponse,
    responses={
        400: {"description": "Query does not match selected source database"},
        401: {"description": "Missing API key"},
        403: {"description": "Invalid API key"},
        500: {"model": ErrorResponse}
    }
)
async def convert(
    request: ConvertQueryRequest,
    api_key: str = Depends(verify_api_key)
):
    """
    Convert a query from one database type to another.
    Supports: postgresql ↔ mysql ↔ mongodb ↔ oracle
    """
    # ── Validate query matches source DB ──────────────────────────────────────
    valid, reason = _validate_query_matches_source(
        query=request.query,
        source_db=request.source_db.value
    )
    if not valid:
        raise HTTPException(status_code=400, detail=reason)

    try:
        result = convert_query(
            query=request.query,
            source_db=request.source_db.value,
            target_db=request.target_db.value
        )

        # ── Ensure converted_query is always a string ─────────────────────────
        converted_query = result["converted_query"]
        if isinstance(converted_query, dict):
            converted_query = json.dumps(converted_query, indent=2)
        elif not isinstance(converted_query, str):
            converted_query = str(converted_query)

        # ── Ensure original query is also a string ────────────────────────────
        original_query = request.query
        if isinstance(original_query, dict):
            original_query = json.dumps(original_query, indent=2)

        # ── Save to history ───────────────────────────────────────────────────
        save_query(
            question         = f"[CONVERT] {request.source_db.value} → {request.target_db.value}",
            db_type          = request.target_db.value,
            generated_query  = converted_query,
            schema_context   = f"Converted from {request.source_db.value}: {str(original_query)[:200]}",
            query_result     = None,
            row_count        = 0,
            execution_status = "preview",
            error_message    = None
        )

        return ConvertQueryResponse(
            original_query  = original_query,
            converted_query = converted_query,
            source_db       = request.source_db.value,
            target_db       = request.target_db.value,
            notes           = result.get("notes")
        )

    except RuntimeError as e:
        raise HTTPException(status_code=500, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Unexpected error: {str(e)}")
