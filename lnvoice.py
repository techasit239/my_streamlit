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
    DATA_URL = (
        "https://raw.githubusercontent.com/techasit239/my_streamlit/"
        "refs/heads/main/BI%20Project%20status_Prototype-%20Invoice.csv"
    )

    df = pd.read_csv(DATA_URL)

    # 1) Project year
    df["project_year"] = pd.to_numeric(df["Project year"], errors="coerce")

    # 2) base invoice_date
    df["invoice_date"] = pd.to_datetime(
        df["Invoice plan date"], errors="coerce", infer_datetime_format=True
    )
    mask_missing = df["invoice_date"].isna()
    if mask_missing.any():
        df.loc[mask_missing, "invoice_date"] = pd.to_datetime(
            df.loc[mask_missing, "Issued Date"],
            errors="coerce",
            infer_datetime_format=True
        )

    # 2.1) convert all date fields weใช้ภายหลัง
    date_cols = [
        "Invoice plan date",
        "Issued Date",
        "Invoice due date",
        "Plan payment date",
        "Expected Payment date",
        "Actual Payment received date",
    ]
    for c in date_cols:
        df[c] = pd.to_datetime(df[c], errors="coerce", infer_datetime_format=True)

    # 3) money
    money_cols = [" Total amount ", " Invoice value ", "Claim Plan 2025"]
    for c in money_cols:
        df[c + "_num"] = (
            df[c]
            .astype(str)
            .str.replace(",", "", regex=False)
            .str.replace("-", "0", regex=False)
        )
        df[c + "_num"] = pd.to_numeric(df[c + "_num"], errors="coerce").fillna(0.0)

    df["invoice_amount"] = df[" Invoice value _num"]
    df["total_amount"] = df[" Total amount _num"]
    df["claim_plan_2025"] = df["Claim Plan 2025_num"]

    # 4) receipt & outstanding
    df["Payment Status_clean"] = df["Payment Status"].astype(str).str.strip().str.lower()
    df["receipt_amount"] = np.where(
        df["Payment Status_clean"] == "paid",
        df["invoice_amount"],
        0.0,
    )
    df["outstanding_amount"] = df["invoice_amount"] - df["receipt_amount"]

    # 5) time dims
    df["invoice_year"] = df["invoice_date"].dt.year
    df["invoice_quarter"] = "Qtr " + df["invoice_date"].dt.quarter.astype("Int64").astype(str)
    df["invoice_month_name"] = df["invoice_date"].dt.month_name()
    df["invoice_year_month"] = df["invoice_date"].dt.to_period("M").astype(str)

    return df


df = load_data()

# ---------------------------------------------------
# SIDEBAR FILTERS
# ---------------------------------------------------
st.sidebar.header("Filters")

years = sorted([int(y) for y in df["project_year"].dropna().unique()])
default_year = 2025 if 2025 in years else years[-1]
year_selected = st.sidebar.radio(
    "Project year analysis",
    years,
    index=years.index(default_year)
)

df_filtered = df[df["project_year"] == year_selected].copy()

quarter_opts = ["--"] + sorted(df_filtered["invoice_quarter"].dropna().unique())
quarter_selected = st.sidebar.selectbox("Quarter", quarter_opts, index=0)
if quarter_selected != "--":
    df_filtered = df_filtered[df_filtered["invoice_quarter"] == quarter_selected]

month_opts = ["--"] + list(df_filtered["invoice_month_name"].dropna().unique())
month_selected = st.sidebar.selectbox("Month", month_opts, index=0)
if month_selected != "--":
    df_filtered = df_filtered[df_filtered["invoice_month_name"] == month_selected]

customers = ["All"] + sorted(df_filtered["Customer"].dropna().unique())
customer_selected = st.sidebar.selectbox("Analysis by Customer", customers, index=0)
if customer_selected != "All":
    df_filtered = df_filtered[df_filtered["Customer"] == customer_selected]

aging_all = sorted(df["Payment Status"].dropna().unique())
aging_selected = st.sidebar.multiselect(
    "Payment Status (Aging)",
    aging_all,
    default=aging_all
)
if aging_selected:
    df_filtered = df_filtered[df_filtered["Payment Status"].isin(aging_selected)]

