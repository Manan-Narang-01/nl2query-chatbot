# frontend/app.py
import os
import streamlit as st
import requests
from datetime import datetime

# ─── Load config (works both locally and on Streamlit Cloud) ──────────────────

try:
    # Streamlit Cloud — uses secrets.toml
    API_BASE_URL = st.secrets["API_BASE_URL"]
    API_KEY      = st.secrets["STREAMLIT_API_KEY"]
except Exception:
    # Local development — uses .env
    from dotenv import load_dotenv
    load_dotenv()
    API_BASE_URL = os.getenv("API_BASE_URL", "http://127.0.0.1:8000")
    API_KEY      = os.getenv("STREAMLIT_API_KEY", "nlq-key-dev999")

HEADERS = {"X-API-Key": API_KEY}

# ─── Page Config ──────────────────────────────────────────────────────────────

st.set_page_config(
    page_title="NL2Query Chatbot",
    page_icon="🗄️",
    layout="wide",
    initial_sidebar_state="expanded"
)

# ─── Constants ────────────────────────────────────────────────────────────────

DB_TYPES = ["postgresql", "mysql", "mongodb", "oracle"]

DB_ICONS = {
    "postgresql": "🐘",
    "mysql":      "🐬",
    "mongodb":    "🍃",
    "oracle":     "🔴"
}

EXAMPLE_QUESTIONS = {
    "postgresql": [
        "Get all users registered in the last 7 days",
        "Find top 5 customers by total orders",
        "Count users registered per month",
    ],
    "mysql": [
        "Find all products with stock less than 10",
        "Get the 5 most recent transactions",
        "Show all employees with salary above 50000",
    ],
    "mongodb": [
        "Find all active users",
        "Get orders with status pending",
        "Find products with price greater than 500",
    ],
    "oracle": [
        "List all employees in HR department",
        "Find top 5 employees by salary",
        "Show all invoices that are overdue",
    ]
}

# ─── Session State ────────────────────────────────────────────────────────────

if "chat_history" not in st.session_state:
    st.session_state.chat_history = []

if "selected_db" not in st.session_state:
    st.session_state.selected_db = "postgresql"

if "conversions" not in st.session_state:
    st.session_state.conversions = []

# ─── Sidebar ──────────────────────────────────────────────────────────────────

with st.sidebar:
    st.title("🗄️ NL2Query")
    st.markdown("Convert plain English to database queries using Groq AI")
    st.divider()

    # Database selector
    st.subheader("Select Database")
    selected_db = st.selectbox(
        label="Database type",
        options=DB_TYPES,
        format_func=lambda x: f"{DB_ICONS[x]}  {x.upper()}",
        key="db_selector",
        label_visibility="collapsed"
    )
    st.session_state.selected_db = selected_db

    st.divider()

    # Schema context
    st.subheader("Schema Context (optional)")
    schema_context = st.text_area(
        label="Schema",
        placeholder="e.g. users(id, name, email, created_at)",
        height=120,
        label_visibility="collapsed"
    )

    st.divider()

    # Mode
    st.subheader("Mode")
    mode = st.radio(
        label="Query mode",
        options=["Preview only", "Execute query"],
        label_visibility="collapsed"
    )

    st.divider()

    # Example questions
    st.subheader("Example questions")
    examples = EXAMPLE_QUESTIONS.get(selected_db, [])
    for example in examples:
        if st.button(
            label=example,
            use_container_width=True,
            key=f"ex_{example[:20]}"
        ):
            st.session_state["prefill_question"] = example

    st.divider()

    # Clear chat
    if st.button("🗑️ Clear chat history", use_container_width=True):
        st.session_state.chat_history = []
        st.rerun()

    # API status
    st.subheader("API status")
    try:
        res = requests.get(f"{API_BASE_URL}/health", timeout=3)
        if res.status_code == 200:
            data = res.json()
            st.success(f"Online — {data.get('groq_model', '')}")
        else:
            st.error("API returned error")
    except Exception:
        st.error("API offline — start FastAPI server")

    # Auth status
    st.subheader("Auth status")
    if API_KEY and API_KEY != "nlq-key-dev999":
        st.success("API key loaded from .env")
    else:
        st.warning("Using default dev key")


# ─── Tabs ─────────────────────────────────────────────────────────────────────

