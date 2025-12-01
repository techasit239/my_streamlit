import streamlit as st
import pandas as pd
import numpy as np
from datetime import datetime

# ---------------------------------------------------
# PAGE CONFIG
# ---------------------------------------------------
st.set_page_config(
    page_title="CRM Invoice Dashboard",
    layout="wide"
)

# ---------------------------------------------------
# LOAD & PREPARE DATA
# ---------------------------------------------------
@st.cache_data
def load_data():
    DATA_URL = (
        "https://raw.githubusercontent.com/techasit239/my_streamlit/"
        "refs/heads/main/BI%20Project%20status_Prototype_R1_invoice.csv"
    )

    df = pd.read_csv(DATA_URL)

    # เก็บ column name ให้สะอาด เช่น " Total amount " -> "Total amount"
    df.columns = df.columns.str.strip()

    # --- แปลงวันที่ที่สำคัญ ---
    date_cols = [
        "Invoice plan date",
        "Invoice Issued Date",
        "Invoice due date",
        "Plan payment date",
        "Expected Payment date",
        "Actual Payment received date",
    ]
    for c in date_cols:
        df[c] = pd.to_datetime(df[c], errors="coerce", infer_datetime_format=True)

    # --- แปลงตัวเลขที่สำคัญ ---
    money_cols = ["Total amount", "Invoice value"]
    for c in money_cols:
        df[c] = (
            df[c]
            .astype(str)
            .str.replace(",", "", regex=False)
            .str.replace(" ", "", regex=False)
            .str.replace("-", "0", regex=False)
        )
        df[c] = pd.to_numeric(df[c], errors="coerce").fillna(0.0)

    # --- เตรียม field สำหรับ CRM ---
    today = pd.Timestamp.today().normalize()

    # จำนวนวันจากวันนี้ไปถึง Expected Payment date
    df["days_to_expected"] = (df["Expected Payment date"] - today).dt.days

    # overdue = วันนี้เกิน Expected Payment date แล้ว
    df["is_overdue"] = df["days_to_expected"] < 0

    # ความแตกต่างระหว่าง Actual vs Expected (ใช้วิเคราะห์เร็ว/ช้า)
    df["days_diff_actual_expected"] = (
        df["Actual Payment received date"] - df["Expected Payment date"]
    ).dt.days

    # ทำ field ช่วยสำหรับ Paid ว่าจ่ายแล้วหรือยัง
    df["Payment Status"] = df["Payment Status"].astype(str).str.strip()
    df["status_lower"] = df["Payment Status"].str.lower()
    df["is_paid"] = df["status_lower"].str.startswith("paid")

    return df


df = load_data()

# ---------------------------------------------------
# SIDEBAR FILTERS
# ---------------------------------------------------
st.sidebar.header("Filters")

# Filter ตาม Payment Status (CRM อยากเลือกดูสถานะต่าง ๆ ได้)
payment_statuses = sorted(df["Payment Status"].dropna().unique())
status_selected = st.sidebar.multiselect(
    "Payment Status",
    payment_statuses,
    default=payment_statuses
)

df_filtered = df[df["Payment Status"].isin(status_selected)].copy()

# Optional: filter ตามลูกค้า
customers = ["All"] + sorted(df_filtered["Customer"].dropna().unique())
customer_selected = st.sidebar.selectbox("Customer", customers, index=0)

if customer_selected != "All":
    df_filtered = df_filtered[df_filtered["Customer"] == customer_selected]

# ---------------------------------------------------
# SECTION 1: INVOICE OVERVIEW (CRM VIEW)
# ---------------------------------------------------
st.title("CRM Invoice Overview")

if df_filtered.empty:
    st.warning("No data for current filter selection.")
