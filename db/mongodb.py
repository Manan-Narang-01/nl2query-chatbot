# db/mongodb.py
import pymongo
from typing import Any
from config import settings


def get_mongo_db():
    """Create and return a MongoDB database instance."""
    try:
        client = pymongo.MongoClient(
            settings.MONGO_URI,
            serverSelectionTimeoutMS=5000
        )
        # Ping to verify connection
        client.admin.command("ping")
        db = client[settings.MONGO_DATABASE]
        return db
    except pymongo.errors.ServerSelectionTimeoutError as e:
        raise ConnectionError(f"MongoDB connection failed: {str(e)}")


def run_mongo_query(query: dict[str, Any]) -> dict[str, Any]:
    """
    Execute a MongoDB query.
    Expected query format:
    {
        "collection": "users",
        "operation": "find",         # find | insert | update | delete | aggregate
        "filter": {},                # for find/update/delete
        "projection": {},            # optional for find
        "document": {},              # for insert
        "update": {},                # for update
        "pipeline": []               # for aggregate
    }
    """
    try:
        db = get_mongo_db()

        collection_name = query.get("collection")
        operation       = query.get("operation", "find").lower()
        filter_query    = query.get("filter", {})
        projection      = query.get("projection", None)
        document        = query.get("document", {})
        update_data     = query.get("update", {})
        pipeline        = query.get("pipeline", [])

        if not collection_name:
            raise ValueError("MongoDB query must include a 'collection' field.")

        collection = db[collection_name]

        # ── Operations ────────────────────────────────────────────────────────
        if operation == "find":
            cursor = collection.find(filter_query, projection)
            result = [{k: str(v) if k == "_id" else v
                       for k, v in doc.items()}
                      for doc in cursor]

        elif operation == "insert":
            res = collection.insert_one(document)
            result = [{"inserted_id": str(res.inserted_id)}]

        elif operation == "update":
            res = collection.update_many(filter_query, update_data)
            result = [{"matched": res.matched_count,
                       "modified": res.modified_count}]

        elif operation == "delete":
            res = collection.delete_many(filter_query)
            result = [{"deleted_count": res.deleted_count}]

        elif operation == "aggregate":
            cursor = collection.aggregate(pipeline)
            result = [{k: str(v) if k == "_id" else v
                       for k, v in doc.items()}
                      for doc in cursor]
        else:
            raise ValueError(f"Unsupported operation: {operation}")

        return {
            "status": "success",
            "data": result,
            "row_count": len(result)
        }

    except Exception as e:
        return {
            "status": "error",
            "data": [],
            "row_count": 0,
            "error": str(e)
        }