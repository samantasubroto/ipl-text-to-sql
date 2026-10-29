"""Streamlit UI for the IPL text-to-SQL app.

Run from the project root:
    streamlit run app.py
"""
import sqlite3

import streamlit as st

from src.db import QueryTimeoutError, run_query
from src.guardrails import UnsafeSQLError
from src.llm import generate_sql

st.set_page_config(page_title="IPL Text-to-SQL", page_icon="🏏")
st.title("🏏 IPL Text-to-SQL")
st.caption("Ask a question about IPL matches (2008-2017) in plain English.")

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
