# db/__init__.py
from .postgres import run_postgres_query
from .mysql    import run_mysql_query
from .mongodb  import run_mongo_query
from .oracle   import run_oracle_query

__all__ = [
    "run_postgres_query",
    "run_mysql_query",
    "run_mongo_query",
    "run_oracle_query"
]