tab_chat, tab_convert, tab_schema, tab_history, tab_stats = st.tabs([
    "💬 Chat",
    "🔄 Query Converter",
    "🏗️ Schema Suggestion",
    "📜 Query History",
    "📊 Stats"
])


# ═══════════════════════════════════════════════════════════════════════════════
# TAB 1 — CHAT
# ═══════════════════════════════════════════════════════════════════════════════

with tab_chat:
    st.title(f"{DB_ICONS[selected_db]} NL2Query — {selected_db.upper()}")
    st.caption("Ask any question in plain English and get a database query instantly.")

    # Display existing chat history
    for chat in st.session_state.chat_history:
        with st.chat_message("user"):
            st.write(chat["question"])

        with st.chat_message("assistant"):
            if chat["status"] in ("success", "preview"):
                st.markdown("**Generated query:**")
                lang = "javascript" if chat["db_type"] == "mongodb" else "sql"
                st.code(chat["generated_query"], language=lang)

                if chat.get("mode") == "Execute query" and chat.get("query_result"):
                    st.markdown(f"**Results** — {chat['row_count']} row(s) returned")
                    try:
                        st.dataframe(chat["query_result"], use_container_width=True)
                    except Exception:
                        st.json(chat["query_result"])
                elif chat.get("mode") == "Execute query":
                    st.info("Query executed — no rows returned")
            else:
                st.error(f"Error: {chat.get('error_message', 'Unknown error')}")

            st.caption(
                f"{DB_ICONS[chat['db_type']]} {chat['db_type'].upper()} · "
                f"{chat['timestamp']} · {chat.get('mode', 'preview')}"
            )

    # ── Chat Input ────────────────────────────────────────────────────────────

    prefill  = st.session_state.pop("prefill_question", "")
    question = st.chat_input(
        placeholder=f"Ask a question about your {selected_db} database..."
    )

    if prefill and not question:
        question = prefill

    if question:
        with st.chat_message("user"):
            st.write(question)

        with st.chat_message("assistant"):
            with st.spinner("Generating query..."):
                try:
                    if mode == "Preview only":
                        response = requests.post(
                            url=f"{API_BASE_URL}/chat/preview",
                            json={
                                "question":       question,
                                "db_type":        selected_db,
                                "schema_context": schema_context or None
                            },
                            headers=HEADERS,
                            timeout=30
                        )
                        if response.status_code == 200:
                            data = response.json()
                            st.markdown("**Generated query:**")
                            lang = "javascript" if selected_db == "mongodb" else "sql"
                            st.code(data["generated_query"], language=lang)
                            st.session_state.chat_history.append({
                                "question":        question,
                                "db_type":         selected_db,
                                "generated_query": data["generated_query"],
                                "query_result":    None,
                                "row_count":       0,
                                "mode":            mode,
                                "status":          "preview",
                                "error_message":   None,
                                "timestamp":       datetime.now().strftime("%H:%M:%S")
                            })
                        elif response.status_code == 401:
                            st.error("Unauthorized — check your API key in .env")
                        elif response.status_code == 403:
                            st.error("Forbidden — invalid API key")
                        else:
                            st.error(f"Error: {response.json().get('detail', 'API error')}")

                    else:
                        response = requests.post(
                            url=f"{API_BASE_URL}/chat/",
                            json={
                                "question":       question,
                                "db_type":        selected_db,
                                "schema_context": schema_context or None
                            },
                            headers=HEADERS,
                            timeout=30
                        )
                        if response.status_code == 200:
                            data = response.json()
                            st.markdown("**Generated query:**")
                            lang = "javascript" if selected_db == "mongodb" else "sql"
                            st.code(data["generated_query"], language=lang)

                            if data["execution_status"] == "success":
                                st.markdown(f"**Results** — {data['row_count']} row(s)")
                                if data["query_result"]:
                                    try:
                                        st.dataframe(
                                            data["query_result"],
                                            use_container_width=True
                                        )
                                    except Exception:
                                        st.json(data["query_result"])
                                else:
                                    st.info("Query executed — no rows returned")
                            else:
                                st.warning(
                                    f"Query generated but execution failed: "
                                    f"{data.get('error_message', 'Unknown')}"
                                )

                            st.session_state.chat_history.append({
                                "question":        question,
                                "db_type":         selected_db,
                                "generated_query": data["generated_query"],
                                "query_result":    data.get("query_result"),
                                "row_count":       data.get("row_count", 0),
                                "mode":            mode,
                                "status":          data["execution_status"],
                                "error_message":   data.get("error_message"),
                                "timestamp":       datetime.now().strftime("%H:%M:%S")
                            })
                        elif response.status_code == 401:
                            st.error("Unauthorized — check your API key in .env")
                        elif response.status_code == 403:
                            st.error("Forbidden — invalid API key")
                        else:
                            st.error(f"Error: {response.json().get('detail', 'API error')}")

                except requests.exceptions.ConnectionError:
                    st.error("Cannot connect to API. Make sure FastAPI is running on port 8000.")
                except Exception as e:
                    st.error(f"Unexpected error: {str(e)}")


