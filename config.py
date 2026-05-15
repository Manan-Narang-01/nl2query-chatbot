# config.py
import os
from dotenv import load_dotenv

load_dotenv()


class Settings:
    # ── Groq ──────────────────────────────────────────────────────────────────
    GROQ_API_KEY: str = os.getenv("GROQ_API_KEY", "")
    GROQ_MODEL:   str = "llama-3.3-70b-versatile"

    # ── API Key Auth ──────────────────────────────────────────────────────────
    _raw_keys: str = os.getenv("VALID_API_KEYS", "")
    VALID_API_KEYS: set = set(
        k.strip() for k in _raw_keys.split(",") if k.strip()
    )

    # ── PostgreSQL ────────────────────────────────────────────────────────────
    PG_HOST:     str = os.getenv("PG_HOST",     "localhost")
    PG_PORT:     int = int(os.getenv("PG_PORT", 5432))
    PG_USER:     str = os.getenv("PG_USER",     "postgres")
    PG_PASSWORD: str = os.getenv("PG_PASSWORD", "")
    PG_DATABASE: str = os.getenv("PG_DATABASE", "mydb")

    # ── MySQL ─────────────────────────────────────────────────────────────────
    MYSQL_HOST:     str = os.getenv("MYSQL_HOST",     "localhost")
    MYSQL_PORT:     int = int(os.getenv("MYSQL_PORT", 3306))
    MYSQL_USER:     str = os.getenv("MYSQL_USER",     "root")
    MYSQL_PASSWORD: str = os.getenv("MYSQL_PASSWORD", "")
    MYSQL_DATABASE: str = os.getenv("MYSQL_DATABASE", "mydb")

    # ── MongoDB ───────────────────────────────────────────────────────────────
    MONGO_URI:      str = os.getenv("MONGO_URI",      "mongodb://localhost:27017")
    MONGO_DATABASE: str = os.getenv("MONGO_DATABASE", "mydb")

    # ── Oracle ────────────────────────────────────────────────────────────────
    ORACLE_DSN:      str = os.getenv("ORACLE_DSN",      "localhost:1521/XEPDB1")
    ORACLE_USER:     str = os.getenv("ORACLE_USER",     "system")
    ORACLE_PASSWORD: str = os.getenv("ORACLE_PASSWORD", "")

    # ── CORS ──────────────────────────────────────────────────────────────────
    _raw_origins: str = os.getenv(
        "ALLOWED_ORIGINS",
        "http://localhost:8501,http://localhost:8502"
    )
    ALLOWED_ORIGINS: list = [o.strip() for o in _raw_origins.split(",") if o.strip()]


settings = Settings()