else:
    # เลือก column สำหรับแสดงภาพรวม CRM
    overview_cols = [
        "Customer",
        "Sale order No.",
        "Invoice value",
        "Invoice Issued Date",
        "Expected Payment date",
        "Payment Status",
        "days_to_expected",
        "is_overdue",
    ]

    display_df = df_filtered[overview_cols].copy()

    # แปลงชื่อ column ให้คนอ่านเข้าใจง่าย
    display_df = display_df.rename(columns={
        "Sale order No.": "Sale Order No.",
        "Invoice value": "Invoice Value",
        "Invoice Issued Date": "Invoice Issued Date",
        "Expected Payment date": "Expected Payment Date",
        "days_to_expected": "Days to Expected Payment",
        "is_overdue": "Overdue?",
    })

    # สร้างคำอธิบายข้อความ เช่น "Due in 5 days" / "Overdue by 3 days"
    def describe_due(days):
        if pd.isna(days):
            return ""
        days = int(days)
        if days > 0:
            return f"Due in {days} days"
        elif days == 0:
            return "Due today"
        else:
            return f"Overdue by {-days} days"

    display_df["Due Status"] = display_df["Days to Expected Payment"].apply(describe_due)

    # จัด format ตัวเลข Invoice Value ให้มี comma
    format_dict = {
        "Invoice Value": "{:,.0f}".format,
        "Days to Expected Payment": "{:+d}".format,  # ให้เห็น +/- วัน
    }

    # สร้าง style ให้แถวที่ overdue เป็นสีแดง
    def highlight_overdue(row):
        if row["Overdue?"]:
            return ["color: red; font-weight: bold"] * len(row)
        else:
            return [""] * len(row)

    styled = display_df.style.format(format_dict, na_rep="").apply(
        highlight_overdue, axis=1
    )

    st.subheader("Invoice list by Customer")
    st.caption(
        "สีแดง = วันนี้เกิน Expected Payment Date แล้ว (เกินเครดิตเทอม) | "
        "Days to Expected Payment เป็นจำนวนวันจากวันนี้ถึงวันที่คาดว่าจะได้รับเงิน"
    )
    st.dataframe(styled, use_container_width=True)

# ---------------------------------------------------
# SECTION 2: CUSTOMER PAYMENT BEHAVIOR (FAST vs SLOW)
# ---------------------------------------------------
st.markdown("---")
st.header("Customer Payment Behavior (Fast vs Slow Payers)")

# ใช้ข้อมูลเฉพาะ invoice ที่จ่ายแล้ว + มี Expected & Actual Payment
df_behavior = df[
    df["is_paid"]
    & df["Expected Payment date"].notna()
    & df["Actual Payment received date"].notna()
].copy()

if df_behavior.empty:
    st.info("No paid invoices with Expected & Actual payment dates to analyze.")
else:
    # ถ้าบาง invoice ยังไม่ได้คำนวณ days_diff_actual_expected ให้ทำซ้ำอีกครั้ง (กันพลาด)
    df_behavior["days_diff_actual_expected"] = (
        df_behavior["Actual Payment received date"] - df_behavior["Expected Payment date"]
    ).dt.days

    # คำนวณเฉลี่ยต่อลูกค้า
    behavior = (
        df_behavior.groupby("Customer")["days_diff_actual_expected"]
        .mean()
        .reset_index()
        .rename(columns={"days_diff_actual_expected": "avg_days_diff"})
    )

    # ยิ่ง avg_days_diff น้อย (ติดลบมาก) = จ่ายเร็ว
    best = behavior.sort_values("avg_days_diff").head(10)
    worst = behavior.sort_values("avg_days_diff", ascending=False).head(10)

    # แปลงคำอธิบาย
    def describe_behavior(d):
        if pd.isna(d):
            return ""
        d = float(d)
        if d < 0:
            return f"Pays {abs(d):.1f} days earlier on average"
        elif d == 0:
            return "Pays on time"
        else:
            return f"Pays {d:.1f} days late on average"

    best["Behavior"] = best["avg_days_diff"].apply(describe_behavior)
    worst["Behavior"] = worst["avg_days_diff"].apply(describe_behavior)

    b1, b2 = st.columns(2)

    with b1:
        st.subheader("⭐ Top Fast Payers")
        st.caption("ลูกค้าที่จ่ายเร็วกว่าคาด (ค่าติดลบมาก = ดี)")
        st.dataframe(
            best.rename(columns={"avg_days_diff": "Avg days (Actual - Expected)"}),
            use_container_width=True,
        )

    with b2:
        st.subheader("⚠️ Top Slow Payers")
        st.caption("ลูกค้าที่จ่ายช้ากว่าคาด (ค่าสูงกว่า 0 = เสี่ยง)")
        st.dataframe(
            worst.rename(columns={"avg_days_diff": "Avg days (Actual - Expected)"}),
            use_container_width=True,
        )