# ═══════════════════════════════════════════════════════════════════════════════
# TAB 2 — QUERY CONVERTER
# ═══════════════════════════════════════════════════════════════════════════════

with tab_convert:
    st.title("🔄 Query Converter")
    st.caption("Convert any database query from one database type to another instantly.")

    col_src, col_arrow, col_tgt = st.columns([5, 1, 5])

    with col_src:
        source_db = st.selectbox(
            "Source database",
            options=DB_TYPES,
            format_func=lambda x: f"{DB_ICONS[x]} {x.upper()}",
            key="conv_source"
        )

    with col_arrow:
        st.write("")
        st.write("")
        st.markdown(
            "<h2 style='text-align:center; margin-top:8px'>→</h2>",
            unsafe_allow_html=True
        )

    with col_tgt:
        default_idx = (DB_TYPES.index(source_db) + 1) % len(DB_TYPES)
        target_db = st.selectbox(
            "Target database",
            options=DB_TYPES,
            index=default_idx,
            format_func=lambda x: f"{DB_ICONS[x]} {x.upper()}",
            key="conv_target"
        )

    st.divider()

    input_query = st.text_area(
        label="Paste your query here",
        placeholder=f"Paste your {source_db.upper()} query here...",
        height=200,
        key="conv_input"
    )

    st.caption("Quick examples:")
    ex_col1, ex_col2, ex_col3 = st.columns(3)

    with ex_col1:
        if st.button("PostgreSQL example", use_container_width=True):
            st.session_state["conv_prefill"] = (
                "SELECT u.name, COUNT(o.id) as order_count\n"
                "FROM users u\n"
                "LEFT JOIN orders o ON u.id = o.user_id\n"
                "WHERE u.created_at >= NOW() - INTERVAL '30 days'\n"
                "GROUP BY u.name\n"
                "ORDER BY order_count DESC\n"
                "LIMIT 10;"
            )
    with ex_col2:
        if st.button("MySQL example", use_container_width=True):
            st.session_state["conv_prefill"] = (
                "SELECT p.name, p.price, c.name as category\n"
                "FROM products p\n"
                "INNER JOIN categories c ON p.category_id = c.id\n"
                "WHERE p.stock < 10\n"
                "ORDER BY p.price DESC\n"
                "LIMIT 5;"
            )
    with ex_col3:
        if st.button("MongoDB example", use_container_width=True):
            st.session_state["conv_prefill"] = (
                '{\n'
                '  "collection": "orders",\n'
                '  "operation": "find",\n'
                '  "filter": {"status": "pending", "amount": {"$gt": 1000}},\n'
                '  "projection": {"customer_name": 1, "amount": 1}\n'
                '}'
            )

    if "conv_prefill" in st.session_state:
        input_query = st.session_state.pop("conv_prefill")

    convert_clicked = st.button(
        label=f"🔄 Convert {source_db.upper()} → {target_db.upper()}",
        type="primary",
        use_container_width=True,
        disabled=not input_query.strip()
    )

    if convert_clicked and input_query.strip():
        if source_db == target_db:
            st.warning("Source and target databases are the same. Please select different databases.")
        else:
            with st.spinner(f"Converting {source_db.upper()} → {target_db.upper()}..."):
                try:
                    response = requests.post(
                        url=f"{API_BASE_URL}/convert/",
                        json={
                            "query":     input_query.strip(),
                            "source_db": source_db,
                            "target_db": target_db
                        },
                        headers=HEADERS,
                        timeout=30
                    )

                    if response.status_code == 200:
                        data = response.json()
                        st.success(
                            f"Successfully converted "
                            f"{DB_ICONS[source_db]} {source_db.upper()} → "
                            f"{DB_ICONS[target_db]} {target_db.upper()}"
                        )
                        st.divider()
                        left, right = st.columns(2)
                        with left:
                            st.markdown(f"**{DB_ICONS[source_db]} Original ({source_db.upper()}):**")
                            lang_src = "javascript" if source_db == "mongodb" else "sql"
                            st.code(data["original_query"], language=lang_src)
                        with right:
                            st.markdown(f"**{DB_ICONS[target_db]} Converted ({target_db.upper()}):**")
                            lang_tgt = "javascript" if target_db == "mongodb" else "sql"
                            st.code(data["converted_query"], language=lang_tgt)

                        if data.get("notes"):
                            st.divider()
                            st.info(f"📝 **Conversion notes:** {data['notes']}")

                        st.session_state.conversions.append({
                            "source_db":       source_db,
                            "target_db":       target_db,
                            "original_query":  data["original_query"],
                            "converted_query": data["converted_query"],
                            "notes":           data.get("notes"),
                            "timestamp":       datetime.now().strftime("%H:%M:%S")
                        })

                    elif response.status_code in (401, 403):
                        st.error("Unauthorized — check your API key in .env")
                    else:
                        st.error(f"Conversion failed: {response.json().get('detail', 'API error')}")

                except requests.exceptions.ConnectionError:
                    st.error("Cannot connect to API. Make sure FastAPI is running on port 8000.")
                except Exception as e:
                    st.error(f"Unexpected error: {str(e)}")

    if st.session_state.conversions:
        st.divider()
        st.subheader("Previous conversions this session")
        for conv in reversed(st.session_state.conversions):
            with st.expander(
                f"{DB_ICONS[conv['source_db']]} {conv['source_db'].upper()} → "
                f"{DB_ICONS[conv['target_db']]} {conv['target_db'].upper()} "
                f"— {conv['timestamp']}"
            ):
                c1, c2 = st.columns(2)
                with c1:
                    st.markdown(f"**Original ({conv['source_db'].upper()}):**")
                    lang = "javascript" if conv["source_db"] == "mongodb" else "sql"
                    st.code(conv["original_query"], language=lang)
                with c2:
                    st.markdown(f"**Converted ({conv['target_db'].upper()}):**")
                    lang = "javascript" if conv["target_db"] == "mongodb" else "sql"
                    st.code(conv["converted_query"], language=lang)
                if conv.get("notes"):
                    st.caption(f"📝 {conv['notes']}")


