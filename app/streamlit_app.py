import json
import os
from pathlib import Path

import httpx
import pandas as pd
import streamlit as st

st.set_page_config(
    page_title="FinRAG | Rwanda Financial Intelligence",
    page_icon="\U0001f4d8",
    layout="wide",
)
st.markdown(
    "<style>.stApp {background:#f5f7fb} h1,h2,h3{color:#15385f} .stMetric{background:white;padding:18px;border-radius:8px} a{color:#165ba8}</style>",
    unsafe_allow_html=True,
)
API = os.getenv("API_URL", "http://127.0.0.1:8000")


def api(path, payload=None):
    try:
        token = os.getenv("API_ACCESS_TOKEN", "")
        headers = {"Authorization": "Bearer " + token} if token else {}
        r = (
            httpx.get(API + path, timeout=180, headers=headers)
            if payload is None
            else httpx.post(API + path, json=payload, timeout=180, headers=headers)
        )
        r.raise_for_status()
        return r.json()
    except httpx.HTTPError:
        st.error(
            "Unable to load data. Start the backend and check its configuration. If rate limited, wait one minute."
        )
        st.stop()


def show(result):
    st.caption("Mode: " + result["mode"] + " | " + str(result["latency_ms"]) + " ms")
    if result["abstained"]:
        st.warning(result["answer"])
    else:
        st.text(result["answer"])
    if len({e["document_id"] for e in result["evidence"]}) > 1:
        st.info(
            "Compare reporting periods, definitions and publication vintages before interpreting differing figures. Source quotations do not resolve revisions."
        )
    used = {claim["chunk_id"] for claim in result.get("claims", [])}
    for source in result["evidence"]:
        if source["chunk_id"] in used:
            st.link_button(
                "Open source ["
                + str(source["chunk_id"])
                + "] | page "
                + str(source["page"]),
                source["citation_url"],
            )
            st.caption(source["title"] + " | Published " + source["publication_date"])
    for e in result["evidence"]:
        with st.expander(
            f"[{e['chunk_id']}] {e['title']} | page {e['page']}",
            expanded=result["mode"] == "retrieval_only",
        ):
            st.write(e["text"])
            st.link_button("Open source | page " + str(e["page"]), e["citation_url"])
            st.caption(e["organization"] + " | " + e["publication_date"])
    st.caption(result.get("support_assessment", ""))
    if result.get("provider") and result["provider"] != "none":
        st.caption(
            "Provider: "
            + result["provider"]
            + " | Only source-verified quotations are published."
        )


st.sidebar.title("FinRAG")
st.sidebar.caption("RWANDA FINANCIAL INTELLIGENCE")
page = st.sidebar.radio(
    "Workspace",
    [
        "Home",
        "AI Research Assistant",
        "Compare Reports",
        "Document Library",
        "Data Quality",
        "Evaluation",
    ],
)
st.sidebar.divider()
st.sidebar.caption(
    "Independent portfolio project. Not affiliated with BNR or NISR. Research use only."
)
st.title(page)
if page == "Home":
    st.subheader("Financial research with traceable evidence")
    st.write(
        "Explore official Rwandan economic publications, compare reports and inspect the quality of the underlying evidence."
    )
    state = api("/health")
    st.info(
        "Answer provider: "
        + state["mode"]
        + " | Embeddings: "
        + state["embedding_backend"]
        + (
            ". Lexical demonstration retrieval."
            if state["embedding_backend"] == "hash"
            else ". Sentence Transformers semantic retrieval enabled."
        )
    )
    q = api("/quality")
    a, b, c = st.columns(3)
    a.metric("Indexed documents", q["documents"])
    b.metric("Searchable passages", q["chunks"])
    c.metric("Processing failures", q["failed_runs"])
    st.write(
        "Try: What does the GDP report say about agriculture? Specify a year or select a report for more precise evidence."
    )
    st.caption(
        "Historical reports cannot establish current conditions. Verify definitions, periods, and revisions in the source."
    )
