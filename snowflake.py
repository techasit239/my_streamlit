# streamlit_app.py

import streamlit as st

conn = st.connection("snowflake")
df = conn.query("SELECT * FROM FINAL_PROJECT;", ttl="10m")

for row in df.itertuples():
    st.write(f"{row}")