# ═══════════════════════════════════════════════════════════════════════════════
# TAB 3 — SCHEMA SUGGESTION
# ═══════════════════════════════════════════════════════════════════════════════

with tab_schema:
    st.title("🏗️ Schema Suggestion")
    st.caption(
        "Describe what you want to build in plain English "
        "— get a complete production-ready database schema instantly."
    )

    col_left, col_right = st.columns([3, 1])
    with col_left:
        schema_db_type = st.selectbox(
            "Target database",
            options=DB_TYPES,
            format_func=lambda x: f"{DB_ICONS[x]} {x.upper()}",
            key="schema_db_type"
        )
    with col_right:
        include_sample = st.checkbox(
            "Include sample data",
            value=False,
            key="include_sample"
        )

    st.caption("Quick examples — click to load:")
    ex1, ex2, ex3, ex4 = st.columns(4)

    with ex1:
        if st.button("🛒 E-commerce", use_container_width=True):
            st.session_state["schema_prefill"] = (
                "I want to build an e-commerce platform. "
                "It should have users who can register and login. "
                "Products belong to categories and have inventory tracking. "
                "Users can place orders containing multiple products. "
                "Each order has a payment record and a shipping address. "
                "Products can have reviews and ratings from users."
            )
    with ex2:
        if st.button("🏥 Hospital", use_container_width=True):
            st.session_state["schema_prefill"] = (
                "I want to build a hospital management system. "
                "It should manage doctors, patients, appointments, "
                "medical records, prescriptions, and billing. "
                "Doctors belong to departments and have specializations. "
                "Patients can book appointments with doctors. "
                "Each appointment can result in a prescription with medicines."
            )
    with ex3:
        if st.button("📚 LMS", use_container_width=True):
            st.session_state["schema_prefill"] = (
                "I want to build a Learning Management System. "
                "It should have students, instructors and courses. "
                "Courses have modules and lessons with video content. "
                "Students can enroll in courses and track their progress. "
                "Instructors can create quizzes and assignments. "
                "Students receive certificates on course completion."
            )
    with ex4:
        if st.button("🏦 Banking", use_container_width=True):
            st.session_state["schema_prefill"] = (
                "I want to build a banking system. "
                "It should manage customers, accounts, and transactions. "
                "Customers can have multiple accounts (savings, checking). "
                "Accounts support deposits, withdrawals and transfers. "
                "Each transaction has a type, amount, and timestamp. "
                "System should support loans with repayment schedules."
            )

    prefill_schema = st.session_state.pop("schema_prefill", "")

    requirement = st.text_area(
        label="Describe your requirement",
        value=prefill_schema,
        placeholder=(
            "Example: I want to build a social media app with users, posts, "
            "comments, likes, followers and direct messaging..."
        ),
        height=180,
        key="schema_requirement"
    )

    st.caption(f"{len(requirement)}/3000 characters")

    generate_clicked = st.button(
        label="🏗️ Generate Schema",
        type="primary",
        use_container_width=True,
        disabled=not requirement.strip()
    )

    if generate_clicked and requirement.strip():
        with st.spinner("Analyzing requirements and generating schema..."):
            try:
                response = requests.post(
                    url=f"{API_BASE_URL}/schema/suggest",
                    json={
                        "requirement":         requirement.strip(),
                        "db_type":             schema_db_type,
                        "include_sample_data": include_sample
                    },
                    headers=HEADERS,
                    timeout=60
                )

                if response.status_code == 200:
                    data = response.json()
                    st.success(
                        f"Generated schema with {len(data['tables'])} tables "
                        f"for {DB_ICONS[schema_db_type]} {schema_db_type.upper()}"
                    )
                    st.divider()

                    m1, m2, m3 = st.columns(3)
                    m1.metric("Tables",        len(data["tables"]))
                    m2.metric("Relationships", len(data["relationships"]))
                    m3.metric("Total columns", sum(len(t["columns"]) for t in data["tables"]))

                    st.divider()
                    r_tab1, r_tab2, r_tab3, r_tab4 = st.tabs([
                        "📋 Tables",
                        "🔗 Relationships",
                        "📝 CREATE Scripts",
                        "📥 Sample Data"
                    ])

                    with r_tab1:
                        for table in data["tables"]:
                            with st.expander(
                                f"📋 {table['table_name'].upper()} — {table['description']}",
                                expanded=True
                            ):
                                col_data = [
                                    {
                                        "Column":      col["name"],
                                        "Type":        col["type"],
                                        "Constraints": col.get("constraints") or "—",
                                        "Description": col.get("description") or "—"
                                    }
                                    for col in table["columns"]
                                ]
                                st.dataframe(
                                    col_data,
                                    use_container_width=True,
                                    hide_index=True
                                )
                                if table.get("indexes"):
                                    st.markdown("**Indexes:**")
                                    for idx in table["indexes"]:
                                        st.code(idx, language="sql")

                    with r_tab2:
                        st.markdown("### Table Relationships")
                        if data["relationships"]:
                            for rel in data["relationships"]:
                                st.markdown(f"- `{rel}`")
                        else:
                            st.info("No relationships defined")
                        if data.get("design_notes"):
                            st.divider()
                            st.markdown("### Design Notes")
                            st.info(data["design_notes"])

                    with r_tab3:
                        st.markdown("### Complete CREATE Scripts")
                        st.caption("Copy and run these scripts in your database")
                        lang = "javascript" if schema_db_type == "mongodb" else "sql"
                        st.code(data["create_scripts"], language=lang)
                        ext = "js" if schema_db_type == "mongodb" else "sql"
                        st.download_button(
                            label=f"⬇️ Download .{ext} file",
                            data=data["create_scripts"],
                            file_name=f"schema_{schema_db_type}.{ext}",
                            mime="text/plain",
                            use_container_width=True
                        )

                    with r_tab4:
                        if data.get("sample_data"):
                            st.markdown("### Sample INSERT Statements")
                            st.code(data["sample_data"], language="sql")
                            st.download_button(
                                label="⬇️ Download sample data",
                                data=data["sample_data"],
                                file_name=f"sample_data_{schema_db_type}.sql",
                                mime="text/plain",
                                use_container_width=True
                            )
                        else:
                            st.info(
                                "Sample data not requested. "
                                "Check 'Include sample data' and regenerate."
                            )

                elif response.status_code in (401, 403):
                    st.error("Unauthorized — check your API key in .env")
                else:
                    st.error(f"Schema generation failed: {response.json().get('detail', 'API error')}")

            except requests.exceptions.ConnectionError:
                st.error("Cannot connect to API. Make sure FastAPI is running on port 8000.")
            except Exception as e:
                st.error(f"Unexpected error: {str(e)}")


