# engines/llm_engine.py
import json
from groq import Groq
from config import settings
import re  
client = Groq(api_key=settings.GROQ_API_KEY)


# ─── System Prompts per DB ────────────────────────────────────────────────────

SYSTEM_PROMPTS = {
    "postgresql": """
You are an expert PostgreSQL query generator.
Your job is to convert natural language questions into valid PostgreSQL queries.

Rules:
- Always return ONLY the raw SQL query, no explanation, no markdown, no backticks
- Use standard PostgreSQL syntax (ILIKE, INTERVAL, NOW(), RETURNING, etc.)
- Always use lowercase table and column names
- Add LIMIT 100 to SELECT queries unless the user specifies otherwise
- Never use DROP, TRUNCATE, or ALTER unless explicitly asked
- If schema context is provided, use ONLY those tables and columns
""",

    "mysql": """
You are an expert MySQL query generator.
Your job is to convert natural language questions into valid MySQL queries.

Rules:
- Always return ONLY the raw SQL query, no explanation, no markdown, no backticks
- Use standard MySQL syntax (LIKE, DATE_SUB, NOW(), LIMIT, etc.)
- Always use backticks for table/column names if they conflict with reserved words
- Add LIMIT 100 to SELECT queries unless the user specifies otherwise
- Never use DROP, TRUNCATE, or ALTER unless explicitly asked
- If schema context is provided, use ONLY those tables and columns
""",

    "oracle": """
You are an expert Oracle SQL query generator.
Your job is to convert natural language questions into valid Oracle SQL queries.

Rules:
- Always return ONLY the raw SQL query, no explanation, no markdown, no backticks
- Use Oracle syntax (ROWNUM, SYSDATE, NVL, TO_DATE, etc.)
- Use FETCH FIRST N ROWS ONLY instead of LIMIT
- Always use uppercase for Oracle keywords and functions
- Never use DROP, TRUNCATE, or ALTER unless explicitly asked
- If schema context is provided, use ONLY those tables and columns
""",

    "mongodb": """
You are an expert MongoDB query generator.
Your job is to convert natural language questions into a valid MongoDB query as a JSON object.

Rules:
- Always return ONLY a valid JSON object, no explanation, no markdown, no backticks
- The JSON must follow this exact structure:
{
    "collection": "<collection_name>",
    "operation": "<find|insert|update|delete|aggregate>",
    "filter": {},
    "projection": {},
    "document": {},
    "update": {},
    "pipeline": []
}
- Use only fields relevant to the operation
- For find operations, use filter and optional projection
- For aggregate operations, use pipeline array
- If schema context is provided, use ONLY those collections and fields
"""
}


# ─── Query Generator ──────────────────────────────────────────────────────────

def generate_query(
    question: str,
    db_type: str,
    schema_context: str = None
) -> str:
    """
    Send user question to Groq and get back a database query.

    Args:
        question:       Natural language question from user
        db_type:        One of postgresql | mysql | mongodb | oracle
        schema_context: Optional table/collection schema string

    Returns:
        Generated query string (SQL or JSON for MongoDB)
    """

    # Build user message
    user_message = f"Question: {question}"
    if schema_context:
        user_message += f"\n\nDatabase Schema:\n{schema_context}"

    # Pick the right system prompt
    system_prompt = SYSTEM_PROMPTS.get(db_type.lower())
    if not system_prompt:
        raise ValueError(f"Unsupported db_type: {db_type}")

    try:
        response = client.chat.completions.create(
            model=settings.GROQ_MODEL,
            messages=[
                {"role": "system", "content": system_prompt.strip()},
                {"role": "user",   "content": user_message.strip()}
            ],
            temperature=0.1,      # Low temp = consistent, accurate queries
            max_tokens=1024,
        )

        raw_output = response.choices[0].message.content.strip()

        # Clean up any accidental markdown code blocks
        raw_output = _clean_output(raw_output)

        # Validate MongoDB output is valid JSON
        if db_type.lower() == "mongodb":
            raw_output = _validate_mongo_json(raw_output)

        return raw_output

    except Exception as e:
        raise RuntimeError(f"Groq API error: {str(e)}")


# ─── Helper: Clean LLM output ─────────────────────────────────────────────────
def _clean_output(text: str) -> str:
    """Remove markdown code fences and sanitize control characters."""
    lines = text.splitlines()
    cleaned = []
    for line in lines:
        stripped = line.strip()
        if stripped.startswith("```"):
            continue
        cleaned.append(line)
    result = "\n".join(cleaned).strip()

    # ✅ NEW: Remove invalid JSON control characters
    import re
    result = re.sub(r'[\x00-\x08\x0B\x0C\x0E-\x1F\x7F]', '', result)
    return result

def _clean_output(text: str) -> str:
    """Remove markdown code fences and clean LLM output."""
    lines   = text.splitlines()
    cleaned = []
    for line in lines:
        stripped = line.strip()
        if stripped.startswith("```"):
            continue
        cleaned.append(line)
    result = "\n".join(cleaned).strip()

    # Remove common LLM preambles
    preambles = [
        "here is the json:",
        "here's the json:",
        "here is the schema:",
        "here's the schema:",
        "json response:",
        "response:"
    ]
    lower = result.lower()
    for p in preambles:
        if lower.startswith(p):
            result = result[len(p):].strip()
            break

    return result


