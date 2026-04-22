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


@router.post(
    "/",
    response_model=ConvertQueryResponse,
    responses={
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
            query_result     = None,        # ← always None for conversions
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
        raise HTTPException(status_code=500, detail=f"Unexpected error: {str(e)}")# routers/convert.py
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


@router.post(
    "/",
    response_model=ConvertQueryResponse,
    responses={
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
            query_result     = None,        # ← always None for conversions
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