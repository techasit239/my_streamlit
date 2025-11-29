import streamlit as st
import pandas as pd
import numpy as np
import altair as alt

# ---------------------------------------------------
# PAGE CONFIG
# ---------------------------------------------------
st.set_page_config(
    page_title="Invoice & Receipt Dashboard",
    layout="wide"
)

# ---------------------------------------------------
# LOAD & CLEAN DATA
# ---------------------------------------------------
@st.cache_data
def load_data():
    # อ่านไฟล์จากโฟลเดอร์เดียวกับ app.py
    df = pd.read_csv("BI Project status_Prototype- Invoice.csv")

    # ---- แปลงปีโครงการให้เป็นตัวเลข ----
    df["project_year"] = pd.to_numeric(df["Project year"], errors="coerce")

    # ---- แปลงวันที่หลักที่ใช้ทำกราฟ (ใช้ Invoice plan date เป็นแกนเวลา) ----
    df["invoice_date"] = pd.to_datetime(
        df["Invoice plan date"], errors="coerce", dayfirst=False, infer_datetime_format=True
    )

    # ถ้า invoice_date ว่างเยอะ จะ fallback ไปใช้ Issued Date
    mask_missing = df["invoice_date"].isna()
    if mask_missing.any():
        df.loc[mask_missing, "invoice_date"] = pd.to_datetime(
            df.loc[mask_missing, "Issued Date"],
            errors="coerce",
            dayfirst=False,
            infer_datetime_format=True
        )

    # ---- แปลงจำนวนเงินให้เป็นตัวเลข ----
    money_cols = [" Total amount ", " Invoice value ", "Claim Plan 2025"]
    for c in money_cols:
        df[c + "_num"] = (
            df[c]
            .astype(str)
            .str.replace(",", "", regex=False)
            .str.replace("-", "0", regex=False)
        )
        df[c + "_num"] = pd.to_numeric(df[c + "_num"], errors="coerce").fillna(0.0)

    # สร้างชื่อสั้น ๆ
    df["invoice_amount"] = df[" Invoice value _num"]
    df["claim_plan_2025"] = df["Claim Plan 2025_num"]

    # ---- กำหนดรับชำระ: สมมติว่า Paid = รับชำระครบ, สถานะอื่นยังไม่รับ ----
    df["receipt_amount"] = np.where(
        df["Payment Status"].astype(str).str.strip().str.lower() == "paid",
        df["invoice_amount"],
        0.0,
    )

    # ---- ยอดค้างชำระ ----
    df["outstanding_amount"] = df["invoice_amount"] - df["receipt_amount"]

    # ---- Dimension ปี / ไตรมาส / เดือน จาก invoice_date ----
    df["invoice_year"] = df["invoice_date"].dt.year
    df["invoice_quarter"] = "Qtr " + df["invoice_date"].dt.quarter.astype("Int64").astype(str)
    df["invoice_month_name"] = df["invoice_date"].dt.month_name()
    df["invoice_year_month"] = df["invoice_date"].dt.to_period("M").astype(str)

    return df


df = load_data()

# ---------------------------------------------------
# FILTER ZONE (ด้านล่างซ้ายของภาพ: Project year / Quarter / Month)
# ---------------------------------------------------
st.sidebar.header("Filters")

# ปีโครงการ (ใช้คอลัมน์ project_year จากไฟล์)
years = sorted([y for y in df["project_year"].dropna().unique()])
default_year = 2025 if 2025 in years else years[-1]  # ถ้ามีปี 2025 ให้เลือกเป็นค่าเริ่มต้น
year_selected = st.sidebar.radio("Project year analysis", years, index=years.index(default_year))

# Filter ตามปีโครงการ
df_filtered = df[df["project_year"] == year_selected].copy()

# Quarter
quarter_opts = ["--"] + sorted(df_filtered["invoice_quarter"].dropna().unique())
quarter_selected = st.sidebar.selectbox("Quarter", quarter_opts, index=0)

if quarter_selected != "--":
    df_filtered = df_filtered[df_filtered["invoice_quarter"] == quarter_selected]

# Month
month_opts = ["--"] + list(df_filtered["invoice_month_name"].dropna().unique())
month_selected = st.sidebar.selectbox("Month", month_opts, index=0)

if month_selected != "--":
    df_filtered = df_filtered[df_filtered["invoice_month_name"] == month_selected]

# Analysis by Customer (dropdown เหมือนในรูป)
customers = ["All"] + sorted(df_filtered["Customer"].dropna().unique())
customer_selected = st.sidebar.selectbox("Analysis by Customer", customers, index=0)

if customer_selected != "All":
    df_filtered = df_filtered[df_filtered["Customer"] == customer_selected]

# Aging checkbox ด้านขวา (ใช้ Payment Status)
aging_all = sorted(df["Payment Status"].dropna().unique())
aging_selected = st.sidebar.multiselect(
    "Aging (Payment Status)",
    aging_all,
    default=aging_all,   # เปิดทุกค่าไว้ก่อนเหมือนในภาพ
)
if aging_selected:
    df_filtered = df_filtered[df_filtered["Payment Status"].isin(aging_selected)]

