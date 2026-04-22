# routers/schema.py
from fastapi import APIRouter, HTTPException, Depends
from models.schemas import (
    SchemaSuggestionRequest,
    SchemaSuggestionResponse,
    TableSchema,
    TableColumn,
    ErrorResponse
)
from engines.llm_engine import suggest_schema
from db.history         import save_query
from auth.api_key       import verify_api_key

router = APIRouter(prefix="/schema", tags=["Schema"])


@router.post(
    "/suggest",
    response_model=SchemaSuggestionResponse,
    responses={
        401: {"description": "Missing API key"},
        403: {"description": "Invalid API key"},
        500: {"model": ErrorResponse}
    }
)
async def schema_suggest(
    request: SchemaSuggestionRequest,
    api_key: str = Depends(verify_api_key)
):
    """
    Analyze requirements and generate a complete database schema.
    Returns tables, columns, relationships, CREATE scripts and optional sample data.
    """
    try:
        result = suggest_schema(
            requirement         = request.requirement,
            db_type             = request.db_type.value,
            include_sample_data = request.include_sample_data
        )

        # ── Parse tables ──────────────────────────────────────────────────────
        tables = []
        for t in result.get("tables", []):
            columns = [
                TableColumn(
                    name        = col.get("name", ""),
                    type        = col.get("type", ""),
                    constraints = col.get("constraints"),
                    description = col.get("description")
                )
                for col in t.get("columns", [])
            ]
            tables.append(
                TableSchema(
                    table_name  = t.get("table_name", ""),
                    description = t.get("description", ""),
                    columns     = columns,
                    indexes     = t.get("indexes", [])
                )
            )

        # ── Save to history ───────────────────────────────────────────────────
        save_query(
            question         = f"[SCHEMA] {request.requirement[:100]}",
            db_type          = request.db_type.value,
            generated_query  = result.get("create_scripts", ""),
            schema_context   = request.requirement,
            query_result     = None,
            row_count        = len(tables),
            execution_status = "preview",
            error_message    = None
        )

        return SchemaSuggestionResponse(
            requirement   = request.requirement,
            db_type       = request.db_type.value,
            tables        = tables,
            relationships = result.get("relationships", []),
            create_scripts= result.get("create_scripts", ""),
            sample_data   = result.get("sample_data"),
            design_notes  = result.get("design_notes")
        )

    except RuntimeError as e:
        raise HTTPException(status_code=500, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Unexpected error: {str(e)}")