import uuid

import pandas as pd
import streamlit as st

from src.config import validate_settings
from src.agent.graph import graph
from src.charts import create_chart

st.set_page_config(
    page_title="AI Data Analyst",
    page_icon="📊",
    layout="wide",
)

# ---------------------------------------------------------------------
# Sidebar
# ---------------------------------------------------------------------

with st.sidebar:
    st.markdown("### AI Data Analyst")

    problems = validate_settings()

    if problems:
        st.error("Configuration problem(s):\n\n" + "\n".join(f"- {p}" for p in problems))
    else:
        try:
            from src.database import test_connection

            if test_connection():
                st.success("Database: Connected")
            else:
                st.error("Database: Unreachable")
        except Exception as exc:
            st.error(f"Database: {exc}")

    st.markdown("---")

    show_sql = st.checkbox("Show generated SQL", value=True)
    show_raw_data = st.checkbox("Show raw data table", value=True)

    st.markdown("---")

    if st.button("New Conversation"):
        st.session_state.thread_id = str(uuid.uuid4())
        st.session_state.messages = []
        st.session_state.conversation_context = []
        st.rerun()


# ---------------------------------------------------------------------
# Session state
# ---------------------------------------------------------------------

if "thread_id" not in st.session_state:
    st.session_state.thread_id = str(uuid.uuid4())

if "messages" not in st.session_state:
    st.session_state.messages = []

if "conversation_context" not in st.session_state:
    st.session_state.conversation_context = []


# ---------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------

st.title("AI Data Analyst")
st.caption("Natural Language → SQL → Business Insights")

with st.expander("Example questions"):
    st.markdown(
        "- What was total revenue in 2025?\n"
        "- Show monthly revenue for 2025.\n"
        "- Top 5 product categories by revenue.\n"
        "- Which month had the biggest decline?\n"
        "- Why did revenue fall in August 2025?\n"
    )

for message in st.session_state.messages:
    with st.chat_message(message["role"]):
        st.markdown(message["content"])

question = st.chat_input("Ask a question about your business data...")

if question:
    st.session_state.messages.append({"role": "user", "content": question})

    with st.chat_message("user"):
        st.markdown(question)

    with st.chat_message("assistant"):
        answer = "Unable to complete analysis."
        result = {}

        with st.status("Analyzing your data...", expanded=True) as status:
            try:
                st.write("Understanding question...")
                st.write("Inspecting database schema...")
                st.write("Generating SQL...")
                st.write("Validating query...")
                st.write("Running analysis...")

                config = {
                    "configurable": {"thread_id": st.session_state.thread_id}
                }

                result = graph.invoke(
                    {
                        "question": question,
                        "conversation_context": st.session_state.conversation_context,
                    },
                    config=config,
                )

                status.update(label="Analysis complete", state="complete")

            except Exception as exc:
                status.update(label="Analysis failed", state="error")
                st.error(f"Something went wrong: {exc}")

        answer = result.get("final_answer", "Unable to complete analysis.")
        st.markdown(answer)

        important_points = result.get("important_points") or []
        if important_points:
            st.markdown("**Key findings:**")
            for point in important_points:
                st.markdown(f"- {point}")

        query_result = result.get("query_result")
        df = pd.DataFrame()

        if query_result:
            df = pd.DataFrame(query_result.get("rows", []))

            if show_raw_data and not df.empty:
                st.dataframe(df, width="stretch")

        plan = result.get("chart_plan")
        if query_result and plan:
            fig = create_chart(query_result, plan)
            if fig:
                st.plotly_chart(fig, width="stretch")

        sql = result.get("generated_sql")
        if show_sql and sql:
            with st.expander("View generated SQL"):
                st.code(sql, language="sql")

            explanation = result.get("sql_explanation")
            if explanation:
                with st.expander("Explain this query"):
                    st.write(explanation)

        if not df.empty:
            csv = df.to_csv(index=False).encode("utf-8")
            st.download_button("Download CSV", csv, "analysis.csv", "text/csv")

    st.session_state.messages.append({"role": "assistant", "content": answer})

    st.session_state.conversation_context.append(
        {
            "question": question,
            "sql": result.get("generated_sql", ""),
            "summary": answer,
        }
    )
    # Bound how much context we carry forward.
    st.session_state.conversation_context = st.session_state.conversation_context[-5:]
