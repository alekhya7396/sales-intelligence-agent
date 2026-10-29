import os
import requests
import pandas as pd
import streamlit as st
import plotly.express as px
from database import initialize_database, query_df
from agent import answer_question

st.set_page_config(page_title="Sales Intelligence Agent", page_icon="📊", layout="wide")
st.title("📊 Sales Intelligence Agent")
st.caption("Ask questions in normal English. Answers are calculated from the sales database.")

with st.sidebar:
    st.header("Data quality")
    try:
        quality = initialize_database()
        st.metric("Source rows", quality["source_rows"])
        st.metric("Valid sales", quality["valid_sales"])
        st.metric("Excluded rows", quality["excluded_rows"])
        with st.expander("Why were rows excluded?"):
            st.write("Excluded transaction IDs:", ", ".join(quality["excluded_transaction_ids"]) or "None")
            st.caption("Rules: completed status, valid date and numeric values, positive quantity, non-negative price/discount/revenue, and required identifiers.")
    except Exception as exc:
        st.error(f"Could not load the dataset: {exc}")

sample_questions = [
    "What is the total revenue?",
    "Which product generated the highest revenue?",
    "What is the monthly revenue trend?",
    "Which region generated the highest sales?",
    "How did revenue change between March and April?",
    "Which category generated the highest revenue?",
    "Compare online and retail sales channels",
]
with st.expander("Try an example question", expanded=True):
    cols = st.columns(2)
    for i, question in enumerate(sample_questions):
        if cols[i % 2].button(question, key=f"sample_{i}", use_container_width=True):
            st.session_state["question"] = question

question = st.text_input("Your question", key="question", placeholder="e.g. Which region generated the highest sales?")
if st.button("Ask agent", type="primary"):
    if not question.strip():
        st.warning("Enter a question first.")
    else:
        try:
            result = answer_question(question)
            if result["ok"]:
                st.success(result["answer"])
                data = result.get("data", [])
                if data:
                    df = pd.DataFrame(data)
                    st.subheader("Supporting figures")
                    st.dataframe(df, use_container_width=True, hide_index=True)
                    if result["intent"] == "monthly_trend" and "month" in df and "revenue" in df:
                        chart = px.bar(df, x="month", y="revenue", title="Monthly revenue", labels={"month": "Month", "revenue": "Revenue (₹)"})
                        st.plotly_chart(chart, use_container_width=True)
                    elif result["intent"] in ["top_product", "top_region", "top_category", "channel_sales"]:
                        category_col = {"top_product": "Product", "top_region": "Region", "top_category": "Category", "channel_sales": "Sales_channel"}[result["intent"]]
                        if category_col in df and "total_revenue" in df:
                            chart = px.bar(df, x=category_col, y="total_revenue", title="Revenue breakdown", labels={"total_revenue": "Revenue (₹)"})
                            st.plotly_chart(chart, use_container_width=True)
                with st.expander("Technical details"):
                    st.write("Intent interpreter:", result.get("interpreter", "rules"))
                    st.code(result.get("sql") or "No query executed", language="sql")
            else:
                st.info(result["answer"])
        except Exception as exc:
            st.error(f"Unable to answer this question: {exc}")

st.divider()
st.caption("Revenue = quantity × unit price − discount. Only valid completed transactions are included. LLM interpretation is optional; SQL templates and calculations remain controlled by the application.")