# ═══════════════════════════════════════════════════════════════════════════════
# TAB 4 — HISTORY
# ═══════════════════════════════════════════════════════════════════════════════

with tab_history:
    st.title("📜 Query History")

    col1, col2, col3 = st.columns([2, 1, 1])
    with col1:
        search_term = st.text_input(
            "Search",
            placeholder="Search by keyword...",
            label_visibility="collapsed"
        )
    with col2:
        filter_db = st.selectbox(
            "Filter by DB",
            ["all"] + DB_TYPES,
            label_visibility="collapsed"
        )
    with col3:
        st.write("")
        if st.button("🗑️ Clear all history", use_container_width=True):
            try:
                res = requests.delete(
                    f"{API_BASE_URL}/history",
                    headers=HEADERS,
                    timeout=5
                )
                if res.status_code == 200:
                    st.success("History cleared!")
                    st.rerun()
                elif res.status_code in (401, 403):
                    st.error("Unauthorized — check API key")
            except Exception:
                st.error("Could not clear history")

    try:
        if search_term:
            res = requests.get(
                f"{API_BASE_URL}/history/search",
                params={"keyword": search_term},
                headers=HEADERS,
                timeout=5
            )
        elif filter_db != "all":
            res = requests.get(
                f"{API_BASE_URL}/history/{filter_db}",
                headers=HEADERS,
                timeout=5
            )
        else:
            res = requests.get(
                f"{API_BASE_URL}/history",
                headers=HEADERS,
                timeout=5
            )

        if res.status_code == 200:
            records = res.json()
            if records:
                st.caption(f"{len(records)} record(s) found")
                for record in records:
                    status_icon = (
                        "✅" if record["execution_status"] == "success"
                        else "👁️" if record["execution_status"] == "preview"
                        else "❌"
                    )
                    with st.expander(
                        f"{status_icon} "
                        f"{DB_ICONS.get(record['db_type'], '')} "
                        f"{record['question'][:70]} "
                        f"— {record['created_at'][:19]}"
                    ):
                        st.markdown("**Question:**")
                        st.write(record["question"])
                        st.markdown("**Generated query:**")
                        lang = "javascript" if record["db_type"] == "mongodb" else "sql"
                        st.code(record["generated_query"], language=lang)
                        st.caption(
                            f"DB: {record['db_type'].upper()} | "
                            f"Status: {record['execution_status']} | "
                            f"Rows: {record.get('row_count', 0)}"
                        )
            else:
                st.info("No history yet — ask some questions first!")
        elif res.status_code in (401, 403):
            st.error("Unauthorized — check API key in .env")
        else:
            st.error("Could not load history")

    except Exception as e:
        st.error(f"API error: {str(e)}")


