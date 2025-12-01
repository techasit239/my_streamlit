from pathlib import Path
from typing import Any, Dict, Generator, List, Tuple
import os

import pandas as pd
import streamlit as st
from ollama import chat
from openai import OpenAI
from streamlit_gsheets import GSheetsConnection
import os
from pathlib import Path
from typing import Optional

def load_env_key(key: str, env_path: Path = Path(".env")) -> Optional[str]:
    if key in os.environ:
        return os.environ[key]
    if not env_path.exists():
        return None
    for line in env_path.read_text().splitlines():
        if not line or line.strip().startswith("#") or "=" not in line:
            continue
        k, v = line.split("=", 1)
        if k.strip() == key:
            return v.strip().strip('"').strip("'")
    return None



from add_record_form import render_invoice_form, render_project_form
try:
    from pypdf import PdfReader
except Exception:
    PdfReader = None

st.set_page_config(page_title="AI Assistant (Project & Invoice)", page_icon="🤖", layout="wide")

PROJECT_WORKFLOW = (
    "Project workflow sequence: "
    "1) Prepare document Focus, 2) Procurement Focus, 3) Fabrication Focus, "
    "4) Final inspection, 5) Shipping, 6) Final Document (no delay considered), "
    "7) Completed (no delay considered)."
)

OPENROUTER_API_KEY = load_env_key("OPENROUTER_API_KEY")
grok_client = None
if OPENROUTER_API_KEY:
    try:
        grok_client = OpenAI(base_url="https://openrouter.ai/api/v1", api_key=OPENROUTER_API_KEY)
    except Exception:
        grok_client = None

# -----------------------------
# Data loading (same sources as dashboards)
# -----------------------------
@st.cache_data(ttl=300, show_spinner=False)
def load_project_invoice() -> Tuple[pd.DataFrame, pd.DataFrame, Dict[str, str]]:
    """Load project/invoice data; prefer Google Sheets, fallback to local Excel."""
    gsheets_error = None
    meta: Dict[str, str] = {}

    def resolve_excel_path() -> Path:
        relative = Path(__file__).resolve().parent.parent / "BI Project status_Prototype-2.xlsx"
        absolute = Path(
            "/Users/sashimild/Desktop/Nguk/NIDA MASTER DEGREE/5001/DADS5001-6720422009/BI Project status_Prototype-2.xlsx"
        )
        if not relative.exists() and absolute.exists():
            return absolute
        return relative

    excel_path = resolve_excel_path()
    if not excel_path.exists():
        raise RuntimeError("Invoice/Project source Excel file is missing.")

    # Try Google Sheets for project
    try:
        conn = st.connection("gsheets", type=GSheetsConnection)
        project_raw = conn.read(worksheet="Project", ttl="5m")
        if project_raw is None or project_raw.empty:
            raise ValueError("Google Sheets returned no rows for 'Project'.")
        project_df = clean_project(project_raw)
        meta["project_source"] = "gsheets"
    except Exception as exc:  # noqa: BLE001
        gsheets_error = exc
        workbook = pd.ExcelFile(excel_path)
        project_sheet = "Project" if "Project" in workbook.sheet_names else workbook.sheet_names[0]
        project_df = clean_project(workbook.parse(project_sheet))
        meta["project_source"] = "excel"
        meta["project_error"] = str(gsheets_error)

    # Invoice always from Excel (per previous requirement)
    try:
        workbook = pd.ExcelFile(excel_path)
    except Exception as exc:  # noqa: BLE001
        raise RuntimeError(f"Unable to read Excel file for invoice: {excel_path}") from exc
    invoice_sheet = "Invoice" if "Invoice" in workbook.sheet_names else workbook.sheet_names[0]
    invoice_df = clean_invoice(workbook.parse(invoice_sheet))
    meta["invoice_source"] = "excel"
    meta["excel_path"] = str(excel_path)

    return project_df, invoice_df, meta