elif page == "AI Research Assistant":
    docs = api("/documents")
    titles = {
        "All reports": None,
        **{d["title"] + " (#" + str(d["id"]) + ")": d["id"] for d in docs},
    }
    selected = st.selectbox("Report", list(titles))
    col1, col2 = st.columns(2)
    org = col1.selectbox("Publisher", ["All", "BNR", "NISR"])
    year = col2.text_input("Publication year (optional)")
    if "history" not in st.session_state:
        st.session_state.history = []
    for item in st.session_state.history:
        with st.chat_message("user"):
            st.write(item["question"])
        with st.chat_message("assistant"):
            show(item["result"])
    question = st.chat_input("Ask about an official report")
    if question:
        filters = {"document_id": titles[selected]}
        if org != "All":
            filters["organization"] = org
        if year:
            if not year.isdigit() or not 1900 <= int(year) <= 2100:
                st.error("Enter a year between 1900 and 2100")
                st.stop()
            filters["year"] = int(year)
        with st.chat_message("user"):
            st.write(question)
        with st.chat_message("assistant"):
            with st.spinner("Finding supporting evidence..."):
                result = api("/ask", {"question": question, "filters": filters})
            show(result)
        st.session_state.history.append({"question": question, "result": result})
elif page == "Compare Reports":
    docs = api("/documents")
    if len(docs) < 2:
        st.info("Ingest at least two reports to compare them.")
        st.stop()
    names = {d["id"]: d["title"] for d in docs}
    a, b = st.columns(2)
    left = a.selectbox("First report", list(names), format_func=names.get)
    right = b.selectbox("Second report", list(names), index=1, format_func=names.get)
    topic = st.selectbox(
        "Research topic",
        [
            "inflation",
            "monetary policy decisions",
            "financial sector risks",
            "economic outlook",
            "policy recommendations",
            "agriculture GDP",
        ],
    )
    specific_topic = st.text_input(
        "Specific comparison question (optional)",
        max_chars=300,
        placeholder="For example: urban CPI annual increase",
    )
    if specific_topic.strip():
        topic = specific_topic.strip()
    if st.button("Compare evidence"):
        if left == right:
            st.error("Select different reports")
            st.stop()
        result = api("/compare", {"left_id": left, "right_id": right, "topic": topic})
        a, b = st.columns(2)
        with a:
            show(result["left"])
        with b:
            show(result["right"])
        st.info(result["interpretation"])
        if result.get("comparison"):
            st.subheader("Cited comparison")
            show(result["comparison"])
elif page == "Document Library":
    docs = api("/documents")
    text = st.text_input("Search titles")
    docs = [d for d in docs if text.lower() in d["title"].lower()]
    if not docs:
        st.info(
            "No matching documents. Run the curated ingestion command in the README."
        )
    for d in docs:
        with st.expander(d["title"], expanded=True):
            st.write(
                d["organization"]
                + " | "
                + d["publication_date"]
                + " | "
                + d["document_type"]
                + " | "
                + d["status"]
            )
            st.link_button("Official document", d["source_url"])
            st.caption(
                "Retrieved: " + d["retrieved_at"] + " | SHA256: " + d["content_hash"]
            )
            st.write(d["usage_notes"])
elif page == "Data Quality":
    q = api("/quality")
    a, b, c = st.columns(3)
    a.metric("Documents", q["documents"])
    b.metric("Chunks", q["chunks"])
    c.metric("Duplicates skipped", q["duplicate_runs"])
    st.caption(
        q["database"] + " | Last successful ingestion: " + str(q["last_success"])
    )
    st.subheader("Extraction checks")
    st.dataframe(pd.DataFrame(q["quality"]), width="stretch")
    st.subheader("Ingestion audit")
    st.dataframe(pd.DataFrame(q["audit"]), width="stretch")
    st.subheader("Governance and provenance")
    st.json(api("/governance"))
else:
    st.subheader("Development evaluation: original 15-report corpus")
    result = api("/evaluation")
    if result.get("status") == "not_run":
        st.info("No evaluation run. Follow the README to generate measured results.")
    else:
        st.warning(
            "Automated retrieval and citation checks. These are not human-verified answer-faithfulness scores."
        )
        st.json(result)

    holdout_path = (
        Path(__file__).resolve().parents[1] / "evaluation/results/holdout-rag.json"
    )
    if holdout_path.exists():
        holdout = json.loads(holdout_path.read_text())
        st.subheader("Holdout evaluation: expanded 30-report corpus")
        st.caption(
            "Saved evaluation artifact, not a live accuracy guarantee. No tuning against these questions; independent human review is pending."
        )
        st.write(
            "Status: "
            + holdout["status"]
            + " | Questions: "
            + str(holdout["n"])
            + "/"
            + str(holdout["planned"])
        )
        st.json(holdout["metrics"])
