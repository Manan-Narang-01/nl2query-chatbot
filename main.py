# main.py
from contextlib import asynccontextmanager
from fastapi import FastAPI, Depends, Request
from fastapi.middleware.cors import CORSMiddleware
from slowapi import Limiter, _rate_limit_exceeded_handler
from slowapi.util import get_remote_address
from slowapi.errors import RateLimitExceeded
from slowapi.middleware import SlowAPIMiddleware
from routers.chat import router as chat_router
from routers.convert import router as convert_router
from models.schemas import HealthResponse
from routers.schema import router as schema_router
from config import settings
from db.history import (
    get_all_history, get_history_by_db,
    get_history_stats, delete_all_history,
    search_history, init_db
)
from auth.api_key import verify_api_key


# ─── Lifespan ─────────────────────────────────────────────────────────────────

@asynccontextmanager
async def lifespan(app: FastAPI):
    init_db()
    print("SQLite history DB initialized")
    yield
    print("App shutting down")


# ─── Rate Limiter ─────────────────────────────────────────────────────────────

limiter = Limiter(
    key_func=get_remote_address,
    default_limits=["60/minute"]
)


# ─── App Init ─────────────────────────────────────────────────────────────────

app = FastAPI(
    title="NL2Query Chatbot",
    description="Convert natural language to database queries using Groq LLM",
    version="1.0.0",
    docs_url="/docs",
    redoc_url="/redoc",
    lifespan=lifespan
)

app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)
app.add_middleware(SlowAPIMiddleware)


# ─── CORS ─────────────────────────────────────────────────────────────────────

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.ALLOWED_ORIGINS,
    allow_credentials=False,
    allow_methods=["GET", "POST", "DELETE"],
    allow_headers=["X-API-Key", "Content-Type"],
)


# ─── Routers ──────────────────────────────────────────────────────────────────

app.include_router(chat_router)
app.include_router(convert_router)
app.include_router(schema_router)


# ─── Health (public) ──────────────────────────────────────────────────────────

@app.get("/health", response_model=HealthResponse, tags=["Health"])
async def health_check():
    return HealthResponse(
        status="ok",
        version="1.0.0",
        groq_model=settings.GROQ_MODEL
    )


# ─── Root (public) ────────────────────────────────────────────────────────────

@app.get("/", tags=["Root"])
async def root():
    return {
        "message": "Welcome to NL2Query Chatbot API",
        "docs":    "/docs",
        "health":  "/health"
    }


# ─── History — GET all ────────────────────────────────────────────────────────

@app.get("/history", tags=["History"])
async def history(
    limit: int = 50,
    api_key: str = Depends(verify_api_key)
):
    records = get_all_history(limit=limit)
    return [
        {
            "id":               r.id,
            "question":         r.question,
            "db_type":          r.db_type,
            "generated_query":  r.generated_query,
            "row_count":        r.row_count,
            "execution_status": r.execution_status,
            "error_message":    r.error_message,
            "created_at":       r.created_at.isoformat()
        }
        for r in records
    ]


# ─── History — stats ──────────────────────────────────────────────────────────

@app.get("/history/stats", tags=["History"])
async def history_stats(
    api_key: str = Depends(verify_api_key)
):
    return get_history_stats()


# ─── History — search ─────────────────────────────────────────────────────────

@app.get("/history/search", tags=["History"])
async def search(
    keyword: str,
    limit: int = 50,
    api_key: str = Depends(verify_api_key)
):
    records = search_history(keyword=keyword, limit=limit)
    return [
        {
            "id":               r.id,
            "question":         r.question,
            "db_type":          r.db_type,
            "generated_query":  r.generated_query,
            "execution_status": r.execution_status,
            "created_at":       r.created_at.isoformat()
        }
        for r in records
    ]


# ─── History — by db type ─────────────────────────────────────────────────────

@app.get("/history/{db_type}", tags=["History"])
async def history_by_db(
    db_type: str,
    limit: int = 50,
    api_key: str = Depends(verify_api_key)
):
    records = get_history_by_db(db_type=db_type, limit=limit)
    return [
        {
            "id":               r.id,
            "question":         r.question,
            "db_type":          r.db_type,
            "generated_query":  r.generated_query,
            "execution_status": r.execution_status,
            "created_at":       r.created_at.isoformat()
        }
        for r in records
    ]


# ─── History — delete all ─────────────────────────────────────────────────────

@app.delete("/history", tags=["History"])
async def clear_history(
    api_key: str = Depends(verify_api_key)
):
    count = delete_all_history()
    return {"message": f"Deleted {count} records"}