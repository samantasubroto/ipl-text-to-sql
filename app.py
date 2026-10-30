"""Streamlit UI for the IPL text-to-SQL app.

Run from the project root:
    streamlit run app.py
"""
import hmac
import os
import sqlite3

import streamlit as st

from scripts.load_db import main as build_database
from src.db import DB_PATH, QueryTimeoutError, run_query
from src.guardrails import UnsafeSQLError
from src.llm import generate_sql

MAX_QUESTIONS_PER_SESSION = 15

st.set_page_config(page_title="IPL Text-to-SQL", page_icon="🏏")
st.title("🏏 IPL Text-to-SQL")
st.caption("Ask a question about IPL matches (2008-2017) in plain English.")


def get_secret(name: str) -> str | None:
    """Read a setting from environment variables, then Streamlit secrets."""
    value = os.environ.get(name)
    if value:
        return value
    try:
        return st.secrets.get(name)
    except Exception:  # no secrets file configured (e.g. running locally)
        return None


# The database is git-ignored, so build it from the CSVs on first start.
if not DB_PATH.exists():
    with st.spinner("Setting up the database (first start only)..."):
        build_database()

# Optional password gate: only active when APP_PASSWORD is set.
app_password = get_secret("APP_PASSWORD")
if app_password and not st.session_state.get("authenticated"):
    entered = st.text_input("Password", type="password")
    if entered:
        if hmac.compare_digest(entered, app_password):
            st.session_state["authenticated"] = True
            st.rerun()
        else:
            st.error("Incorrect password.")
    st.stop()

if st.session_state.get("question_count", 0) >= MAX_QUESTIONS_PER_SESSION:
    st.info("You've reached the question limit for this session. Reload the page to start a new one.")
    st.stop()

EXAMPLES = [
    "Which team won the most matches in 2016?",
    "Who are the top 5 run scorers of all time?",
    "How many matches were decided by a super over?",
]

with st.expander("Example questions"):
    for example in EXAMPLES:
        st.markdown(f"- {example}")

with st.form("question_form"):
    question = st.text_input("Your question")
    submitted = st.form_submit_button("Run")

if submitted:
    question = question.strip()
    if not question:
        st.warning("Please enter a question.")
        st.stop()
    st.session_state["question_count"] = st.session_state.get("question_count", 0) + 1

    try:
        with st.spinner("Generating SQL..."):
            sql = generate_sql(question)
    except Exception as e:  # provider SDK errors differ (OpenAI, Gemini)
        st.error(f"LLM request failed: {e}")
        st.stop()

    if sql.strip().upper() == "CANNOT_ANSWER":
        st.info("I can't answer that from the IPL matches and deliveries data. Try rephrasing.")
        st.stop()

    try:
        with st.spinner("Running query..."):
            final_sql, df = run_query(sql)
    except UnsafeSQLError as e:
        st.error(f"The generated query was blocked: {e}")
        st.code(sql, language="sql")
        st.stop()
    except QueryTimeoutError as e:
        st.error(str(e))
        st.code(sql, language="sql")
        st.stop()
    except sqlite3.Error as e:
        st.error(f"The query failed to run: {e}")
        st.code(sql, language="sql")
        st.stop()

    st.subheader("Generated SQL")
    st.code(final_sql, language="sql")

    st.subheader("Results")
    if df.empty:
        st.info("The query ran but returned no rows.")
    else:
        st.dataframe(df, width="stretch", hide_index=True)
        st.caption(f"{len(df)} row(s)")
