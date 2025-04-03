from langchain_experimental.sql import SQLDatabaseChain
from langchain_community.llms import Ollama
from langchain_community.utilities import SQLDatabase
import streamlit as st
import textwrap as tw

def text_to_sql(query: str, schema: str) -> str:
    llm = Ollama(model="sqlcoder", temperature=0.1)
    query = """
    ### Instructions:
    Your task is to convert a question into a SQL query, given a Postgres database schema.
    Adhere to these rules:
    - **Deliberately go through the question and database schema word by word** to appropriately answer the question
    - **Use Table Aliases** to prevent ambiguity.
    - When creating a ratio, always cast the numerator as float

    ### Input:
    Generate a SQL query that answers the question `{query}`.
    This query will run on a database whose schema is represented in this string:
    `{schema}`

    ### Response:
    Based on your instructions, here is the SQL query I have generated to answer the question `{query}`:
    sql
    """.format(query=query, schema=schema)

    sql = llm(query)
    return sql.strip()

st.title("SQL Query Generator")
st.write("This app generates SQL queries from natural language questions.")
st.write("Enter your question and database schema below:")
schema = st.text_area("Database Schema", height=200)
question = st.text_area("Question", height=100)

if st.button("Generate SQL Query"):
    if schema and question:
        sql_query = text_to_sql(question, schema)
        st.subheader("Generated SQL Query:")
        st.code("\n".join(tw.wrap(sql_query)), language='sql')
    else:
        st.error("Please provide both the database schema and the question.")
        