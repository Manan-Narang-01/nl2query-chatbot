
from models.schemas import ChatRequest, DBType

req = ChatRequest(
    question="Show all orders above 500 rupees",
    db_type=DBType.postgresql,
    schema_context="orders(id, amount, customer_id, created_at)"
)

print(req.model_dump())