# ─── Helper: Validate MongoDB JSON ────────────────────────────────────────────

def _validate_mongo_json(text: str) -> str:
    """Ensure MongoDB output is valid parseable JSON."""
    try:
        parsed = json.loads(text)
        # Ensure required fields exist
        if "collection" not in parsed:
            raise ValueError("MongoDB query missing 'collection' field")
        if "operation" not in parsed:
            raise ValueError("MongoDB query missing 'operation' field")
        return json.dumps(parsed, indent=2)
    except json.JSONDecodeError as e:
        raise ValueError(f"LLM returned invalid MongoDB JSON: {str(e)}\nRaw: {text}")

def _fix_json_string(text: str) -> str:
    """
    Fix common JSON issues from LLM output:
    - Unescaped control characters inside strings
    - Raw newlines inside string values
    - Tab characters inside strings
    """
    import re

    result  = []
    in_str  = False
    escaped = False

    for char in text:
        if escaped:
            result.append(char)
            escaped = False
            continue

        if char == "\\" and in_str:
            result.append(char)
            escaped = True
            continue

        if char == '"' and not escaped:
            in_str = not in_str
            result.append(char)
            continue

        if in_str:
            # Replace raw control characters with escaped versions
            if char == "\n":
                result.append("\\n")
            elif char == "\r":
                result.append("\\r")
            elif char == "\t":
                result.append("\\t")
            elif ord(char) < 32:
                # Other control characters
                result.append(f"\\u{ord(char):04x}")
            else:
                result.append(char)
        else:
            result.append(char)

    return "".join(result)


def _aggressive_json_fix(text: str) -> str:
    """
    Last resort JSON fixer — extracts JSON between first { and last }
    and applies all known fixes.
    """
    import re

    # Extract content between first { and last }
    start = text.find("{")
    end   = text.rfind("}")
    if start != -1 and end != -1:
        text = text[start:end + 1]

    # Remove all control characters outside strings
    text = re.sub(r'[\x00-\x08\x0b\x0c\x0e-\x1f\x7f]', '', text)

    # Apply string fixer
    text = _fix_json_string(text)

    return text

# ─── Quick test function ──────────────────────────────────────────────────────

def test_llm_engine():
    """Run a quick smoke test for all 4 DB types."""
    tests = [
        {
            "question": "Get all users who signed up in the last 7 days",
            "db_type": "postgresql",
            "schema_context": "users(id, name, email, created_at)"
        },
        {
            "question": "Find top 5 products by price",
            "db_type": "mysql",
            "schema_context": "products(id, name, price, stock)"
        },
        {
            "question": "Get all orders above 1000 rupees",
            "db_type": "mongodb",
            "schema_context": "orders collection: {_id, amount, customer_name, status}"
        },
        {
            "question": "List all employees in the HR department",
            "db_type": "oracle",
            "schema_context": "employees(emp_id, name, department, salary)"
        }
    ]

    for test in tests:
        print(f"\n{'='*50}")
        print(f"DB      : {test['db_type'].upper()}")
        print(f"Question: {test['question']}")
        print(f"Schema  : {test['schema_context']}")
        print(f"{'─'*50}")
        try:
            query = generate_query(
                question=test["question"],
                db_type=test["db_type"],
                schema_context=test["schema_context"]
            )
            print(f"Query   :\n{query}")
        except Exception as e:
            print(f"ERROR   : {e}")



CONVERSION_PROMPT = """
You are an expert database query converter.
Your job is to convert a query from one database system to another.

Rules:
- Return ONLY a JSON object with exactly these fields:
  {{
    "converted_query": "<the converted query>",
    "notes": "<any important conversion notes or syntax differences, or null>"
  }}
- converted_query must be the full converted query, clean with no markdown or backticks
- notes should mention key syntax differences (e.g. INTERVAL, LIMIT, data types)
- If converting TO MongoDB, converted_query must be a valid JSON object with collection, operation, filter etc.
- If converting FROM MongoDB, the source will be a JSON object — convert it to SQL
- Preserve all logic, filters, joins, aggregations exactly
- No explanation outside the JSON object
"""


