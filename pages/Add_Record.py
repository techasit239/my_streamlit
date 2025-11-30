import datetime
from typing import Any, Dict

import pandas as pd
import streamlit as st
from streamlit_gsheets import GSheetsConnection

st.set_page_config(page_title="Add Record", page_icon="➕", layout="wide")


def safe_number(value: Any):
    return None if value in ("", None) else value


def load_sheet(conn: GSheetsConnection, worksheet: str) -> pd.DataFrame:
    df = conn.read(worksheet=worksheet, ttl="2m")
    return pd.DataFrame() if df is None else pd.DataFrame(df)


def append_row(conn: GSheetsConnection, worksheet: str, row: Dict[str, Any]) -> None:
    current = load_sheet(conn, worksheet)
    updated = pd.concat([current, pd.DataFrame([row])], ignore_index=True)
    conn.update(worksheet=worksheet, data=updated)


st.title("Add Record")
st.caption("เลือกว่าจะเพิ่มข้อมูลให้ Project หรือ Invoice แล้วกรอกฟอร์มด้านล่าง")

# Navigation links
nav_cols = st.columns(3)
with nav_cols[0]:
    st.page_link("pages/project.py", label="📊 Project dashboard")
with nav_cols[1]:
    st.page_link("pages/Invoice.py", label="🧾 Invoice dashboard")
with nav_cols[2]:
    st.page_link("pages/Add_Record.py", label="➕ Add record (you are here)", disabled=True)

try:
    conn = st.connection("gsheets", type=GSheetsConnection)
    connection_ok = True
except Exception as exc:  # noqa: BLE001
    connection_ok = False
    st.error(f"ไม่สามารถเชื่อมต่อ Google Sheets ได้: {exc}")
    st.stop()

target = st.radio("บันทึกไปยัง", ["Project", "Invoice"], horizontal=True)

with st.form("add_record_form", clear_on_submit=True):
    if target == "Project":
        st.subheader("Project record")
        c1, c2, c3 = st.columns(3)
        project = c1.text_input("Project name", placeholder="Project A")
        customer = c2.text_input("Customer", placeholder="Customer X")
        engineer = c3.text_input("Project Engineer", placeholder="Engineer 1")

        c4, c5, c6 = st.columns(3)
        year = c4.number_input("Project year", min_value=2000, max_value=2100, value=2024, step=1)
        order_no = c5.text_input("Order number", placeholder="123456")
        product = c6.text_input("Product", placeholder="Control Panel")

        c7, c8, c9 = st.columns(3)
        qty = c7.number_input("Qty", min_value=0, value=0, step=1)
        value = c8.number_input("Project Value", min_value=0.0, value=0.0, step=1000.0)
        balance = c9.number_input("Balance", min_value=0.0, value=0.0, step=1000.0)

        c10, c11 = st.columns(2)
        status = c10.selectbox("Status", ["On track", "Delayed", "Shipped", "In progress", "Closed"])
        progress_pct = c11.slider("Progress (%)", min_value=0, max_value=100, value=0)

        project_phrase = st.text_input("Project phrase (optional)", placeholder="e.g. Fabrication")

        submitted = st.form_submit_button("Save to Project", use_container_width=True)
        if submitted:
            row = {
                "Project": project,
                "Customer": customer,
                "Project Engineer": engineer,
                "Project year": safe_number(year),
                "Order number": order_no,
                "Product": product,
                "Qty": safe_number(qty),
                "Project Value": safe_number(value),
                "Balance": safe_number(balance),
                "Status": status,
                "Progress": progress_pct / 100,
                "Project Phrase": project_phrase,
                "Created at": datetime.datetime.utcnow().isoformat(),
            }
            try:
                append_row(conn, "Project", row)
                st.cache_data.clear()
                st.success("บันทึก Project สำเร็จ")
            except Exception as exc:  # noqa: BLE001
                st.error(f"บันทึกไม่สำเร็จ: {exc}")
    else:
        st.subheader("Invoice record")
        c1, c2, c3 = st.columns(3)
        project_year = c1.number_input("Project year", min_value=2000, max_value=2100, value=2024, step=1)
        engineer = c2.text_input("Project Engineer", placeholder="Engineer 1")
        sale_order = c3.text_input("Sale order No.", placeholder="123456")

        c4, c5, c6 = st.columns(3)
        customer = c4.text_input("Customer", placeholder="Customer X")
        invoice_value = c5.number_input("Invoice value", min_value=0.0, value=0.0, step=1000.0)
        plan_date = c6.date_input("Invoice plan date", value=None)

        c7, c8 = st.columns(2)
        payment_status = c7.selectbox("Payment Status", ["Planned", "Invoiced", "Paid", "Overdue"])
        currency = c8.text_input("Currency unit", placeholder="THB")

        issued_date = st.date_input("Issued Date", value=None)

        submitted = st.form_submit_button("Save to Invoice", use_container_width=True)
        if submitted:
            row = {
                "Project year": safe_number(project_year),
                "Project Engineer": engineer,
                "Sale order No.": sale_order,
                "Customer": customer,
                "Invoice value": safe_number(invoice_value),
                "Invoice plan date": pd.to_datetime(plan_date) if plan_date else None,
                "Issued Date": pd.to_datetime(issued_date) if issued_date else None,
                "Payment Status": payment_status,
                "Currency unit": currency,
                "Created at": datetime.datetime.utcnow().isoformat(),
            }
            try:
                append_row(conn, "Invoice", row)
                st.cache_data.clear()
                st.success("บันทึก Invoice สำเร็จ")
            except Exception as exc:  # noqa: BLE001
                st.error(f"บันทึกไม่สำเร็จ: {exc}")
