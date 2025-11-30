import datetime
from typing import Any, Dict

import pandas as pd
import streamlit as st
from streamlit_gsheets import GSheetsConnection


_STYLE_KEY = "_add_record_modal_style_injected"


def inject_add_record_modal_style() -> None:
    """Center the Streamlit popover like a modal and dim the background."""
    if st.session_state.get(_STYLE_KEY):
        return
    st.session_state[_STYLE_KEY] = True
    st.markdown(
        """
        <style>
        /* Center the add-record popover and add a dimmed backdrop */
        div[data-testid="stPopoverBody"],
        div[data-testid="stPopoverContent"] {
            position: fixed !important;
            inset: 0 !important;
            width: 100vw !important;
            height: 100vh !important;
            display: flex;
            align-items: center;
            justify-content: center;
            background: rgba(15, 23, 42, 0.55);
            padding: 20px;
            z-index: 1000;
        }
        div[data-testid="stPopoverBody"] > div,
        div[data-testid="stPopoverContent"] > div {
            width: min(960px, 100%);
            max-height: 90vh;
            overflow: auto;
            background: var(--background-color, #0e1117);
            border-radius: 12px;
            box-shadow: 0 24px 60px rgba(0, 0, 0, 0.35);
            border: 1px solid rgba(255, 255, 255, 0.08);
            padding: 12px 14px;
        }
        /* Hide caret/arrow so modal looks centered */
        div[data-testid="stPopoverCaret"] {
            display: none !important;
        }
        </style>
        """,
        unsafe_allow_html=True,
    )


def safe_number(value: Any):
    return None if value in ("", None) else value


def load_sheet(conn: GSheetsConnection, worksheet: str) -> pd.DataFrame:
    df = conn.read(worksheet=worksheet, ttl="2m")
    return pd.DataFrame() if df is None else pd.DataFrame(df)


def append_row(conn: GSheetsConnection, worksheet: str, row: Dict[str, Any]) -> None:
    current = load_sheet(conn, worksheet)
    updated = pd.concat([current, pd.DataFrame([row])], ignore_index=True)
    conn.update(worksheet=worksheet, data=updated)


def render_project_form(form_key: str = "project_add_form") -> None:
    """Render the Project-only form (no target dropdown)."""
    inject_add_record_modal_style()
    try:
        conn = st.connection("gsheets", type=GSheetsConnection)
    except Exception as exc:  # noqa: BLE001
        st.error(f"ไม่สามารถเชื่อมต่อ Google Sheets ได้: {exc}")
        return

    with st.form(form_key, clear_on_submit=True):
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


def render_invoice_form(form_key: str = "invoice_add_form") -> None:
    """Render the Invoice-only form (no target dropdown)."""
    inject_add_record_modal_style()
    try:
        conn = st.connection("gsheets", type=GSheetsConnection)
    except Exception as exc:  # noqa: BLE001
        st.error(f"ไม่สามารถเชื่อมต่อ Google Sheets ได้: {exc}")
        return

    with st.form(form_key, clear_on_submit=True):
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


def render_add_record_form(default_target: str = "Project", form_key: str = "add_record_form") -> None:
    """
    Backwards-compatible wrapper for legacy calls.
    Chooses a fixed form (Project or Invoice) without showing a selector.
    """
    if default_target.lower().startswith("inv"):
        render_invoice_form(form_key=form_key)
    else:
        render_project_form(form_key=form_key)
