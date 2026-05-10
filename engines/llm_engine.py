# engines/llm_engine.py
import json
import re
from groq import Groq
from config import settings

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
    """
    user_message = f"Question: {question}"
    if schema_context:
        user_message += f"\n\nDatabase Schema:\n{schema_context}"

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
            temperature=0.1,
            max_tokens=1024,
        )

        raw_output = response.choices[0].message.content.strip()
        raw_output = _clean_output(raw_output)

        if db_type.lower() == "mongodb":
            raw_output = _validate_mongo_json(raw_output)

        return raw_output

    except Exception as e:
        raise RuntimeError(f"Groq API error: {str(e)}")


# ─── Helper: Clean LLM output ─────────────────────────────────────────────────

def _clean_output(text: str) -> str:
    """Remove markdown code fences, preambles and clean LLM output."""
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

    # Remove invalid control characters
    result = re.sub(r'[\x00-\x08\x0B\x0C\x0E-\x1F\x7F]', '', result)

    return result


# ─── Helper: Validate MongoDB JSON ────────────────────────────────────────────

def _validate_mongo_json(text: str) -> str:
    """Ensure MongoDB output is valid parseable JSON."""
    try:
        parsed = json.loads(text)
        if "collection" not in parsed:
            raise ValueError("MongoDB query missing 'collection' field")
        if "operation" not in parsed:
            raise ValueError("MongoDB query missing 'operation' field")
        return json.dumps(parsed, indent=2)
    except json.JSONDecodeError as e:
        raise ValueError(f"LLM returned invalid MongoDB JSON: {str(e)}\nRaw: {text}")


# ─── Helper: Fix JSON strings ─────────────────────────────────────────────────

def _fix_json_string(text: str) -> str:
    """
    Fix common JSON issues from LLM output:
    - Unescaped control characters inside strings
    - Raw newlines inside string values
    """
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
            if char == "\n":
                result.append("\\n")
            elif char == "\r":
                result.append("\\r")
            elif char == "\t":
                result.append("\\t")
            elif ord(char) < 32:
                result.append(f"\\u{ord(char):04x}")
            else:
                result.append(char)
        else:
            result.append(char)

    return "".join(result)


# ─── Helper: Aggressive JSON fix ─────────────────────────────────────────────

def _aggressive_json_fix(text: str) -> str:
    """
    Last resort JSON fixer — extracts JSON between first { and last }
    and applies all known fixes.
    """
    start = text.find("{")
    end   = text.rfind("}")
    if start != -1 and end != -1:
        text = text[start:end + 1]

    text = re.sub(r'[\x00-\x08\x0b\x0c\x0e-\x1f\x7f]', '', text)
    text = _fix_json_string(text)

    return text


# ─── Test function ────────────────────────────────────────────────────────────

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


# ─── Conversion Prompt ────────────────────────────────────────────────────────

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

        # ── Parse JSON response ───────────────────────────────────────────────
        try:
            result = json.loads(raw)
            if "converted_query" not in result:
                raise ValueError("Missing converted_query in response")
            return {
                "converted_query": result.get("converted_query", ""),
                "notes":           result.get("notes", None)
            }
        except json.JSONDecodeError:
            # Try aggressive sanitization
            try:
                sanitized = re.sub(
                    r'[\x00-\x1F\x7F]',
                    lambda m: '\\n' if m.group() == '\n' else '',
                    raw
                )
                result = json.loads(sanitized)
                return {
                    "converted_query": result.get("converted_query", raw),
                    "notes":           result.get("notes", None)
                }
            except json.JSONDecodeError:
                # Return raw as converted query if all parsing fails
                return {
                    "converted_query": raw,
                    "notes": "Note: Could not parse structured response from LLM."
                }

    except Exception as e:
        raise RuntimeError(f"Groq conversion error: {str(e)}")


# ─── Schema Suggestion Prompt ─────────────────────────────────────────────────

SCHEMA_PROMPT = """
You are an expert database architect.
Generate a complete database schema based on the requirements.

CRITICAL RULES:
- Return ONLY a valid JSON object
- NO markdown, NO backticks, NO explanation outside JSON
- NO newlines or tabs inside string values
- ALL SQL must use \\n for line breaks inside strings
- Keep string values SHORT and CLEAN

Return this EXACT structure:
{
  "tables": [
    {
      "table_name": "users",
      "description": "Stores user information",
      "columns": [
        {
          "name": "id",
          "type": "UUID",
          "constraints": "PRIMARY KEY DEFAULT gen_random_uuid()",
          "description": "Unique identifier"
        }
      ],
      "indexes": ["CREATE INDEX idx_users_email ON users(email);"]
    }
  ],
  "relationships": [
    "users.id -> orders.user_id (One-to-Many)"
  ],
  "create_scripts": "CREATE TABLE users (id UUID PRIMARY KEY);\\nCREATE TABLE orders (id UUID PRIMARY KEY);",
  "sample_data": null,
  "design_notes": "Brief design notes here"
}

IMPORTANT FOR create_scripts:
- Put ALL CREATE TABLE statements in ONE single string
- Use \\n between statements NOT actual newlines
- Keep it concise
"""


def suggest_schema(
    requirement: str,
    db_type: str,
    include_sample_data: bool = False
) -> dict:
    """
    Generate a full database schema based on requirements.
    Robust version with multiple fallback strategies.
    """
    sample_instruction = (
        "Include 2 sample INSERT statements per table in sample_data field."
        if include_sample_data
        else "Set sample_data to null."
    )

    user_message = f"""
Generate a {db_type.upper()} database schema for:

{requirement}

SAMPLE DATA: {sample_instruction}

STRICT RULES:
1. Return ONLY the JSON object - nothing else
2. No actual newlines inside string values - use \\n instead
3. Keep all string values concise
4. create_scripts must be ONE string with \\n between statements
"""

    last_error = None
    for attempt in range(3):
        temperature = 0.1 + (attempt * 0.05)
        try:
            response = client.chat.completions.create(
                model=settings.GROQ_MODEL,
                messages=[
                    {"role": "system", "content": SCHEMA_PROMPT.strip()},
                    {"role": "user",   "content": user_message.strip()}
                ],
                temperature=temperature,
                max_tokens=4096,
            )

            raw = response.choices[0].message.content.strip()
            raw = _clean_output(raw)

            result = _parse_schema_json(raw)
            if result:
                result = _sanitize_schema_result(result)
                return result

        except Exception as e:
            last_error = str(e)
            continue

    raise RuntimeError(
        f"Failed to generate schema after 3 attempts. "
        f"Last error: {last_error}"
    )


# ─── Schema JSON Parser ───────────────────────────────────────────────────────

def _parse_schema_json(raw: str) -> dict | None:
    """
    Try multiple strategies to parse the JSON response.
    Returns dict if successful, None if all strategies fail.
    """

    # Strategy 1 — direct parse
    try:
        result = json.loads(raw)
        if "tables" in result:
            return result
    except Exception:
        pass

    # Strategy 2 — fix control characters then parse
    try:
        fixed  = _fix_json_string(raw)
        result = json.loads(fixed)
        if "tables" in result:
            return result
    except Exception:
        pass

    # Strategy 3 — extract JSON block then fix
    try:
        start = raw.find("{")
        end   = raw.rfind("}")
        if start != -1 and end != -1:
            extracted = raw[start:end + 1]
            fixed     = _fix_json_string(extracted)
            result    = json.loads(fixed)
            if "tables" in result:
                return result
    except Exception:
        pass

    # Strategy 4 — aggressive cleanup
    try:
        cleaned = _aggressive_json_fix(raw)
        result  = json.loads(cleaned)
        if "tables" in result:
            return result
    except Exception:
        pass

    # Strategy 5 — rebuild minimal valid JSON from partial response
    try:
        result = _rebuild_from_partial(raw)
        if result:
            return result
    except Exception:
        pass

    return None


# ─── Schema Result Sanitizer ──────────────────────────────────────────────────

def _sanitize_schema_result(result: dict) -> dict:
    """Clean up schema result to ensure all values are safe strings."""

    # Fix create_scripts
    if "create_scripts" in result:
        cs = result["create_scripts"]
        if isinstance(cs, list):
            cs = "\n".join(cs)
        if isinstance(cs, str):
            result["create_scripts"] = (
                cs.replace("\\n", "\n")
                  .replace("\\t", "\t")
                  .strip()
            )

    # Fix sample_data
    if result.get("sample_data"):
        sd = result["sample_data"]
        if isinstance(sd, list):
            sd = "\n".join(sd)
        if isinstance(sd, str):
            result["sample_data"] = (
                sd.replace("\\n", "\n")
                  .replace("\\t", "\t")
                  .strip()
            )

    # Fix tables
    for table in result.get("tables", []):
        if "indexes" in table and isinstance(table["indexes"], list):
            table["indexes"] = [
                str(idx).replace("\\n", "\n") for idx in table["indexes"]
            ]
        for col in table.get("columns", []):
            if col.get("constraints"):
                col["constraints"] = str(col["constraints"]).strip()
            if col.get("description"):
                col["description"] = str(col["description"]).strip()

    # Ensure relationships is a list of strings
    if "relationships" in result:
        result["relationships"] = [
            str(r) for r in result["relationships"]
        ]

    # Ensure design_notes is a string
    if result.get("design_notes") and not isinstance(result["design_notes"], str):
        result["design_notes"] = str(result["design_notes"])

    return result


# ─── Schema Partial Rebuilder ─────────────────────────────────────────────────

def _rebuild_from_partial(raw: str) -> dict | None:
    """
    Last resort — extract table names and build minimal valid schema.
    """
    table_names = re.findall(r'"table_name"\s*:\s*"([^"]+)"', raw)

    if not table_names:
        return None

    tables = []
    for name in table_names:
        tables.append({
            "table_name":  name,
            "description": f"Table for {name}",
            "columns": [
                {
                    "name":        "id",
                    "type":        "UUID",
                    "constraints": "PRIMARY KEY",
                    "description": "Primary key"
                },
                {
                    "name":        "created_at",
                    "type":        "TIMESTAMP",
                    "constraints": "DEFAULT NOW()",
                    "description": "Creation timestamp"
                }
            ],
            "indexes": []
        })

    cs_match = re.search(
        r'"create_scripts"\s*:\s*"((?:[^"\\]|\\.)*)"',
        raw
    )
    create_scripts = cs_match.group(1) if cs_match else (
        "\n".join([
            f"CREATE TABLE {t['table_name']} "
            f"(id UUID PRIMARY KEY, "
            f"created_at TIMESTAMP DEFAULT NOW());"
            for t in tables
        ])
    )

    return {
        "tables":         tables,
        "relationships":  [],
        "create_scripts": create_scripts.replace("\\n", "\n"),
        "sample_data":    None,
        "design_notes":   (
            "Note: Schema was partially recovered due to LLM response "
            "formatting issues. Please review and enhance as needed."
        )
    }


if __name__ == "__main__":
    test_llm_engine()