# ---------------------------------------------------
# TOP KPIs
# ---------------------------------------------------
def fmt_million(x: float) -> str:
    return f"{x/1_000_000:,.1f} M"

st.markdown("## Invoice & Receipt Dashboard")

if df_filtered.empty:
    st.warning("No data for current filter selection.")
else:
    total_invoice = float(df_filtered["invoice_amount"].sum())
    total_receipt = float(df_filtered["receipt_amount"].sum())
    outstanding = float(df_filtered["outstanding_amount"].sum())

    k1, k2, k3 = st.columns(3)
    with k1:
        st.markdown("**Sum of Total invoice billing**")
        st.markdown(
            f"<h1 style='color:#C00000; font-size: 36px;'>{fmt_million(total_invoice)}</h1>",
            unsafe_allow_html=True,
        )
    with k2:
        st.markdown("**Total receipt**")
        st.markdown(
            f"<h1 style='color:#C00000; font-size: 36px;'>{fmt_million(total_receipt)}</h1>",
            unsafe_allow_html=True,
        )
    with k3:
        st.markdown("**Outstanding balance**")
        st.markdown(
            f"<h1 style='color:#C00000; font-size: 36px;'>{fmt_million(outstanding)}</h1>",
            unsafe_allow_html=True,
        )

st.markdown("---")

# ---------------------------------------------------
# MAIN CHARTS (แสดงต่อให้ df_filtered ว่างก็เช็กก่อน)
# ---------------------------------------------------
left_col, right_col = st.columns([1, 2])

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
        x=alt.X(
            "outstanding_amount:Q",
            title="Outstanding balance",
            axis=alt.Axis(format=",.0f"),
        ),
        y=alt.Y("Customer:N", sort="-x", title="Customer"),
        tooltip=[
            alt.Tooltip("Customer:N", title="Customer"),
            alt.Tooltip("outstanding_amount:Q", title="Outstanding", format=",.0f"),
        ],
    )
    .properties(height=320)
)


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
        month_group["acc_receipt"] = month_group["total_receipt"].cumsum()

        base = alt.Chart(month_group).encode(
            x=alt.X("invoice_year_month:N", title="Month")
        )
        bar_invoice = base.mark_bar(color="#4472C4").encode(
    y=alt.Y("total_invoice:Q", title="Amount", axis=alt.Axis(format=",.0f")),
    tooltip=[
        alt.Tooltip("invoice_year_month:N", title="Month"),
        alt.Tooltip("total_invoice:Q", title="Total invoice", format=",.0f"),
        alt.Tooltip("total_outstanding:Q", title="Outstanding", format=",.0f"),
        alt.Tooltip("total_receipt:Q", title="Total receipt", format=",.0f"),
        alt.Tooltip("acc_receipt:Q", title="Acc. receipt", format=",.0f"),
    ],
)
        bar_receipt = base.mark_bar(color="#ED7D31", opacity=0.8).encode(
            y="total_receipt:Q"
        )
        line_acc = base.mark_line(color="#A020F0", point=True).encode(
            y="acc_receipt:Q"
        )
        combo = (bar_invoice + bar_receipt + line_acc).properties(height=380)
        st.altair_chart(combo, use_container_width=True)

st.markdown("---")

# ---------------------------------------------------
# DETAIL TABLE
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

# ---------------------------------------------------
# SECTION A: Delay Analysis
# ---------------------------------------------------
st.markdown("## ⏱️ Delay Analysis")
if df_filtered.empty:
    st.info("No data for Delay Analysis.")
else:
    df_delay = df_filtered.copy()
    df_delay["days_late"] = (
        df_delay["Actual Payment received date"] - df_delay["Plan payment date"]
    ).dt.days

    df_delay["delay_status"] = np.where(
        df_delay["days_late"] > 0, "Late", "On-time"
    )

    percent_late = (df_delay["delay_status"].eq("Late").mean()) * 100
    avg_days_late = df_delay["days_late"].clip(lower=0).mean()

    c1, c2 = st.columns(2)
    c1.metric("Percentage Late Payment", f"{percent_late:.1f}%")
    c2.metric("Average Days Late", f"{avg_days_late:.1f} days")

    delay_counts = df_delay["delay_status"].value_counts().reset_index()
    delay_counts.columns = ["status", "count"]

    donut_chart = (
        alt.Chart(delay_counts)
        .mark_arc(innerRadius=60)
        .encode(
            theta="count:Q",
            color="status:N",
            tooltip=["status", "count"]
        )
    )
    st.altair_chart(donut_chart, use_container_width=True)

    st.markdown("#### Delay Summary Table")
    st.dataframe(
        df_delay[[
            "Customer",
            "invoice_amount",
            "Payment Status",
            "days_late",
            "delay_status"
        ]].sort_values("days_late", ascending=False),
        use_container_width=True
    )