# ---------------------------------------------------
# TOP KPI (3 กล่องบนสุด)
# ---------------------------------------------------
def fmt_million(x: float) -> str:
    return f"{x/1_000_000:,.1f} M"

st.markdown("### Project Billing Dashboard")

total_invoice = float(df_filtered["invoice_amount"].sum())
total_receipt = float(df_filtered["receipt_amount"].sum())
outstanding = float(df_filtered["outstanding_amount"].sum())

k1, k2, k3 = st.columns(3)

with k1:
    st.markdown("**Sum of Total invoice billing**")
    st.markdown(
        f"<h1 style='color:red; font-size: 40px;'>{fmt_million(total_invoice)}</h1>",
        unsafe_allow_html=True,
    )

with k2:
    st.markdown("**Total receipt**")
    st.markdown(
        f"<h1 style='color:red; font-size: 40px;'>{fmt_million(total_receipt)}</h1>",
        unsafe_allow_html=True,
    )

with k3:
    st.markdown("**Outstanding balance**")
    st.markdown(
        f"<h1 style='color:red; font-size: 40px;'>{fmt_million(outstanding)}</h1>",
        unsafe_allow_html=True,
    )

st.markdown("---")

# ---------------------------------------------------
# MID LAYOUT: LEFT = bar by customer, RIGHT = combo chart month
# ---------------------------------------------------
left_col, right_col = st.columns([1, 2])

# ---------- LEFT: Outstanding balance by Customer ----------
with left_col:
    st.markdown("#### Outstanding balance by Customer")

    if df_filtered.empty:
        st.info("No data for current filters.")
    else:
        cust_group = (
            df_filtered.groupby("Customer", as_index=False)["outstanding_amount"]
            .sum()
            .sort_values("outstanding_amount", ascending=True)
        )

        # slider ช่วงยอดค้างเหมือนในภาพ (optional แต่ใส่ให้คล้าย)
        min_val = float(cust_group["outstanding_amount"].min())
        max_val = float(cust_group["outstanding_amount"].max())
        if min_val == max_val:
            range_selected = (min_val, max_val)
        else:
            range_selected = st.slider(
                "Outstanding balance range",
                min_value=min_val,
                max_value=max_val,
                value=(min_val, max_val),
            )
            cust_group = cust_group[
                cust_group["outstanding_amount"].between(range_selected[0], range_selected[1])
            ]

        bar = (
            alt.Chart(cust_group)
            .mark_bar()
            .encode(
                x=alt.X("outstanding_amount:Q", title="Outstanding balance"),
                y=alt.Y("Customer:N", sort="-x", title="Customer"),
                tooltip=["Customer", "outstanding_amount"],
            )
            .properties(height=320)
        )

        st.altair_chart(bar, use_container_width=True)

# ---------- RIGHT: Combo chart (invoice, outstanding, receipt, accumulated receipt) ----------
with right_col:
    st.markdown(
        "#### Sum of Total invoice billing, Outstanding balance, "
        "Total receipt & Accumulated total receipt by Month"
    )

    if df_filtered.empty:
        st.info("No data for current filters.")
    else:
        month_group = (
            df_filtered.groupby("invoice_year_month", as_index=False)
            .agg(
                total_invoice=("invoice_amount", "sum"),
                total_receipt=("receipt_amount", "sum"),
                total_outstanding=("outstanding_amount", "sum"),
            )
            .sort_values("invoice_year_month")
        )

        # ยอดสะสม receipt
        month_group["acc_receipt"] = month_group["total_receipt"].cumsum()

        base = alt.Chart(month_group).encode(
            x=alt.X("invoice_year_month:N", title="Month")
        )

        bar_invoice = base.mark_bar(color="#1f77b4").encode(
            y=alt.Y("total_invoice:Q", title="Amount"),
            tooltip=[
                "invoice_year_month",
                "total_invoice",
                "total_outstanding",
                "total_receipt",
                "acc_receipt",
            ],
        )

        bar_receipt = base.mark_bar(color="#ff7f0e", opacity=0.7).encode(
            y="total_receipt:Q"
        )

        line_acc = base.mark_line(color="purple", point=True).encode(
            y="acc_receipt:Q"
        )

        combo = (bar_invoice + bar_receipt + line_acc).properties(height=380)

        st.altair_chart(combo, use_container_width=True)

st.markdown("---")

# ---------------------------------------------------
# OPTIONAL: ตารางรายละเอียดด้านล่าง
# ---------------------------------------------------
st.markdown("#### Detail table")

if df_filtered.empty:
    st.info("No data for current filters.")
else:
    st.dataframe(
        df_filtered[
            [
                "invoice_date",
                "project_year",
                "Customer",
                "invoice_amount",
                "receipt_amount",
                "outstanding_amount",
                "Payment Status",
            ]
        ].sort_values("invoice_date"),
        use_container_width=True,
    )
