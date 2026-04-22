# routers/chat.py
from fastapi import APIRouter, HTTPException, Depends
from models.schemas import (
    ChatRequest, ChatResponse,
    QueryPreviewRequest, QueryPreviewResponse,
    ErrorResponse
)
from engines.llm_engine   import generate_query
from engines.query_router import route_and_execute
from db.history           import save_query
from auth.api_key         import verify_api_key        # ← NEW

router = APIRouter(prefix="/chat", tags=["Chat"])


# ─── POST /chat ───────────────────────────────────────────────────────────────

@router.post(
    "/",
    response_model=ChatResponse,
    responses={
        401: {"description": "Missing API key"},
        403: {"description": "Invalid API key"},
        500: {"model": ErrorResponse}
    }
)
async def chat(
    request: ChatRequest,
    api_key: str = Depends(verify_api_key)     # ← protected
):
    try:
        generated_query = generate_query(
            question       = request.question,
            db_type        = request.db_type.value,
            schema_context = request.schema_context
        )
        db_result = route_and_execute(
            query   = generated_query,
            db_type = request.db_type.value
        )
        save_query(
            question         = request.question,
            db_type          = request.db_type.value,
            generated_query  = generated_query,
            schema_context   = request.schema_context,
            query_result     = db_result.get("data", []),
            row_count        = db_result.get("row_count", 0),
            execution_status = db_result.get("status", "error"),
            error_message    = db_result.get("error")
        )
        return ChatResponse(
            question         = request.question,
            db_type          = request.db_type.value,
            generated_query  = generated_query,
            query_result     = db_result.get("data", []),
            row_count        = db_result.get("row_count", 0),
            execution_status = db_result.get("status", "error"),
            error_message    = db_result.get("error")
        )
    except RuntimeError as e:
        raise HTTPException(status_code=500, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Unexpected error: {str(e)}")


# ─── POST /chat/preview ───────────────────────────────────────────────────────

@router.post(
    "/preview",
    response_model=QueryPreviewResponse,
    responses={
        401: {"description": "Missing API key"},
        403: {"description": "Invalid API key"},
        500: {"model": ErrorResponse}
    }
)
async def preview_query(
    request: QueryPreviewRequest,
    api_key: str = Depends(verify_api_key)     # ← protected
):
    try:
        generated_query = generate_query(
            question       = request.question,
            db_type        = request.db_type.value,
            schema_context = request.schema_context
        )
        save_query(
            question         = request.question,
            db_type          = request.db_type.value,
            generated_query  = generated_query,
            schema_context   = request.schema_context,
            execution_status = "preview"
        )
        return QueryPreviewResponse(
            question        = request.question,
            db_type         = request.db_type.value,
            generated_query = generated_query
        )
    except RuntimeError as e:
        raise HTTPException(status_code=500, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Unexpected error: {str(e)}")