def clean_project(df: pd.DataFrame) -> pd.DataFrame:
    df = df.copy()
    df.columns = [str(c).strip() for c in df.columns]
    df.rename(columns={"Q'ty": "Qty"}, inplace=True)
    df = df.dropna(how="all")

    date_cols = [
        "PO Date",
        "Original Delivery Date",
        "Estimated shipdate",
        "Actual shipdate",
        "Waranty end",
    ]
    numeric_cols = [
        "Project year",
        "Order number",
        "Project Value",
        "Balance",
        "Progress",
        "Number of Status",
        "Max LD",
        "Max LD Amount",
        "Extra cost",
        "Change order amount",
        "Storage fee amount",
        "Days late",
        "Qty",
    ]
    for col in date_cols:
        if col in df.columns:
            df[col] = pd.to_datetime(df[col], errors="coerce")
    for col in numeric_cols:
        if col in df.columns:
            df[col] = pd.to_numeric(df[col], errors="coerce")
    if "Progress" in df.columns:
        df["Progress"] = df["Progress"].clip(lower=0, upper=1)
    return df


def clean_invoice(df: pd.DataFrame) -> pd.DataFrame:
    df = df.copy()
    df.columns = [str(c).strip() for c in df.columns]
    df.rename(columns={"Currency unit ": "Currency unit"}, inplace=True)
    df = df.dropna(how="all")
    numeric_cols = [
        "Project year",
        "SEQ",
        "Total amount",
        "Percentage of amount",
        "Invoice value",
        "Plan Delayed",
        "Actual Delayed",
        "Claim Plan 2025",
    ]
    for col in numeric_cols:
        if col in df.columns:
            df[col] = pd.to_numeric(df[col], errors="coerce")
    date_cols = [
        "Invoice plan date",
        "Issued Date",
        "Invoice due date",
        "Plan payment date",
        "Expected Payment date",
        "Actual Payment received date",
    ]
    for col in date_cols:
        if col in df.columns:
            df[col] = pd.to_datetime(df[col], errors="coerce")
    return df


@st.cache_data(ttl=1800, show_spinner=False)
def load_pmbok_chunks() -> List[str]:
    """Load PMBOK PDF and split into small chunks for retrieval; return empty if unavailable."""
    pdf_path = Path(__file__).resolve().parent.parent / "PMBOK 7th Edition.pdf"
    if not pdf_path.exists() or PdfReader is None:
        return []
    try:
        reader = PdfReader(str(pdf_path))
        pages_text: List[str] = []
        for page in reader.pages:
            text = page.extract_text() or ""
            if text:
                pages_text.append(text)
        full_text = "\n".join(pages_text)
        chunks: List[str] = []
        chunk_size = 1200
        for i in range(0, len(full_text), chunk_size):
            chunk = full_text[i : i + chunk_size].strip()
            if chunk:
                chunks.append(chunk)
        return chunks
    except Exception:
        return []


# -----------------------------
# Simple RAG helpers
# -----------------------------
def row_to_snippet(row: pd.Series, kind: str) -> str:
    if kind == "project":
        parts = [
            f"Project: {row.get('Project', '')}",
            f"Customer: {row.get('Customer', '')}",
            f"Engineer: {row.get('Project Engineer', '')}",
            f"Order: {row.get('Order number', '')}",
            f"Status: {row.get('Status', '')}",
            f"Progress: {row.get('Progress', 0):.0%}" if pd.notna(row.get("Progress")) else "Progress: n/a",
            f"Value: {row.get('Project Value', '')}",
            f"Balance: {row.get('Balance', '')}",
            f"Phrase: {row.get('Project Phrase', '')}",
        ]
    else:
        parts = [
            f"Customer: {row.get('Customer', '')}",
            f"Engineer: {row.get('Project Engineer', '')}",
            f"Order: {row.get('Sale order No.', '')}",
            f"Invoice value: {row.get('Invoice value', '')}",
            f"Payment status: {row.get('Payment Status', '')}",
            f"Plan date: {row.get('Invoice plan date', '')}",
            f"Issued: {row.get('Issued Date', '')}",
        ]
    return " | ".join(str(p) for p in parts if p)