def convert_query(
    query: str,
    source_db: str,
    target_db: str
) -> dict:
    """
    Convert a query from one database type to another.

    Args:
        query:     The original query string
        source_db: Source database type
        target_db: Target database type

    Returns:
        dict with converted_query and notes
    """
    if source_db.lower() == target_db.lower():
        return {
            "converted_query": query,
            "notes": "Source and target databases are the same — no conversion needed."
        }

    user_message = f"""
Convert this {source_db.upper()} query to {target_db.upper()}:

{query}

Return ONLY the JSON object as specified.
"""

    try:
        response = client.chat.completions.create(
            model=settings.GROQ_MODEL,
            messages=[
                {"role": "system", "content": CONVERSION_PROMPT.strip()},
                {"role": "user",   "content": user_message.strip()}
            ],
            temperature=0.1,
            max_tokens=2048,
        )

        raw = response.choices[0].message.content.strip()
        raw = _clean_output(raw)

        # Parse JSON response
        try:
    # ✅ Use raw_unicode_escape to handle edge cases
            result = json.loads(raw)
        except json.JSONDecodeError as e:
    # ✅ Try aggressive sanitization before giving up
            try:
                sanitized = re.sub(r'[\x00-\x1F\x7F]', 
                           lambda m: '\\n' if m.group() == '\n' else '', raw)
                result = json.loads(sanitized)
            except json.JSONDecodeError:
                raise ValueError(f"LLM returned invalid JSON: {str(e)}\nRaw: {raw[:200]}")
        return {
                "converted_query": raw,
                "notes": "Note: Could not parse structured response from LLM."
            }

    except Exception as e:
        raise RuntimeError(f"Groq conversion error: {str(e)}")
    

SCHEMA_PROMPT = """
You are an expert database architect with 15+ years of experience.
Your job is to analyze requirements and generate a complete, production-ready database schema.

Return ONLY a valid JSON object with exactly this structure:
{{
  "tables": [
    {{
      "table_name": "users",
      "description": "Stores user account information",
      "columns": [
        {{
          "name": "id",
          "type": "UUID",
          "constraints": "PRIMARY KEY DEFAULT gen_random_uuid()",
          "description": "Unique identifier"
        }}
      ],
      "indexes": [
        "CREATE INDEX idx_users_email ON users(email);"
      ]
    }}
  ],
  "relationships": [
    "users.id → orders.user_id (One-to-Many)",
    "orders.id → order_items.order_id (One-to-Many)"
  ],
  "create_scripts": "-- Full CREATE TABLE scripts here as a single string",
  "sample_data": "-- Sample INSERT statements here or null if not requested",
  "design_notes": "Key design decisions and recommendations"
}}

Rules:
- Always use appropriate primary keys (UUID for PostgreSQL, BIGINT AUTO_INCREMENT for MySQL)
- Always add created_at and updated_at timestamps
- Always add proper foreign keys with ON DELETE behavior
- Always suggest indexes for frequently queried columns
- Normalize to at least 3NF unless denormalization is justified
- For MongoDB: use collections instead of tables, nested documents where appropriate
- For Oracle: use Oracle-specific syntax (NUMBER, VARCHAR2, SYSDATE etc.)
- create_scripts must be complete, runnable SQL (or MongoDB commands)
- Return ONLY the JSON object, no markdown, no explanation outside JSON
"""

def suggest_schema(
    requirement: str,
    db_type: str,
    include_sample_data: bool = False
) -> dict:
    """
    Generate a full database schema based on requirements.
    """
    sample_instruction = (
        "Include realistic sample INSERT statements for 2-3 rows per table."
        if include_sample_data
        else "Set sample_data to null."
    )

    user_message = f"""
Analyze this requirement and generate a complete {db_type.upper()} database schema:

REQUIREMENT:
{requirement}

DATABASE: {db_type.upper()}
SAMPLE DATA: {sample_instruction}

IMPORTANT:
- Return ONLY the JSON object
- Do NOT include any newlines or line breaks inside JSON string values
- All SQL scripts must be on a single line or use \\n escape sequences
- No raw newlines inside string values

Return ONLY the JSON object as specified in your instructions.
"""

    try:
        response = client.chat.completions.create(
            model=settings.GROQ_MODEL,
            messages=[
                {"role": "system", "content": SCHEMA_PROMPT.strip()},
                {"role": "user",   "content": user_message.strip()}
            ],
            temperature=0.2,
            max_tokens=4096,
        )

        raw = response.choices[0].message.content.strip()
        raw = _clean_output(raw)
        raw = _fix_json_string(raw)

        # Parse JSON response
        try:
            result = json.loads(raw)

            # Validate required fields
            for field in ["tables", "relationships", "create_scripts"]:
                if field not in result:
                    raise ValueError(f"Missing field: {field}")

            # Clean up create_scripts — convert \n back to real newlines
            if "create_scripts" in result:
                result["create_scripts"] = (
                    result["create_scripts"]
                    .replace("\\n", "\n")
                    .replace("\\t", "\t")
                )

            if result.get("sample_data"):
                result["sample_data"] = (
                    result["sample_data"]
                    .replace("\\n", "\n")
                    .replace("\\t", "\t")
                )

            return result

        except json.JSONDecodeError as e:
            # Last resort — try aggressive cleanup
            cleaned = _aggressive_json_fix(raw)
            try:
                result = json.loads(cleaned)
                return result
            except Exception:
                raise ValueError(
                    f"LLM returned invalid JSON: {str(e)}\n"
                    f"Raw: {raw[:300]}"
                )

    except Exception as e:
        raise RuntimeError(f"Groq schema suggestion error: {str(e)}")

if __name__ == "__main__":
    test_llm_engine()