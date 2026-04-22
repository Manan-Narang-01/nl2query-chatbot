# db/history.py
from sqlalchemy import (
    create_engine, Column, Integer, String,
    Text, DateTime, JSON
)
from sqlalchemy.orm import declarative_base, sessionmaker
from datetime import datetime
import os

# ─── Database Setup ───────────────────────────────────────────────────────────

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DB_PATH  = os.path.join(BASE_DIR, "query_history.db")

engine       = create_engine(f"sqlite:///{DB_PATH}", echo=False)
SessionLocal = sessionmaker(bind=engine, autocommit=False, autoflush=False)
Base         = declarative_base()


# ─── Model ────────────────────────────────────────────────────────────────────

class QueryHistory(Base):
    __tablename__ = "query_history"

    id              = Column(Integer, primary_key=True, index=True)
    question        = Column(Text,    nullable=False)
    db_type         = Column(String,  nullable=False)
    generated_query = Column(Text,    nullable=False)
    schema_context  = Column(Text,    nullable=True)
    query_result    = Column(JSON,    nullable=True)
    row_count       = Column(Integer, default=0)
    execution_status= Column(String,  default="preview")
    error_message   = Column(Text,    nullable=True)
    created_at      = Column(DateTime, default=datetime.utcnow)


# ─── Create Tables ────────────────────────────────────────────────────────────

def init_db():
    """Create all tables if they don't exist."""
    Base.metadata.create_all(bind=engine)


# ─── CRUD Operations ──────────────────────────────────────────────────────────

def save_query(
    question: str,
    db_type: str,
    generated_query: str,
    schema_context: str  = None,
    query_result: list   = None,
    row_count: int       = 0,
    execution_status: str = "preview",
    error_message: str   = None
) -> QueryHistory:
    """Save a query record to SQLite."""
    db = SessionLocal()
    try:
        record = QueryHistory(
            question         = question,
            db_type          = db_type,
            generated_query  = generated_query,
            schema_context   = schema_context,
            query_result     = query_result,
            row_count        = row_count,
            execution_status = execution_status,
            error_message    = error_message
        )
        db.add(record)
        db.commit()
        db.refresh(record)
        return record
    except Exception as e:
        db.rollback()
        raise RuntimeError(f"Failed to save query history: {str(e)}")
    finally:
        db.close()


def get_all_history(limit: int = 50) -> list:
    """Fetch most recent query history records."""
    db = SessionLocal()
    try:
        records = (
            db.query(QueryHistory)
            .order_by(QueryHistory.created_at.desc())
            .limit(limit)
            .all()
        )
        return records
    finally:
        db.close()


def get_history_by_db(db_type: str, limit: int = 50) -> list:
    """Fetch history filtered by database type."""
    db = SessionLocal()
    try:
        records = (
            db.query(QueryHistory)
            .filter(QueryHistory.db_type == db_type)
            .order_by(QueryHistory.created_at.desc())
            .limit(limit)
            .all()
        )
        return records
    finally:
        db.close()


def get_history_stats() -> dict:
    """Get summary stats for the history dashboard."""
    db = SessionLocal()
    try:
        total   = db.query(QueryHistory).count()
        success = db.query(QueryHistory).filter(
            QueryHistory.execution_status == "success"
        ).count()
        preview = db.query(QueryHistory).filter(
            QueryHistory.execution_status == "preview"
        ).count()
        error   = db.query(QueryHistory).filter(
            QueryHistory.execution_status == "error"
        ).count()

        # Count per DB type
        from sqlalchemy import func
        db_counts = (
            db.query(
                QueryHistory.db_type,
                func.count(QueryHistory.id).label("count")
            )
            .group_by(QueryHistory.db_type)
            .all()
        )

        return {
            "total":    total,
            "success":  success,
            "preview":  preview,
            "error":    error,
            "by_db":    {row.db_type: row.count for row in db_counts}
        }
    finally:
        db.close()


def delete_all_history() -> int:
    """Delete all history records. Returns count deleted."""
    db = SessionLocal()
    try:
        count = db.query(QueryHistory).count()
        db.query(QueryHistory).delete()
        db.commit()
        return count
    except Exception as e:
        db.rollback()
        raise RuntimeError(f"Failed to delete history: {str(e)}")
    finally:
        db.close()


def search_history(keyword: str, limit: int = 50) -> list:
    """Search history by keyword in question or query."""
    db = SessionLocal()
    try:
        records = (
            db.query(QueryHistory)
            .filter(
                QueryHistory.question.ilike(f"%{keyword}%") |
                QueryHistory.generated_query.ilike(f"%{keyword}%")
            )
            .order_by(QueryHistory.created_at.desc())
            .limit(limit)
            .all()
        )
        return records
    finally:
        db.close()