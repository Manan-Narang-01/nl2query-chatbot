# models/schemas.py
from pydantic import BaseModel, Field
from typing import Optional, Any
from enum import Enum


# ─── Database Type Enum ───────────────────────────────────────────────────────

class DBType(str, Enum):
    postgresql = "postgresql"
    mysql      = "mysql"
    mongodb    = "mongodb"
    oracle     = "oracle"


# ─── Chat Request ─────────────────────────────────────────────────────────────

class ChatRequest(BaseModel):
    question: str = Field(
        ...,
        min_length=3,
        max_length=1000,
        description="Natural language question from the user"
    )
    db_type: DBType = Field(
        ...,
        description="Target database type"
    )
    schema_context: Optional[str] = Field(
        default=None,
        description="Optional: paste your table schema for accurate queries"
    )

    class Config:
        json_schema_extra = {
            "example": {
                "question": "Get all users who registered in the last 30 days",
                "db_type": "postgresql",
                "schema_context": "users(id, name, email, created_at)"
            }
        }


# ─── Chat Response ────────────────────────────────────────────────────────────

class ChatResponse(BaseModel):
    question: str           = Field(..., description="Original user question")
    db_type: str            = Field(..., description="Target database used")
    generated_query: str    = Field(..., description="Generated query string")
    query_result: Any       = Field(..., description="Result rows from the DB")
    row_count: int          = Field(..., description="Number of rows returned")
    execution_status: str   = Field(..., description="success or error")
    error_message: Optional[str] = Field(
        default=None,
        description="Error details if execution failed"
    )

    class Config:
        json_schema_extra = {
            "example": {
                "question": "Get all users who registered in the last 30 days",
                "db_type": "postgresql",
                "generated_query": "SELECT * FROM users WHERE created_at >= NOW() - INTERVAL '30 days';",
                "query_result": [{"id": 1, "name": "Alice"}],
                "row_count": 1,
                "execution_status": "success",
                "error_message": None
            }
        }


# ─── Query Preview (no execution) ────────────────────────────────────────────

class QueryPreviewRequest(BaseModel):
    question: str = Field(
        ...,
        min_length=3,
        max_length=1000,
        description="Natural language question"
    )
    db_type: DBType = Field(
        ...,
        description="Target database type"
    )
    schema_context: Optional[str] = Field(
        default=None,
        description="Optional schema context"
    )

    class Config:
        json_schema_extra = {
            "example": {
                "question": "Find top 5 products by sales",
                "db_type": "mysql",
                "schema_context": "products(id, name, sales_count)"
            }
        }


class QueryPreviewResponse(BaseModel):
    question: str        = Field(..., description="Original question")
    db_type: str         = Field(..., description="Target database")
    generated_query: str = Field(..., description="Generated query — not yet executed")

    class Config:
        json_schema_extra = {
            "example": {
                "question": "Find top 5 products by sales",
                "db_type": "mysql",
                "generated_query": "SELECT * FROM products ORDER BY sales_count DESC LIMIT 5;"
            }
        }


# ─── Health Check ─────────────────────────────────────────────────────────────

class HealthResponse(BaseModel):
    status: str  = Field(..., description="API health status")
    version: str = Field(..., description="API version")
    groq_model: str = Field(..., description="Active Groq model in use")

    class Config:
        json_schema_extra = {
            "example": {
                "status": "ok",
                "version": "1.0.0",
                "groq_model": "llama3-70b-8192"
            }
        }


# ─── Error Response ───────────────────────────────────────────────────────────

class ErrorResponse(BaseModel):
    status: str  = Field(default="error")
    message: str = Field(..., description="Error message")
    detail: Optional[str] = Field(default=None, description="Extra detail")

    class Config:
        json_schema_extra = {
            "example": {
                "status": "error",
                "message": "Failed to connect to database",
                "detail": "Connection refused at localhost:5432"
            }
        }
        
        
# Add to models/schemas.py

class ConvertQueryRequest(BaseModel):
    query: str = Field(
        ...,
        min_length=3,
        max_length=5000,
        description="The query to convert"
    )
    source_db: DBType = Field(
        ...,
        description="Source database type"
    )
    target_db: DBType = Field(
        ...,
        description="Target database type"
    )

    class Config:
        json_schema_extra = {
            "example": {
                "query": "SELECT * FROM users WHERE created_at >= NOW() - INTERVAL '7 days'",
                "source_db": "postgresql",
                "target_db": "mysql"
            }
        }


class ConvertQueryResponse(BaseModel):
    original_query:  str = Field(..., description="Original query")
    converted_query: str = Field(..., description="Converted query")
    source_db:       str = Field(..., description="Source database")
    target_db:       str = Field(..., description="Target database")
    notes:           Optional[str] = Field(
        default=None,
        description="Conversion notes or warnings"
    )

    class Config:
        json_schema_extra = {
            "example": {
                "original_query":  "SELECT * FROM users WHERE created_at >= NOW() - INTERVAL '7 days'",
                "converted_query": "SELECT * FROM users WHERE created_at >= DATE_SUB(NOW(), INTERVAL 7 DAY)",
                "source_db":       "postgresql",
                "target_db":       "mysql",
                "notes":           "INTERVAL syntax differs between PostgreSQL and MySQL"
            }
        }
        

class SchemaSuggestionRequest(BaseModel):
    requirement: str = Field(
        ...,
        min_length=10,
        max_length=3000,
        description="Plain English description of what you want to build"
    )
    db_type: DBType = Field(
        ...,
        description="Target database type"
    )
    include_sample_data: bool = Field(
        default=False,
        description="Whether to include sample INSERT statements"
    )

    class Config:
        json_schema_extra = {
            "example": {
                "requirement": "I want to build an e-commerce platform with users, products, orders and payments",
                "db_type": "postgresql",
                "include_sample_data": True
            }
        }


class TableColumn(BaseModel):
    name:        str
    type:        str
    constraints: Optional[str] = None
    description: Optional[str] = None


class TableSchema(BaseModel):
    table_name:  str
    description: str
    columns:     list[TableColumn]
    indexes:     Optional[list[str]] = None


class SchemaSuggestionResponse(BaseModel):
    requirement:     str
    db_type:         str
    tables:          list[TableSchema]
    relationships:   list[str]
    create_scripts:  str
    sample_data:     Optional[str] = None
    design_notes:    Optional[str] = None

    class Config:
        json_schema_extra = {
            "example": {
                "requirement": "E-commerce platform",
                "db_type": "postgresql",
                "tables": [],
                "relationships": [],
                "create_scripts": "CREATE TABLE users (...);",
                "sample_data": "INSERT INTO users VALUES (...);",
                "design_notes": "Used UUID for primary keys for scalability"
            }
        }