def build_corpus(
    project_df: pd.DataFrame,
    invoice_df: pd.DataFrame,
    domain: str,
    include_pmbok: bool,
    pmbok_chunks: List[str],
    include_workflow: bool = True,
    limit: int = 200,
):
    docs = []
    if domain in {"project", "both"}:
        sample = project_df.head(limit)
        for _, row in sample.iterrows():
            docs.append({"source": "project", "text": row_to_snippet(row, "project")})
    if domain in {"invoice", "both"}:
        sample = invoice_df.head(limit)
        for _, row in sample.iterrows():
            docs.append({"source": "invoice", "text": row_to_snippet(row, "invoice")})
    if include_pmbok and pmbok_chunks:
        for chunk in pmbok_chunks[:50]:  # cap chunks for efficiency
            docs.append({"source": "pmbok", "text": chunk})
    if include_workflow:
        docs.append({"source": "workflow", "text": PROJECT_WORKFLOW})
    return docs


def rank_docs(query: str, docs: List[Dict[str, str]], top_k: int = 10):
    # Simple keyword overlap score
    tokens = set(query.lower().split())
    scored = []
    for doc in docs:
        words = set(doc["text"].lower().split())
        score = len(tokens & words)
        scored.append((score, doc))
    scored.sort(key=lambda x: x[0], reverse=True)
    # Always keep at least one PMBOK chunk if available and nothing matches
    top = [doc for score, doc in scored[:top_k] if score > 0]
    if not top:
        top = [doc for _, doc in scored[: max(1, top_k // 3)]]  # fallback few docs
    return top


def call_model_stream(question: str, context: List[Dict[str, str]], model_choice: str) -> Generator[str, None, None]:
    ctx_block = "\n".join([f"- ({d['source']}) {d['text']}" for d in context])
    system_prompt = (
        "You are an expert in project management (PMP/PMBOK) and an assistant for project/invoice data. "
        "Ground answers in the provided context and PMBOK best practices: prioritize project value, timelines, risk, and invoice status. "
        f"Always consider this project workflow: {PROJECT_WORKFLOW} "
        "Answer with enough detail (3-5 sentences) using only the provided context; include key numbers/status when available. "
        "If unsure, say you do not have that information. "
        "ตอบเป็นภาษาไทยถ้าคำถามเป็นภาษาไทย และตอบเป็นอังกฤษถ้าคำถามเป็นอังกฤษ."
    )
    user_prompt = f"Context:\n{ctx_block}\n\nQuestion: {question}"

    if model_choice == "grok":
        if grok_client is None:
            raise RuntimeError("Grok client unavailable: set OPENROUTER_API_KEY in .env")
        stream = grok_client.chat.completions.create(
            model="x-ai/grok-4.1-fast:free",
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
            extra_body={"reasoning": {"enabled": True}},
            stream=True,
        )
        for chunk in stream:
            delta = chunk.choices[0].delta.content if chunk.choices else None
            if delta:
                yield delta
    else:
        for chunk in chat(
            model="gemma3",
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
            stream=True,
        ):
            yield chunk.get("message", {}).get("content") if isinstance(chunk, dict) else ""


# -----------------------------
# UI
# -----------------------------
st.title("AI Assistant for Project & Invoice")
st.caption("ถาม-ตอบเกี่ยวกับโครงการ/ใบแจ้งหนี้ ระบบจะค้นหาบริบท (RAG) และสตรีมคำตอบแบบละเอียด")

nav_cols = st.columns(3)
with nav_cols[0]:
    st.page_link("pages/project.py", label="📊 Project dashboard")
with nav_cols[1]:
    st.page_link("pages/Invoice.py", label="🧾 Invoice dashboard")
with nav_cols[2]:
    with st.popover("➕ Add project record", use_container_width=True):
        render_project_form(form_key="ai_add_project_form")
    with st.popover("➕ Add invoice record", use_container_width=True):
        render_invoice_form(form_key="ai_add_invoice_form")

try:
    project_df, invoice_df, meta = load_project_invoice()
    pmbok_chunks = load_pmbok_chunks()
    st.success(
        f"Data ready (Project: {meta.get('project_source','?')}, Invoice: {meta.get('invoice_source','?')}, PMBOK chunks: {len(pmbok_chunks)})",
        icon="✅",
    )
except Exception as exc:  # noqa: BLE001
    st.error(f"โหลดข้อมูลไม่สำเร็จ: {exc}", icon="🚫")
    st.stop()

model_choice = st.selectbox(
    "Model",
    ["ollama_gemma3", "grok_openrouter"],
    format_func=lambda v: "Grok (OpenRouter)" if v == "grok_openrouter" else "Ollama gemma3 (local)",
    help="เลือกโมเดล: Grok ใช้ API key จาก OPENROUTER_API_KEY ใน .env, ส่วน Ollama ใช้โมเดล gemma3 ในเครื่อง",
)
domain = st.radio("แหล่งข้อมูลที่ใช้ประกอบคำตอบ", ["both", "project", "invoice"], horizontal=True, index=0,
                  format_func=lambda x: {"both": "Project + Invoice", "project": "Project only", "invoice": "Invoice only"}[x])
pmbok_use = st.checkbox("ใช้ความรู้จาก PMBOK (PDF) ประกอบ", value=True if 'pmbok_chunks' in locals() and pmbok_chunks else False)
question = st.text_area("ถามคำถาม", value=st.session_state.get("ai_question_prefill", ""), placeholder="เช่น สถานะออเดอร์ 182xxxx เป็นอย่างไร? หรือ Invoice ของ Customer X อยู่ที่สถานะอะไร?", height=120)

st.markdown("**Quick prompts**")
prompt_cols = st.columns(4)
quick_prompts = [
    "โปรเจกต์ไหน Delay และต้องเร่งให้ทันกำหนดส่ง?",
    "ใบแจ้งหนี้ไหนจ่ายช้า/Overdue ต้องตามลูกค้า?",
    "ยอด Invoice ที่ Paid แล้วปีนี้รวมเท่าไหร่?",
    "สรุปความเสี่ยงหลักของโปรเจกต์มูลค่าสูงสุด 3 อันดับ",
]
for col, p in zip(prompt_cols, quick_prompts):
    if col.button(p, use_container_width=True):
        question = p
        st.session_state["ai_question_prefill"] = p

# Preserve the selected quick prompt in the text area
if "ai_question_prefill" in st.session_state and not question.strip():
    question = st.session_state["ai_question_prefill"]
if st.button("Ask AI", type="primary", disabled=not question.strip()):
    with st.spinner("กำลังค้นหาและตอบ..."):
        corpus = build_corpus(project_df, invoice_df, domain, pmbok_use, pmbok_chunks, include_workflow=True)
        context = rank_docs(question, corpus, top_k=8)
        try:
            chosen = "grok" if model_choice == "grok_openrouter" else "ollama"
            stream = call_model_stream(question, context, chosen)
            st.subheader("Answer:")
            st.write_stream(stream)
            with st.expander("ดูบริบทที่ใช้ตอบ (context)"):
                for idx, doc in enumerate(context, 1):
                    st.markdown(f"{idx}. **{doc['source']}** — {doc['text']}")
        except Exception as exc:  # noqa: BLE001
            st.error(f"เรียกโมเดลไม่สำเร็จ: {exc}")
elif not question.strip():
    st.info("พิมพ์คำถามก่อน แล้วกด Ask AI")