# ═══════════════════════════════════════════════════════════════════════════════
# TAB 5 — STATS
# ═══════════════════════════════════════════════════════════════════════════════

with tab_stats:
    st.title("📊 Query Statistics")

    if st.button("🔄 Refresh stats"):
        st.rerun()

    try:
        res = requests.get(
            f"{API_BASE_URL}/history/stats",
            headers=HEADERS,
            timeout=5
        )
        if res.status_code == 200:
            stats = res.json()

            c1, c2, c3, c4 = st.columns(4)
            c1.metric("Total queries", stats["total"])
            c2.metric("Executed",      stats["success"])
            c3.metric("Preview only",  stats["preview"])
            c4.metric("Errors",        stats["error"])

            st.divider()

            st.subheader("Queries by database")
            by_db = stats.get("by_db", {})
            if by_db:
                max_count = max(by_db.values())
                for db_name, count in by_db.items():
                    st.progress(
                        value=count / max_count,
                        text=(
                            f"{DB_ICONS.get(db_name, '')} "
                            f"{db_name.upper()} — {count} queries"
                        )
                    )
            else:
                st.info("No data yet — ask some questions first!")

        elif res.status_code in (401, 403):
            st.error("Unauthorized — check API key in .env")
        else:
            st.error("Could not load stats")

    except Exception as e:
        st.error(f"API error: {str(e)}")