# ---------------------------------------------------
# SECTION B: Customer Payment Behavior Ranking
# ---------------------------------------------------
st.markdown("## 🏆 Customer Payment Behavior Ranking")
if df_filtered.empty:
    st.info("No data for Customer Ranking.")
else:
    df_rank = df_filtered.copy()
    df_rank["days_late"] = (
        df_rank["Actual Payment received date"] - df_rank["Plan payment date"]
    ).dt.days

    behavior = (
        df_rank.groupby("Customer")["days_late"]
        .mean()
        .reset_index()
        .fillna(0)
    )

    best = behavior.sort_values("days_late").head(5)
    worst = behavior.sort_values("days_late", ascending=False).head(5)

    b1, b2 = st.columns(2)
    with b1:
        st.markdown("### ⭐ Top 5 Best Customers (Pay On-time)")
        st.dataframe(best, use_container_width=True)
    with b2:
        st.markdown("### ⚠️ Top 5 Worst Customers (Pay the Latest)")
        st.dataframe(worst, use_container_width=True)

# ---------------------------------------------------
# SECTION C: Cashflow Forecast
# ---------------------------------------------------
st.markdown("## 📈 Cashflow Forecast (Plan vs Actual)")
if df_filtered.empty:
    st.info("No data for Cashflow Forecast.")
else:
    df_cf = df_filtered.copy()
    df_cf["plan_month"] = df_cf["Plan payment date"].dt.to_period("M").astype(str)
    df_cf["actual_month"] = df_cf["Actual Payment received date"].dt.to_period("M").astype(str)

    plan = (
        df_cf.groupby("plan_month")["claim_plan_2025"]
        .sum()
        .reset_index()
        .rename(columns={"claim_plan_2025": "plan_amount"})
    )
    actual = (
        df_cf.groupby("actual_month")["receipt_amount"]
        .sum()
        .reset_index()
        .rename(columns={"receipt_amount": "actual_amount"})
    )
    merged = pd.merge(plan, actual, left_on="plan_month", right_on="actual_month", how="outer")
    merged["month"] = merged["plan_month"].fillna(merged["actual_month"])

    chart_cf = (
        alt.Chart(merged)
        .mark_line(point=True)
        .encode(
            x=alt.X("month:N", title="Month"),
            y=alt.Y("plan_amount:Q", title="Amount"),
        )
        +
        alt.Chart(merged)
        .mark_line(point=True, color="#ED7D31")
        .encode(
            x="month:N",
            y="actual_amount:Q",
            tooltip=["month", "actual_amount"]
        )
    ).properties(height=400)

    st.altair_chart(chart_cf, use_container_width=True)

# ---------------------------------------------------
# SECTION D: Calendar Heatmap
# ---------------------------------------------------
st.markdown("## 📅 Calendar Heatmap (Invoice Frequency)")
if df_filtered.empty:
    st.info("No data for Calendar Heatmap.")
else:
    df_cal = df_filtered.copy()
    df_cal["date_only"] = df_cal["invoice_date"].dt.date

    calendar = (
        df_cal.groupby("date_only")["invoice_amount"]
        .sum()
        .reset_index()
    )
    calendar["weekday"] = pd.to_datetime(calendar["date_only"]).dt.weekday
    calendar["week"] = pd.to_datetime(calendar["date_only"]).dt.isocalendar().week

    heatmap = (
        alt.Chart(calendar)
        .mark_rect()
        .encode(
            x=alt.X("weekday:O", title="Day of Week"),
            y=alt.Y("week:O", title="Week Number"),
            color=alt.Color("invoice_amount:Q", title="Invoice Amount"),
            tooltip=["date_only", "invoice_amount"]
        )
        .properties(height=350)
    )
    st.altair_chart(heatmap, use_container_width=True)

